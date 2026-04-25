"""
Celery tasks for the Playto Payout Engine.

process_payout: Simulates bank settlement for a single payout.
    - 70% chance: success → status=completed, create DEBIT entry
    - 20% chance: failure → status=failed, create RELEASE entry
    - 10% chance: hang → stays in processing (will be retried by beat task)

retry_stuck_payouts: Periodic task that finds payouts stuck in "processing"
    for more than 30 seconds. Retries with exponential backoff, max 3 attempts.
"""
import random
import time
import logging
from datetime import timedelta

from celery import shared_task
from django.db import transaction
from django.utils import timezone
from django.conf import settings

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=0)
def process_payout(self, payout_id):
    """
    Process a single payout by simulating bank settlement.

    This task runs asynchronously via Celery (not faked sync).
    It picks up a pending payout, transitions it to processing,
    then simulates the bank response.
    """
    from payouts.models import Payout, LedgerEntry
    from payouts.services import create_ledger_entry

    try:
        with transaction.atomic():
            # Lock the payout row to prevent concurrent processing
            payout = Payout.objects.select_for_update().get(id=payout_id)

            if payout.status == Payout.Status.PROCESSING:
                # Already being processed (retry scenario) — continue
                pass
            elif payout.status == Payout.Status.PENDING:
                # Transition: pending → processing
                payout.transition_to(Payout.Status.PROCESSING)
                payout.attempts += 1
                payout.last_attempted_at = timezone.now()
                payout.save(update_fields=["status", "attempts", "last_attempted_at", "updated_at"])
            else:
                # Already completed or failed — nothing to do
                logger.info(f"Payout {payout_id} is already in {payout.status} state, skipping.")
                return {"payout_id": str(payout_id), "status": payout.status}

        # --- Simulate bank settlement (outside the lock) ---
        config = settings.PAYOUT_CONFIG
        roll = random.random()

        if roll < config["SUCCESS_RATE"]:
            # 70% — Bank confirms settlement
            _complete_payout(payout_id)
            return {"payout_id": str(payout_id), "status": "completed"}

        elif roll < config["SUCCESS_RATE"] + config["FAILURE_RATE"]:
            # 20% — Bank rejects the transfer
            _fail_payout(payout_id, reason="Bank rejected: insufficient funds or invalid account")
            return {"payout_id": str(payout_id), "status": "failed"}

        else:
            # 10% — Bank hangs (no response)
            # We do nothing — the payout stays in "processing".
            # The retry_stuck_payouts beat task will pick it up after 30s.
            logger.warning(f"Payout {payout_id} — bank response timed out (simulated hang)")
            return {"payout_id": str(payout_id), "status": "processing_hung"}

    except Payout.DoesNotExist:
        logger.error(f"Payout {payout_id} not found")
        return {"payout_id": str(payout_id), "error": "not_found"}
    except ValueError as e:
        logger.error(f"Invalid state transition for payout {payout_id}: {e}")
        return {"payout_id": str(payout_id), "error": str(e)}


def _complete_payout(payout_id):
    """
    Atomically: transition payout to completed + create DEBIT ledger entry.

    Both operations happen in the same transaction so either both succeed
    or neither does. This prevents the balance from being wrong if the
    state update succeeds but the ledger entry fails (or vice versa).
    """
    from payouts.models import Payout, LedgerEntry
    from payouts.services import create_ledger_entry

    with transaction.atomic():
        payout = Payout.objects.select_for_update().get(id=payout_id)

        # State machine check — only processing → completed is legal
        payout.transition_to(Payout.Status.COMPLETED)
        payout.save(update_fields=["status", "completed_at", "updated_at"])

        # 1. Release the HOLD — the reservation is no longer needed
        create_ledger_entry(
            merchant_id=payout.merchant_id,
            entry_type=LedgerEntry.EntryType.RELEASE,
            amount_paise=payout.amount_paise,
            description=f"Payout {payout.id} reservation released (settled)",
            reference_id=payout.id,
        )

        # 2. Create DEBIT entry — money officially leaves the merchant's balance
        create_ledger_entry(
            merchant_id=payout.merchant_id,
            entry_type=LedgerEntry.EntryType.DEBIT,
            amount_paise=payout.amount_paise,
            description=f"Payout {payout.id} completed — settled to bank",
            reference_id=payout.id,
        )

    logger.info(f"Payout {payout_id} completed successfully")


def _fail_payout(payout_id, reason=""):
    """
    Atomically: transition payout to failed + create RELEASE ledger entry.

    The RELEASE entry returns the held funds back to the merchant's
    available balance. This happens in the same transaction as the
    state change to guarantee consistency.
    """
    from payouts.models import Payout, LedgerEntry
    from payouts.services import create_ledger_entry

    with transaction.atomic():
        payout = Payout.objects.select_for_update().get(id=payout_id)

        # State machine check — only processing → failed is legal
        payout.transition_to(Payout.Status.FAILED)
        payout.failure_reason = reason
        payout.save(update_fields=["status", "failure_reason", "updated_at"])

        # Create RELEASE entry — held funds return to available balance
        create_ledger_entry(
            merchant_id=payout.merchant_id,
            entry_type=LedgerEntry.EntryType.RELEASE,
            amount_paise=payout.amount_paise,
            description=f"Payout {payout.id} failed — funds released. Reason: {reason}",
            reference_id=payout.id,
        )

    logger.info(f"Payout {payout_id} failed: {reason}")


@shared_task
def retry_stuck_payouts():
    """
    Periodic task: find payouts stuck in 'processing' for > 30 seconds.

    For each stuck payout:
    - If attempts < max_attempts (3): retry with exponential backoff
    - If attempts >= max_attempts: move to failed and release funds

    Exponential backoff: delay = 2^attempts seconds (2s, 4s, 8s)
    """
    from payouts.models import Payout

    config = settings.PAYOUT_CONFIG
    timeout = timedelta(seconds=config["STUCK_TIMEOUT_SECONDS"])
    cutoff = timezone.now() - timeout

    stuck_payouts = Payout.objects.filter(
        status=Payout.Status.PROCESSING,
        last_attempted_at__lt=cutoff,
    )

    for payout in stuck_payouts:
        if payout.attempts >= payout.max_attempts:
            # Max retries exceeded — fail the payout and release funds
            logger.warning(
                f"Payout {payout.id} exceeded max attempts ({payout.max_attempts}). "
                f"Moving to failed and releasing funds."
            )
            _fail_payout(
                str(payout.id),
                reason=f"Max retry attempts ({payout.max_attempts}) exceeded — bank unresponsive"
            )
        else:
            # Retry with exponential backoff
            backoff_seconds = 2 ** payout.attempts  # 2, 4, 8 seconds
            logger.info(
                f"Retrying stuck payout {payout.id} (attempt {payout.attempts + 1}/"
                f"{payout.max_attempts}) with {backoff_seconds}s backoff"
            )

            # Update attempt counter before retrying
            with transaction.atomic():
                p = Payout.objects.select_for_update().get(id=payout.id)
                p.attempts += 1
                p.last_attempted_at = timezone.now()
                p.save(update_fields=["attempts", "last_attempted_at", "updated_at"])

            # Dispatch retry with backoff delay
            process_payout.apply_async(
                args=[str(payout.id)],
                countdown=backoff_seconds,
            )
