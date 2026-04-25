"""
Models for the Playto Payout Engine.

Key design decisions:
- All monetary amounts stored as BigIntegerField in paise (1 INR = 100 paise).
- Balance is NEVER stored; it is always derived from ledger entries via DB aggregation.
- Payout state machine enforces legal transitions at the model level.
- Idempotency keys are scoped per merchant and expire after 24 hours.
"""
import uuid
from django.db import models
from django.utils import timezone
from django.core.serializers.json import DjangoJSONEncoder


class Merchant(models.Model):
    """
    Represents a merchant who collects payments and requests payouts.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "merchants"

    def __str__(self):
        return f"{self.name} ({self.email})"


class BankAccount(models.Model):
    """
    Bank account details for a merchant (INR accounts only).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(
        Merchant, on_delete=models.CASCADE, related_name="bank_accounts"
    )
    account_holder_name = models.CharField(max_length=255)
    account_number = models.CharField(max_length=20)
    ifsc_code = models.CharField(max_length=11)
    bank_name = models.CharField(max_length=255)
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "bank_accounts"

    def __str__(self):
        return f"{self.bank_name} - ****{self.account_number[-4:]}"


class LedgerEntry(models.Model):
    """
    Immutable record of every money movement.

    Types:
    - CREDIT: Money coming in (customer payment received)
    - DEBIT: Money going out (payout completed)
    - HOLD: Funds reserved for a pending payout
    - RELEASE: Funds released back when a payout fails

    Balance = SUM(CREDIT) + SUM(RELEASE) - SUM(DEBIT) - SUM(HOLD)

    This is computed at the database level, never in Python.
    """

    class EntryType(models.TextChoices):
        CREDIT = "credit", "Credit"
        DEBIT = "debit", "Debit"
        HOLD = "hold", "Hold"
        RELEASE = "release", "Release"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(
        Merchant, on_delete=models.CASCADE, related_name="ledger_entries"
    )
    entry_type = models.CharField(max_length=10, choices=EntryType.choices)
    amount_paise = models.BigIntegerField(
        help_text="Amount in paise. Always positive. Direction determined by entry_type."
    )
    description = models.CharField(max_length=500, blank=True)
    reference_id = models.UUIDField(
        null=True, blank=True,
        help_text="FK to payout or external reference for traceability"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ledger_entries"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["merchant", "entry_type"]),
            models.Index(fields=["merchant", "created_at"]),
        ]

    def __str__(self):
        return f"{self.entry_type} Rs.{self.amount_paise / 100:.2f} for {self.merchant.name}"


class Payout(models.Model):
    """
    Represents a payout request with a strict state machine.

    Legal transitions:
        pending → processing → completed
        pending → processing → failed

    Illegal (rejected at model level):
        completed → anything
        failed → anything
        processing → pending
        Any backward transition
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    # Legal state transitions
    VALID_TRANSITIONS = {
        Status.PENDING: {Status.PROCESSING},
        Status.PROCESSING: {Status.COMPLETED, Status.FAILED},
    }

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(
        Merchant, on_delete=models.CASCADE, related_name="payouts"
    )
    bank_account = models.ForeignKey(
        BankAccount, on_delete=models.PROTECT, related_name="payouts"
    )
    amount_paise = models.BigIntegerField(
        help_text="Payout amount in paise"
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    idempotency_key = models.CharField(max_length=255)
    attempts = models.IntegerField(default=0)
    max_attempts = models.IntegerField(default=3)
    last_attempted_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    failure_reason = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "payouts"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["merchant", "idempotency_key"],
                name="unique_merchant_idempotency_key",
            ),
        ]
        indexes = [
            models.Index(fields=["status", "last_attempted_at"]),
            models.Index(fields=["merchant", "status"]),
        ]

    def __str__(self):
        return f"Payout {self.id} - Rs.{self.amount_paise / 100:.2f} ({self.status})"

    def can_transition_to(self, new_status):
        """Check if the transition to new_status is legal."""
        allowed = self.VALID_TRANSITIONS.get(self.status, set())
        return new_status in allowed

    def transition_to(self, new_status):
        """
        Attempt a state transition. Raises ValueError if the transition is illegal.

        This is the ONLY place where payout status should be changed.
        This prevents completed→pending, failed→completed, or any backward move.
        """
        if not self.can_transition_to(new_status):
            raise ValueError(
                f"Illegal state transition: {self.status} → {new_status}. "
                f"Allowed transitions from '{self.status}': "
                f"{self.VALID_TRANSITIONS.get(self.status, 'none')}"
            )
        self.status = new_status
        if new_status == self.Status.COMPLETED:
            self.completed_at = timezone.now()


class IdempotencyKey(models.Model):
    """
    Stores idempotency keys with their cached responses.

    Keys are scoped per merchant and expire after 24 hours.
    Uses a unique constraint on (merchant_id, key) to handle race conditions
    at the database level — if two identical requests arrive simultaneously,
    only one INSERT will succeed.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(
        Merchant, on_delete=models.CASCADE, related_name="idempotency_keys"
    )
    key = models.CharField(max_length=255)
    request_path = models.CharField(max_length=500)
    request_method = models.CharField(max_length=10)
    response_status_code = models.IntegerField(null=True)
    response_body = models.JSONField(null=True, encoder=DjangoJSONEncoder)
    is_processing = models.BooleanField(
        default=True,
        help_text="True while the original request is still in-flight."
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "idempotency_keys"
        constraints = [
            models.UniqueConstraint(
                fields=["merchant", "key"],
                name="unique_idempotency_per_merchant",
            ),
        ]

    def __str__(self):
        return f"IdemKey {self.key[:8]}... for {self.merchant.name}"

    @property
    def is_expired(self):
        """Keys expire after 24 hours."""
        from django.conf import settings
        ttl_hours = settings.PAYOUT_CONFIG.get("IDEMPOTENCY_KEY_TTL_HOURS", 24)
        expiry = self.created_at + timezone.timedelta(hours=ttl_hours)
        return timezone.now() > expiry
