# EXPLAINER.md — Playto Payout Engine

## 1. The Ledger

### Balance Calculation Query

The balance is **never stored** — it is always computed from the immutable ledger via database-level aggregation. Here's the exact query (from `payouts/services/__init__.py`):

```python
aggregation = LedgerEntry.objects.filter(
    merchant_id=merchant_id
).aggregate(
    total_credits=Sum(
        Case(
            When(entry_type=LedgerEntry.EntryType.CREDIT, then="amount_paise"),
            default=Value(0),
            output_field=BigIntegerField(),
        )
    ),
    total_debits=Sum(
        Case(
            When(entry_type=LedgerEntry.EntryType.DEBIT, then="amount_paise"),
            default=Value(0),
            output_field=BigIntegerField(),
        )
    ),
    total_holds=Sum(
        Case(
            When(entry_type=LedgerEntry.EntryType.HOLD, then="amount_paise"),
            default=Value(0),
            output_field=BigIntegerField(),
        )
    ),
    total_releases=Sum(
        Case(
            When(entry_type=LedgerEntry.EntryType.RELEASE, then="amount_paise"),
            default=Value(0),
            output_field=BigIntegerField(),
        )
    ),
)
```

This generates a single SQL query:
```sql
SELECT
    SUM(CASE WHEN entry_type='credit' THEN amount_paise ELSE 0 END) as total_credits,
    SUM(CASE WHEN entry_type='debit'  THEN amount_paise ELSE 0 END) as total_debits,
    SUM(CASE WHEN entry_type='hold'   THEN amount_paise ELSE 0 END) as total_holds,
    SUM(CASE WHEN entry_type='release' THEN amount_paise ELSE 0 END) as total_releases
FROM ledger_entries
WHERE merchant_id = %s;
```

**Available balance** = credits + releases - debits - holds

### Why this model?

I used **four entry types** instead of just credit/debit because payout lifecycle has intermediate states:

1. **CREDIT** — Money comes in (customer payment received). This is the simplest path.
2. **HOLD** — Funds reserved for a pending payout. This reduces available balance immediately when a payout is requested, preventing double-spending.
3. **DEBIT** — Funds permanently leave the merchant's balance (payout completed successfully).
4. **RELEASE** — Held funds returned (payout failed). This restores available balance.

The key insight: **a hold is not a debit**. If we deducted immediately, a failed payout would need a compensating credit entry, which would inflate the `total_credits` metric and make reconciliation confusing. With holds and releases, the invariant is simple:

```
credits - debits = available_balance + held_balance
```

This invariant is checked in `test_balance_invariant`. If it ever breaks, the ledger is corrupt.

All entries are **append-only** (immutable). We never update or delete ledger rows. This makes the system auditable and provides a complete history for reconciliation.

---

## 2. The Lock

### Exact Code

From `payouts/services/payout_service.py`:

```python
with transaction.atomic():
    # Acquire an exclusive row-level lock on the merchant.
    # SELECT ... FROM merchants WHERE id = %s FOR UPDATE
    merchant = Merchant.objects.select_for_update().get(id=merchant_id)

    # Compute available balance at DB level (inside the lock)
    balance_info = get_merchant_balance(merchant_id)
    available = balance_info["available_balance_paise"]

    if available < amount_paise:
        raise InsufficientBalanceError(...)

    # Create payout + HOLD entry inside the same transaction
    payout = Payout.objects.create(...)
    create_ledger_entry(entry_type="hold", amount_paise=amount_paise, ...)
```

### Database Primitive

This relies on **PostgreSQL `SELECT ... FOR UPDATE`**, which acquires an exclusive **row-level lock** on the merchant row. The lock is held for the duration of the `transaction.atomic()` block.

**How it prevents the race condition:**

Scenario: Merchant has ₹100 balance. Two requests arrive simultaneously for ₹60 each.

1. **Request A** enters the `atomic()` block and executes `SELECT ... FOR UPDATE` on the merchant row. PostgreSQL grants the lock.
2. **Request B** enters the `atomic()` block and executes `SELECT ... FOR UPDATE` on the **same** merchant row. PostgreSQL **blocks** this query — B waits.
3. **Request A** computes balance (₹100 ≥ ₹60 ✓), creates the hold, and the transaction commits. Lock released.
4. **Request B** unblocks, re-reads the merchant row, computes balance (**₹40** < ₹60 ✗), raises `InsufficientBalanceError`.

The critical point: the balance check and the hold creation happen inside the same transaction, under the same lock. There is no window where another transaction can modify the balance between the check and the write.

**Why SELECT FOR UPDATE instead of alternatives:**
- **Application-level locks (threading.Lock)**: Only work within a single process. Useless with multiple Django workers or Gunicorn processes.
- **Django F() expressions**: Good for single atomic updates, but the check-then-deduct pattern requires reading first, which F() doesn't protect.
- **Optimistic locking (version field)**: Would require retry logic at the API level and doesn't guarantee exactly-one-succeeds semantics.
- **SERIALIZABLE isolation level**: Would work but is a sledgehammer — locks more than needed and causes more retries.

---

## 3. The Idempotency

### How the system knows it has seen a key before

Two mechanisms work together:

1. **`IdempotencyKey` model** with a unique constraint on `(merchant_id, key)`. Before creating a payout, we check if this combination exists.

2. **`Payout` model** also has a unique constraint on `(merchant_id, idempotency_key)`. This is the database-level safety net if the IdempotencyKey check passes but two requests race.

From `payouts/services/payout_service.py`:

```python
# Step 1: Check idempotency key
try:
    existing_key = IdempotencyKey.objects.get(
        merchant_id=merchant_id,
        key=idempotency_key,
    )
    if existing_key.is_expired:
        existing_key.delete()  # Expired — treat as new
    elif existing_key.is_processing:
        raise DuplicateIdempotencyKeyError(...)  # First request still in-flight
    else:
        # Return cached response — exact same payout object
        payout = Payout.objects.get(
            merchant_id=merchant_id,
            idempotency_key=idempotency_key,
        )
        return payout, False  # False = not newly created
except IdempotencyKey.DoesNotExist:
    pass  # New key, proceed
```

### What happens if the first request is in-flight when the second arrives

The `IdempotencyKey` has an `is_processing` boolean field:

1. When the first request starts, it creates an `IdempotencyKey` with `is_processing=True`.
2. When the second request arrives and finds the key with `is_processing=True`, it receives a **409 Conflict** response with `"IDEMPOTENCY_CONFLICT"`.
3. Once the first request completes, it updates `is_processing=False` and stores the response body.
4. Any **subsequent** requests (third, fourth, etc.) will find `is_processing=False` and receive the cached response.

This prevents the edge case where the client retries before the original request finishes — without this, the second request could create a duplicate or interfere with the in-progress transaction.

**Database-level safety net**: Even if the `IdempotencyKey` check somehow doesn't catch a race (e.g., both requests execute the check at the exact same nanosecond), the `UNIQUE` constraint on `Payout(merchant, idempotency_key)` will cause an `IntegrityError` on the second INSERT. The code catches this and returns the existing payout.

---

## 4. The State Machine

### Where failed-to-completed is blocked

In `payouts/models.py`, the `Payout` model:

```python
class Payout(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending"
        PROCESSING = "processing"
        COMPLETED = "completed"
        FAILED = "failed"

    # Legal state transitions — this is the definitive map
    VALID_TRANSITIONS = {
        Status.PENDING: {Status.PROCESSING},
        Status.PROCESSING: {Status.COMPLETED, Status.FAILED},
        # COMPLETED and FAILED are terminal states — not in the map at all
    }

    def transition_to(self, new_status):
        """
        Attempt a state transition. Raises ValueError if illegal.
        This is the ONLY place where payout status should be changed.
        """
        if not self.can_transition_to(new_status):
            raise ValueError(
                f"Illegal state transition: {self.status} → {new_status}. "
                f"Allowed transitions from '{self.status}': "
                f"{self.VALID_TRANSITIONS.get(self.status, 'none')}"
            )
        self.status = new_status
```

**`COMPLETED` and `FAILED` are not keys in `VALID_TRANSITIONS`**, so `can_transition_to()` returns `False` for ANY transition from those states. This blocks:
- `completed → pending` ✗
- `completed → processing` ✗
- `failed → completed` ✗
- `failed → pending` ✗
- `processing → pending` (backward) ✗

The `transition_to()` method is the **only** place where status changes happen. Direct assignment (`payout.status = "completed"`) is avoided throughout the codebase — all state changes go through `transition_to()`.

This is enforced in `tasks.py` for both the happy path and failure path:

```python
# In _complete_payout:
payout.transition_to(Payout.Status.COMPLETED)  # Only legal from PROCESSING

# In _fail_payout:
payout.transition_to(Payout.Status.FAILED)     # Only legal from PROCESSING
```

If anything tries to illegally transition a completed or failed payout, the `ValueError` propagates up and the operation is rejected.

---

## 5. The AI Audit

### Example: AI initially generated incorrect balance aggregation

**What AI gave me (wrong):**

```python
def get_merchant_balance(merchant_id):
    credits = LedgerEntry.objects.filter(
        merchant_id=merchant_id,
        entry_type='credit'
    ).aggregate(total=Sum('amount_paise'))['total'] or 0

    debits = LedgerEntry.objects.filter(
        merchant_id=merchant_id,
        entry_type='debit'
    ).aggregate(total=Sum('amount_paise'))['total'] or 0

    return credits - debits
```

**What I caught:**

This code has two problems:

1. **Multiple database queries** — it hits the database 2 times (one for credits, one for debits), which creates a race condition. Between query 1 and query 2, a new ledger entry could be inserted, giving an inconsistent balance. This is the same class of bug as check-then-act race conditions.

2. **Missing hold/release types** — it only considers credits and debits, completely ignoring the hold/release lifecycle. A merchant with ₹100 credits and a ₹60 hold would show ₹100 available instead of ₹40. This would allow overdrawing: the merchant could request another ₹60 payout and both would be approved.

**What I replaced it with:**

A single aggregation query using `CASE/WHEN` expressions that computes all four sums in one database round-trip:

```python
aggregation = LedgerEntry.objects.filter(
    merchant_id=merchant_id
).aggregate(
    total_credits=Sum(Case(When(entry_type='credit', then='amount_paise'), default=Value(0), output_field=BigIntegerField())),
    total_debits=Sum(Case(When(entry_type='debit', then='amount_paise'), default=Value(0), output_field=BigIntegerField())),
    total_holds=Sum(Case(When(entry_type='hold', then='amount_paise'), default=Value(0), output_field=BigIntegerField())),
    total_releases=Sum(Case(When(entry_type='release', then='amount_paise'), default=Value(0), output_field=BigIntegerField())),
)
```

This is **atomic at the database level** — PostgreSQL computes all four sums from a single snapshot of the table, eliminating the race condition. And it correctly accounts for all four entry types.

### Second example: AI put lock in wrong place

AI initially placed the `select_for_update()` call on the balance aggregation query:

```python
# WRONG — you can't SELECT FOR UPDATE on an aggregate query
balance = LedgerEntry.objects.select_for_update().filter(
    merchant_id=merchant_id
).aggregate(total=Sum('amount_paise'))
```

This doesn't work because `select_for_update()` locks individual rows returned by a query, but `aggregate()` doesn't return rows — it returns a computed value. The lock would apply to the ledger entries, but we'd be locking hundreds of rows unnecessarily and still not preventing concurrent payout creation.

The correct approach is to lock the **merchant row** (`Merchant.objects.select_for_update().get(id=merchant_id)`), which is a single row that serializes all payout operations for that merchant. This is cheaper (one row locked vs. hundreds) and semantically correct (we're serializing access to the merchant's account, not individual ledger entries).
