import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from payouts.models import Payout, LedgerEntry
from payouts.services import create_ledger_entry

completed_payouts = Payout.objects.filter(status='completed')
for p in completed_payouts:
    # Check if a release already exists for this payout
    exists = LedgerEntry.objects.filter(
        reference_id=p.id, 
        entry_type=LedgerEntry.EntryType.RELEASE
    ).exists()
    
    if not exists:
        print(f"Fixing payout {p.id} for merchant {p.merchant_id}")
        create_ledger_entry(
            merchant_id=p.merchant_id,
            entry_type=LedgerEntry.EntryType.RELEASE,
            amount_paise=p.amount_paise,
            description=f"Payout {p.id} reservation released (cleanup fix)",
            reference_id=p.id
        )
        print("Fixed.")
    else:
        print(f"Payout {p.id} already has a release entry.")
