"""
Payout service — handles the creation of payouts with concurrency control.

This is the most critical piece of the system. The key challenge:
A merchant with ₹100 balance submits two simultaneous ₹60 payout requests.
Exactly one must succeed; the other must be rejected.

We solve this with SELECT FOR UPDATE on the merchant row, which acquires
a row-level exclusive lock in PostgreSQL. This serializes concurrent
payout requests for the same merchant, preventing race conditions.

The lock is held for the duration of the transaction (transaction.atomic).
"""
from django.db import transaction, IntegrityError
from django.utils import timezone

from payouts.models import Merchant, BankAccount, Payout, IdempotencyKey, LedgerEntry
from payouts.services import get_merchant_balance, create_ledger_entry


class InsufficientBalanceError(Exception):
    pass


class InvalidBankAccountError(Exception):
    pass


class DuplicateIdempotencyKeyError(Exception):
    """Raised when a second request arrives while the first is still in-flight."""
    pass


def create_payout(merchant_id, amount_paise, bank_account_id, idempotency_key):
    """
    Create a payout request with full concurrency protection.

    Steps:
    1. Check idempotency — if key exists and has a response, return cached response.
    2. Acquire row-level lock on the merchant (SELECT FOR UPDATE).
    3. Compute available balance at DB level.
    4. If sufficient, create HOLD ledger entry + Payout record atomically.
    5. Dispatch to background worker for processing.

    Args:
        merchant_id: UUID of the merchant
        amount_paise: Amount to payout in paise (positive integer)
        bank_account_id: UUID of the bank account to send to
        idempotency_key: Client-supplied UUID for idempotency

    Returns:
        tuple: (payout, created) — the payout object and whether it was newly created

    Raises:
        InsufficientBalanceError: If available balance < amount_paise
        InvalidBankAccountError: If bank account doesn't belong to merchant
        DuplicateIdempotencyKeyError: If first request is still in-flight
    """
    if amount_paise <= 0:
        raise ValueError("Payout amount must be positive")

    # --- Step 1: Check idempotency key ---
    try:
        existing_key = IdempotencyKey.objects.get(
            merchant_id=merchant_id,
            key=idempotency_key,
        )
        if existing_key.is_expired:
            # Expired key — delete it and proceed as new request
            existing_key.delete()
        elif existing_key.is_processing:
            # First request is still in-flight — reject the duplicate
            raise DuplicateIdempotencyKeyError(
                "A request with this idempotency key is currently being processed. "
                "Please retry after a moment."
            )
        else:
            # Return cached response (the payout from the first request)
            payout = Payout.objects.get(
                merchant_id=merchant_id,
                idempotency_key=idempotency_key,
            )
            return payout, False  # False = not newly created
    except IdempotencyKey.DoesNotExist:
        pass  # New key, proceed

    # --- Step 2-4: Atomic transaction with row-level locking ---
    with transaction.atomic():
        # Acquire an exclusive row-level lock on the merchant.
        # SELECT ... FROM merchants WHERE id = %s FOR UPDATE
        #
        # This is the critical concurrency primitive. Any other transaction
        # trying to lock the same merchant row will BLOCK here until this
        # transaction commits or rolls back.
        #
        # This means two concurrent ₹60 requests on a ₹100 balance will
        # be serialized: the first acquires the lock, checks balance (₹100 >= ₹60 ✓),
        # creates the hold, and commits. The second then acquires the lock,
        # checks balance (₹40 < ₹60 ✗), and is rejected.
        merchant = Merchant.objects.select_for_update().get(id=merchant_id)

        # Verify the bank account belongs to this merchant
        try:
            bank_account = BankAccount.objects.get(
                id=bank_account_id,
                merchant_id=merchant_id,
            )
        except BankAccount.DoesNotExist:
            raise InvalidBankAccountError(
                f"Bank account {bank_account_id} does not belong to merchant {merchant_id}"
            )

        # Compute available balance at DB level (inside the lock)
        balance_info = get_merchant_balance(merchant_id)
        available = balance_info["available_balance_paise"]

        if available < amount_paise:
            raise InsufficientBalanceError(
                f"Insufficient balance. Available: Rs.{available / 100:.2f}, "
                f"Requested: Rs.{amount_paise / 100:.2f}"
            )

        # Create the payout record
        try:
            payout = Payout.objects.create(
                merchant=merchant,
                bank_account=bank_account,
                amount_paise=amount_paise,
                status=Payout.Status.PENDING,
                idempotency_key=idempotency_key,
            )
        except IntegrityError:
            # Race condition on idempotency key — another request won
            # This handles the case where two identical requests arrive
            # at the exact same moment and both pass the IdempotencyKey check.
            payout = Payout.objects.get(
                merchant_id=merchant_id,
                idempotency_key=idempotency_key,
            )
            return payout, False

        # Create HOLD ledger entry — funds are now reserved
        create_ledger_entry(
            merchant_id=merchant_id,
            entry_type=LedgerEntry.EntryType.HOLD,
            amount_paise=amount_paise,
            description=f"Funds held for payout {payout.id}",
            reference_id=payout.id,
        )

        # Record the idempotency key (in-processing state)
        try:
            IdempotencyKey.objects.create(
                merchant=merchant,
                key=idempotency_key,
                request_path="/api/v1/payouts/",
                request_method="POST",
                is_processing=True,
            )
        except IntegrityError:
            pass  # Key already exists from a race — that's fine

    # --- Step 5: Dispatch to background worker ---
    # In eager mode (local dev with SQLite), the task runs synchronously.
    # We catch errors here so the API response still succeeds — the payout
    # was created and funds held; the task can be retried later.
    import logging
    logger = logging.getLogger(__name__)
    try:
        from payouts.tasks import process_payout
        process_payout.delay(str(payout.id))
    except Exception as e:
        logger.warning(f"Task dispatch/execution error (non-fatal): {e}")

    return payout, True


def finalize_idempotency_key(merchant_id, idempotency_key, status_code, response_body):
    """
    Mark an idempotency key as completed and cache the response.
    Called after the payout request has been fully processed.
    """
    IdempotencyKey.objects.filter(
        merchant_id=merchant_id,
        key=idempotency_key,
    ).update(
        is_processing=False,
        response_status_code=status_code,
        response_body=response_body,
    )
