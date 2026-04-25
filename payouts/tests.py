"""
Tests for the Playto Payout Engine.

Two critical tests as required:
1. Concurrency test: Two simultaneous ₹60 payouts on ₹100 balance — exactly one succeeds.
2. Idempotency test: Duplicate idempotency key returns same response, no duplicate payout.

Plus additional tests for state machine and balance integrity.
"""
import uuid
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import patch

from django.test import TestCase, TransactionTestCase
from django.db import connection
from rest_framework.test import APIClient

from payouts.models import Merchant, BankAccount, LedgerEntry, Payout, IdempotencyKey
from payouts.services import get_merchant_balance, create_ledger_entry
from payouts.services.payout_service import (
    create_payout,
    InsufficientBalanceError,
    DuplicateIdempotencyKeyError,
)


class LedgerBalanceTest(TestCase):
    """Tests that balance calculations are correct and DB-level."""

    def setUp(self):
        self.merchant = Merchant.objects.create(
            name="Test Merchant", email="test@example.com"
        )
        self.bank_account = BankAccount.objects.create(
            merchant=self.merchant,
            account_holder_name="Test Account",
            account_number="1234567890",
            ifsc_code="TEST0001234",
            bank_name="Test Bank",
            is_primary=True,
        )

    def test_balance_from_credits(self):
        """Balance should equal sum of credits when no debits."""
        create_ledger_entry(self.merchant.id, "credit", 10000, "Payment 1")
        create_ledger_entry(self.merchant.id, "credit", 5000, "Payment 2")

        balance = get_merchant_balance(self.merchant.id)
        self.assertEqual(balance["available_balance_paise"], 15000)  # ₹150
        self.assertEqual(balance["total_credits_paise"], 15000)
        self.assertEqual(balance["total_debits_paise"], 0)

    def test_balance_with_hold(self):
        """Hold should reduce available balance."""
        create_ledger_entry(self.merchant.id, "credit", 10000)
        create_ledger_entry(self.merchant.id, "hold", 3000)

        balance = get_merchant_balance(self.merchant.id)
        self.assertEqual(balance["available_balance_paise"], 7000)  # ₹70
        self.assertEqual(balance["held_balance_paise"], 3000)  # ₹30 held

    def test_balance_after_release(self):
        """Release should return held funds to available balance."""
        create_ledger_entry(self.merchant.id, "credit", 10000)
        create_ledger_entry(self.merchant.id, "hold", 3000)
        create_ledger_entry(self.merchant.id, "release", 3000)

        balance = get_merchant_balance(self.merchant.id)
        self.assertEqual(balance["available_balance_paise"], 10000)  # ₹100 restored
        self.assertEqual(balance["held_balance_paise"], 0)

    def test_balance_invariant(self):
        """Sum of credits - debits must always equal displayed balance + held."""
        create_ledger_entry(self.merchant.id, "credit", 50000)
        create_ledger_entry(self.merchant.id, "credit", 30000)
        create_ledger_entry(self.merchant.id, "hold", 10000)
        create_ledger_entry(self.merchant.id, "debit", 5000)

        balance = get_merchant_balance(self.merchant.id)
        # Invariant: credits - debits = available + held
        credits = balance["total_credits_paise"]
        debits = balance["total_debits_paise"]
        available = balance["available_balance_paise"]
        held = balance["held_balance_paise"]

        self.assertEqual(credits - debits, available + held)


class ConcurrencyTest(TransactionTestCase):
    """
    CRITICAL TEST: Two simultaneous ₹60 payouts on ₹100 balance.

    Uses TransactionTestCase because we need real database transactions
    (not wrapped in a test transaction) to properly test SELECT FOR UPDATE.

    Expected result: Exactly one payout succeeds, the other is rejected
    with InsufficientBalanceError.
    """

    def setUp(self):
        self.merchant = Merchant.objects.create(
            name="Concurrency Test Merchant", email="concurrent@test.com"
        )
        self.bank_account = BankAccount.objects.create(
            merchant=self.merchant,
            account_holder_name="Test Account",
            account_number="9999888877776666",
            ifsc_code="TEST0001234",
            bank_name="Test Bank",
            is_primary=True,
        )
        # Seed ₹100 balance (10000 paise)
        create_ledger_entry(self.merchant.id, "credit", 10000, "Seed credit")

    @patch("payouts.services.payout_service.create_payout.__module__")
    def test_concurrent_payouts_one_succeeds(self):
        """
        Two threads simultaneously submit ₹60 payouts.
        Exactly one should succeed, the other should fail.

        This test verifies that SELECT FOR UPDATE properly serializes
        the balance check, preventing both payouts from seeing ₹100
        and both deducting ₹60 (which would overdraw to -₹20).
        """
        results = {"successes": 0, "failures": 0, "errors": []}
        barrier = threading.Barrier(2, timeout=10)

        def submit_payout(key):
            try:
                # Use a new DB connection for each thread
                from django.db import connections
                connections.close_all()

                barrier.wait()  # Synchronize both threads to fire at the same time
                # Patch to prevent Celery task dispatch during test
                with patch("payouts.services.payout_service.process_payout") as mock_task:
                    mock_task.delay = lambda x: None
                    payout, created = create_payout(
                        merchant_id=self.merchant.id,
                        amount_paise=6000,  # ₹60
                        bank_account_id=self.bank_account.id,
                        idempotency_key=key,
                    )
                    if created:
                        results["successes"] += 1
            except InsufficientBalanceError:
                results["failures"] += 1
            except Exception as e:
                results["errors"].append(str(e))

        key1 = str(uuid.uuid4())
        key2 = str(uuid.uuid4())

        t1 = threading.Thread(target=submit_payout, args=(key1,))
        t2 = threading.Thread(target=submit_payout, args=(key2,))

        t1.start()
        t2.start()
        t1.join(timeout=15)
        t2.join(timeout=15)

        # Exactly one should succeed, one should fail
        self.assertEqual(
            results["successes"], 1,
            f"Expected exactly 1 success, got {results['successes']}. "
            f"Errors: {results['errors']}"
        )
        self.assertEqual(
            results["failures"], 1,
            f"Expected exactly 1 failure, got {results['failures']}. "
            f"Errors: {results['errors']}"
        )

        # Verify balance integrity
        balance = get_merchant_balance(self.merchant.id)
        self.assertEqual(
            balance["available_balance_paise"], 4000,  # ₹100 - ₹60 = ₹40
            "Balance should be ₹40 (₹100 - ₹60 hold)"
        )
        self.assertEqual(
            balance["held_balance_paise"], 6000,  # ₹60 held
            "Held balance should be ₹60"
        )


class IdempotencyTest(TransactionTestCase):
    """
    CRITICAL TEST: Duplicate idempotency key returns same response.

    No duplicate payout should be created. Keys are scoped per merchant.
    """

    def setUp(self):
        self.merchant = Merchant.objects.create(
            name="Idempotency Test Merchant", email="idempotent@test.com"
        )
        self.bank_account = BankAccount.objects.create(
            merchant=self.merchant,
            account_holder_name="Test Account",
            account_number="1111222233334444",
            ifsc_code="TEST0001234",
            bank_name="Test Bank",
            is_primary=True,
        )
        create_ledger_entry(self.merchant.id, "credit", 50000, "Seed credit")

    @patch("payouts.services.payout_service.process_payout")
    def test_duplicate_key_returns_same_response(self, mock_task):
        """Second call with same key returns the same payout, not a new one."""
        mock_task.delay = lambda x: None
        idempotency_key = str(uuid.uuid4())

        # First request
        payout1, created1 = create_payout(
            merchant_id=self.merchant.id,
            amount_paise=5000,
            bank_account_id=self.bank_account.id,
            idempotency_key=idempotency_key,
        )
        self.assertTrue(created1, "First request should create a new payout")

        # Second request with same key
        payout2, created2 = create_payout(
            merchant_id=self.merchant.id,
            amount_paise=5000,
            bank_account_id=self.bank_account.id,
            idempotency_key=idempotency_key,
        )
        self.assertFalse(created2, "Second request should NOT create a new payout")
        self.assertEqual(payout1.id, payout2.id, "Should return the same payout")

        # Verify only one payout exists
        payout_count = Payout.objects.filter(
            merchant=self.merchant,
            idempotency_key=idempotency_key,
        ).count()
        self.assertEqual(payout_count, 1, "Only one payout should exist")

    @patch("payouts.services.payout_service.process_payout")
    def test_same_key_different_merchants(self, mock_task):
        """Same idempotency key for different merchants should create separate payouts."""
        mock_task.delay = lambda x: None

        merchant2 = Merchant.objects.create(
            name="Other Merchant", email="other@test.com"
        )
        ba2 = BankAccount.objects.create(
            merchant=merchant2,
            account_holder_name="Other Account",
            account_number="5555666677778888",
            ifsc_code="TEST0005678",
            bank_name="Other Bank",
            is_primary=True,
        )
        create_ledger_entry(merchant2.id, "credit", 50000, "Seed credit")

        same_key = str(uuid.uuid4())

        payout1, _ = create_payout(
            merchant_id=self.merchant.id,
            amount_paise=1000,
            bank_account_id=self.bank_account.id,
            idempotency_key=same_key,
        )

        payout2, _ = create_payout(
            merchant_id=merchant2.id,
            amount_paise=1000,
            bank_account_id=ba2.id,
            idempotency_key=same_key,
        )

        self.assertNotEqual(payout1.id, payout2.id, "Different merchants should get different payouts")


class StateMachineTest(TestCase):
    """Tests that the payout state machine enforces legal transitions."""

    def setUp(self):
        self.merchant = Merchant.objects.create(
            name="State Machine Test", email="state@test.com"
        )
        self.bank_account = BankAccount.objects.create(
            merchant=self.merchant,
            account_holder_name="Test",
            account_number="1234567890",
            ifsc_code="TEST0001234",
            bank_name="Test Bank",
        )

    def test_legal_transitions(self):
        """pending → processing → completed should work."""
        payout = Payout.objects.create(
            merchant=self.merchant,
            bank_account=self.bank_account,
            amount_paise=1000,
            status=Payout.Status.PENDING,
            idempotency_key=str(uuid.uuid4()),
        )

        payout.transition_to(Payout.Status.PROCESSING)
        self.assertEqual(payout.status, Payout.Status.PROCESSING)

        payout.transition_to(Payout.Status.COMPLETED)
        self.assertEqual(payout.status, Payout.Status.COMPLETED)

    def test_completed_to_pending_blocked(self):
        """completed → pending must be rejected."""
        payout = Payout.objects.create(
            merchant=self.merchant,
            bank_account=self.bank_account,
            amount_paise=1000,
            status=Payout.Status.COMPLETED,
            idempotency_key=str(uuid.uuid4()),
        )

        with self.assertRaises(ValueError) as ctx:
            payout.transition_to(Payout.Status.PENDING)

        self.assertIn("Illegal state transition", str(ctx.exception))

    def test_failed_to_completed_blocked(self):
        """failed → completed must be rejected."""
        payout = Payout.objects.create(
            merchant=self.merchant,
            bank_account=self.bank_account,
            amount_paise=1000,
            status=Payout.Status.FAILED,
            idempotency_key=str(uuid.uuid4()),
        )

        with self.assertRaises(ValueError) as ctx:
            payout.transition_to(Payout.Status.COMPLETED)

        self.assertIn("Illegal state transition", str(ctx.exception))

    def test_processing_to_pending_blocked(self):
        """processing → pending (backward) must be rejected."""
        payout = Payout.objects.create(
            merchant=self.merchant,
            bank_account=self.bank_account,
            amount_paise=1000,
            status=Payout.Status.PROCESSING,
            idempotency_key=str(uuid.uuid4()),
        )

        with self.assertRaises(ValueError) as ctx:
            payout.transition_to(Payout.Status.PENDING)

        self.assertIn("Illegal state transition", str(ctx.exception))


class APIEndpointTest(TransactionTestCase):
    """Tests for the REST API endpoints."""

    def setUp(self):
        self.client = APIClient()
        self.merchant = Merchant.objects.create(
            name="API Test Merchant", email="api@test.com"
        )
        self.bank_account = BankAccount.objects.create(
            merchant=self.merchant,
            account_holder_name="API Test",
            account_number="1234567890",
            ifsc_code="TEST0001234",
            bank_name="Test Bank",
            is_primary=True,
        )
        create_ledger_entry(self.merchant.id, "credit", 100000, "Seed")

    def test_merchant_balance_endpoint(self):
        """GET /api/v1/merchants/{id}/balance/ should return correct balance."""
        response = self.client.get(f"/api/v1/merchants/{self.merchant.id}/balance/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["available_balance_paise"], 100000)

    @patch("payouts.services.payout_service.process_payout")
    def test_create_payout_requires_idempotency_key(self, mock_task):
        """POST without Idempotency-Key header should return 400."""
        mock_task.delay = lambda x: None
        response = self.client.post(
            "/api/v1/payouts/",
            data={
                "merchant_id": str(self.merchant.id),
                "amount_paise": 5000,
                "bank_account_id": str(self.bank_account.id),
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Idempotency-Key", response.data.get("error", ""))

    @patch("payouts.services.payout_service.process_payout")
    def test_create_payout_success(self, mock_task):
        """POST with valid data should create a payout."""
        mock_task.delay = lambda x: None
        response = self.client.post(
            "/api/v1/payouts/",
            data={
                "merchant_id": str(self.merchant.id),
                "amount_paise": 5000,
                "bank_account_id": str(self.bank_account.id),
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["amount_paise"], 5000)
        self.assertEqual(response.data["status"], "pending")
