"""
Management command to seed the database with test merchants and credit history.

Creates 3 merchants, each with bank accounts and credit history.
This simulates the state after merchants have collected customer payments.
"""
import uuid
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone

from payouts.models import Merchant, BankAccount, LedgerEntry


class Command(BaseCommand):
    help = "Seed the database with test merchants, bank accounts, and credit history"

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("[*] Seeding database..."))

        # Clear existing data (order matters for FK constraints)
        from payouts.models import Payout, IdempotencyKey
        IdempotencyKey.objects.all().delete()
        Payout.objects.all().delete()
        LedgerEntry.objects.all().delete()
        BankAccount.objects.all().delete()
        Merchant.objects.all().delete()

        # --- Merchant 1: Acme Digital Agency ---
        m1 = Merchant.objects.create(
            name="Acme Digital Agency",
            email="finance@acmedigital.in",
        )
        ba1 = BankAccount.objects.create(
            merchant=m1,
            account_holder_name="Acme Digital Pvt Ltd",
            account_number="1234567890123456",
            ifsc_code="HDFC0001234",
            bank_name="HDFC Bank",
            is_primary=True,
        )
        # Credit history — ₹50,000 total from 5 customer payments
        credits_m1 = [
            (1500000, "Invoice #INV-001 — Webflow project for ClientCo (USA)", 30),
            (800000, "Invoice #INV-002 — SEO retainer — GlobalTech LLC", 25),
            (1200000, "Invoice #INV-003 — Shopify store build — RetailMax Inc", 18),
            (500000, "Invoice #INV-004 — Landing page design — StartupHQ", 10),
            (1000000, "Invoice #INV-005 — API integration — DataCorp", 5),
        ]
        for amount, desc, days_ago in credits_m1:
            LedgerEntry.objects.create(
                merchant=m1,
                entry_type=LedgerEntry.EntryType.CREDIT,
                amount_paise=amount,
                description=desc,
                created_at=timezone.now() - timedelta(days=days_ago),
            )

        self.stdout.write(self.style.SUCCESS(
            f"  [OK] {m1.name} - Rs.{sum(c[0] for c in credits_m1)/100:,.2f} in credits"
        ))

        # --- Merchant 2: Priya Freelance Design ---
        m2 = Merchant.objects.create(
            name="Priya Sharma — Freelance Designer",
            email="priya@priyaDesigns.in",
        )
        ba2 = BankAccount.objects.create(
            merchant=m2,
            account_holder_name="Priya Sharma",
            account_number="9876543210987654",
            ifsc_code="ICIC0005678",
            bank_name="ICICI Bank",
            is_primary=True,
        )
        ba2b = BankAccount.objects.create(
            merchant=m2,
            account_holder_name="Priya Sharma",
            account_number="5555666677778888",
            ifsc_code="SBIN0009012",
            bank_name="State Bank of India",
            is_primary=False,
        )
        # Credit history — ₹25,000 total from 4 customer payments
        credits_m2 = [
            (750000, "Brand identity package — TechNova (UK)", 22),
            (500000, "UI/UX audit — HealthFirst App (Singapore)", 15),
            (400000, "Social media creatives — FoodieBox (UAE)", 8),
            (850000, "Product design sprint — EduLearn (USA)", 3),
        ]
        for amount, desc, days_ago in credits_m2:
            LedgerEntry.objects.create(
                merchant=m2,
                entry_type=LedgerEntry.EntryType.CREDIT,
                amount_paise=amount,
                description=desc,
                created_at=timezone.now() - timedelta(days=days_ago),
            )

        self.stdout.write(self.style.SUCCESS(
            f"  [OK] {m2.name} - Rs.{sum(c[0] for c in credits_m2)/100:,.2f} in credits"
        ))

        # --- Merchant 3: DevStack Solutions ---
        m3 = Merchant.objects.create(
            name="DevStack Solutions",
            email="payouts@devstack.io",
        )
        ba3 = BankAccount.objects.create(
            merchant=m3,
            account_holder_name="DevStack Solutions LLP",
            account_number="1111222233334444",
            ifsc_code="AXIS0003456",
            bank_name="Axis Bank",
            is_primary=True,
        )
        # Credit history — ₹1,00,000 total from 6 customer payments
        credits_m3 = [
            (2000000, "SaaS MVP development — CloudFirst (USA)", 45),
            (1500000, "Mobile app development — FinEdge (Australia)", 35),
            (1800000, "Backend architecture — LogiTrack (Germany)", 28),
            (2200000, "Full-stack project — MedConnect (Canada)", 20),
            (1000000, "DevOps setup — ScaleUp (USA)", 12),
            (1500000, "API gateway project — PayRoute (UK)", 4),
        ]
        for amount, desc, days_ago in credits_m3:
            LedgerEntry.objects.create(
                merchant=m3,
                entry_type=LedgerEntry.EntryType.CREDIT,
                amount_paise=amount,
                description=desc,
                created_at=timezone.now() - timedelta(days=days_ago),
            )

        self.stdout.write(self.style.SUCCESS(
            f"  [OK] {m3.name} - Rs.{sum(c[0] for c in credits_m3)/100:,.2f} in credits"
        ))

        self.stdout.write(self.style.SUCCESS("\n[DONE] Seeding complete!"))
        self.stdout.write(self.style.NOTICE(
            f"\nMerchant IDs for testing:\n"
            f"  1. {m1.name}: {m1.id}\n"
            f"  2. {m2.name}: {m2.id}\n"
            f"  3. {m3.name}: {m3.id}\n"
        ))
