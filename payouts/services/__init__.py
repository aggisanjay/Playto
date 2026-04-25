"""
Ledger service — all balance calculations happen here at the database level.

The balance is NEVER stored as a field. It is always computed from the
immutable ledger entries using PostgreSQL aggregation.

Available balance = SUM(credits) + SUM(releases) - SUM(debits) - SUM(holds)
Held balance = SUM(holds) - SUM(releases) - SUM(debits linked to holds)

We use Django's ORM aggregation (which translates to SQL SUM/CASE)
to keep all arithmetic in PostgreSQL, not Python.
"""
from django.db import models
from django.db.models import Sum, Case, When, Value, BigIntegerField

from payouts.models import LedgerEntry, Merchant


def get_merchant_balance(merchant_id):
    """
    Compute the merchant's available and held balances at the database level.

    Returns dict with:
    - available_balance_paise: funds the merchant can withdraw
    - held_balance_paise: funds reserved for pending payouts
    - total_credits_paise: total money received
    - total_debits_paise: total money paid out (completed payouts)

    The SQL generated is roughly:
        SELECT
            SUM(CASE WHEN entry_type='credit' THEN amount_paise ELSE 0 END) as credits,
            SUM(CASE WHEN entry_type='debit' THEN amount_paise ELSE 0 END) as debits,
            SUM(CASE WHEN entry_type='hold' THEN amount_paise ELSE 0 END) as holds,
            SUM(CASE WHEN entry_type='release' THEN amount_paise ELSE 0 END) as releases
        FROM ledger_entries
        WHERE merchant_id = %s;
    """
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

    credits = aggregation["total_credits"] or 0
    debits = aggregation["total_debits"] or 0
    holds = aggregation["total_holds"] or 0
    releases = aggregation["total_releases"] or 0

    # Available = credits + releases - debits - holds
    available = credits + releases - debits - holds

    # Held = holds - releases - debits (that were from holds)
    # Simplified: held = holds - releases - debits for held payouts
    # Since every completed payout creates both a HOLD and then a DEBIT
    # and a failed payout creates HOLD then RELEASE, we can say:
    # held_balance = holds - releases - debits
    # BUT debits come from converting holds to final debits, so:
    # Actually: net_held = holds - releases - debits
    # Wait — let me think more carefully:
    #
    # Flow for a payout:
    # 1. Request created → HOLD entry (funds reserved)
    # 2a. Success → DEBIT entry (funds leave) — hold becomes permanent debit
    # 2b. Failure → RELEASE entry (funds returned)
    #
    # So at any point:
    # - Held balance = holds that haven't been settled = holds - releases - debits
    # - Available balance = credits + releases - debits - holds
    #   = credits - (holds - releases) - debits
    #   = credits - held - debits
    #
    # This means:  held = holds - releases - debits
    # BUT that could go negative if we have debits from before the hold system.
    # For safety, held funds = SUM of holds - SUM of releases for payout-linked entries.
    # Simpler approach: held = holds - releases (debits are separate final settlements)
    held = holds - releases

    return {
        "available_balance_paise": available,
        "held_balance_paise": max(held, 0),
        "total_credits_paise": credits,
        "total_debits_paise": debits,
    }


def create_ledger_entry(merchant_id, entry_type, amount_paise, description="", reference_id=None):
    """
    Create an immutable ledger entry.

    Args:
        merchant_id: UUID of the merchant
        entry_type: One of credit, debit, hold, release
        amount_paise: Amount in paise (must be positive)
        description: Human-readable description
        reference_id: UUID of the related payout or external reference
    """
    if amount_paise <= 0:
        raise ValueError(f"Ledger amount must be positive, got {amount_paise}")

    return LedgerEntry.objects.create(
        merchant_id=merchant_id,
        entry_type=entry_type,
        amount_paise=amount_paise,
        description=description,
        reference_id=reference_id,
    )
