"""
API views for the Playto Payout Engine.

Endpoints:
- GET  /api/v1/merchants/                  — list merchants
- GET  /api/v1/merchants/{id}/             — merchant detail with balance
- GET  /api/v1/merchants/{id}/ledger/      — ledger entries for merchant
- GET  /api/v1/merchants/{id}/bank-accounts/ — bank accounts for merchant
- POST /api/v1/payouts/                    — create payout (idempotency key required)
- GET  /api/v1/payouts/?merchant_id={id}   — list payouts for merchant
- GET  /api/v1/payouts/{id}/               — payout detail
"""
import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from rest_framework.views import APIView

from payouts.models import Merchant, BankAccount, LedgerEntry, Payout
from payouts.serializers import (
    MerchantSerializer, MerchantBalanceSerializer, BankAccountSerializer,
    LedgerEntrySerializer, PayoutSerializer, CreatePayoutSerializer,
)
from payouts.services import get_merchant_balance
from payouts.services.payout_service import (
    create_payout,
    finalize_idempotency_key,
    InsufficientBalanceError,
    InvalidBankAccountError,
    DuplicateIdempotencyKeyError,
)


logger = logging.getLogger(__name__)


class MerchantViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for merchants — read-only since merchants are seeded.
    """
    queryset = Merchant.objects.all()
    serializer_class = MerchantSerializer

    @action(detail=True, methods=["get"])
    def balance(self, request, pk=None):
        """GET /api/v1/merchants/{id}/balance/ — computed balance"""
        merchant = self.get_object()
        balance_info = get_merchant_balance(merchant.id)
        serializer = MerchantBalanceSerializer(balance_info)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def ledger(self, request, pk=None):
        """GET /api/v1/merchants/{id}/ledger/ — paginated ledger entries"""
        merchant = self.get_object()
        entries = LedgerEntry.objects.filter(merchant=merchant)

        # Optional filtering by entry_type
        entry_type = request.query_params.get("entry_type")
        if entry_type:
            entries = entries.filter(entry_type=entry_type)

        page = self.paginate_queryset(entries)
        if page is not None:
            serializer = LedgerEntrySerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = LedgerEntrySerializer(entries, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"], url_path="bank-accounts")
    def bank_accounts(self, request, pk=None):
        """GET /api/v1/merchants/{id}/bank-accounts/"""
        merchant = self.get_object()
        accounts = BankAccount.objects.filter(merchant=merchant)
        serializer = BankAccountSerializer(accounts, many=True)
        return Response(serializer.data)


class PayoutViewSet(viewsets.ViewSet):
    """
    ViewSet for payouts.

    POST /api/v1/payouts/ — create payout with idempotency key
    GET  /api/v1/payouts/ — list payouts (filtered by merchant_id)
    GET  /api/v1/payouts/{id}/ — payout detail
    """

    def list(self, request):
        """List payouts filtered by merchant_id."""
        merchant_id = request.query_params.get("merchant_id")
        if not merchant_id:
            return Response(
                {"error": "merchant_id query parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payouts = Payout.objects.filter(merchant_id=merchant_id)

        # Optional status filter
        payout_status = request.query_params.get("status")
        if payout_status:
            payouts = payouts.filter(status=payout_status)

        serializer = PayoutSerializer(payouts, many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        """Get a single payout by ID."""
        try:
            payout = Payout.objects.get(id=pk)
            serializer = PayoutSerializer(payout)
            return Response(serializer.data)
        except Payout.DoesNotExist:
            return Response(
                {"error": "Payout not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

    def create(self, request):
        try:
            return self._create(request)
        except Exception as e:
            logger.exception(f"Unhandled error in PayoutViewSet.create: {e}")
            return Response(
                {"error": "Internal server error. Check logs for details."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _create(self, request):
        """
        Inner create method with the actual logic.
        """
        # --- Validate idempotency key header ---
        idempotency_key = request.headers.get("Idempotency-Key")
        if not idempotency_key:
            return Response(
                {"error": "Idempotency-Key header is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # --- Validate merchant_id ---
        merchant_id = request.data.get("merchant_id") or request.query_params.get("merchant_id")
        if not merchant_id:
            return Response(
                {"error": "merchant_id is required (in body or query param)"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Verify merchant exists
        try:
            Merchant.objects.get(id=merchant_id)
        except Merchant.DoesNotExist:
            return Response(
                {"error": f"Merchant {merchant_id} not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # --- Validate request body ---
        serializer = CreatePayoutSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        amount_paise = serializer.validated_data["amount_paise"]
        bank_account_id = serializer.validated_data["bank_account_id"]

        # --- Create the payout ---
        try:
            payout, created = create_payout(
                merchant_id=merchant_id,
                amount_paise=amount_paise,
                bank_account_id=bank_account_id,
                idempotency_key=idempotency_key,
            )
        except InsufficientBalanceError as e:
            return Response(
                {"error": str(e), "code": "INSUFFICIENT_BALANCE"},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        except InvalidBankAccountError as e:
            return Response(
                {"error": str(e), "code": "INVALID_BANK_ACCOUNT"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DuplicateIdempotencyKeyError as e:
            return Response(
                {"error": str(e), "code": "IDEMPOTENCY_CONFLICT"},
                status=status.HTTP_409_CONFLICT,
            )
        except ValueError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        response_serializer = PayoutSerializer(payout)
        response_data = response_serializer.data
        response_status = status.HTTP_201_CREATED if created else status.HTTP_200_OK

        # Finalize idempotency key with cached response
        if created:
            finalize_idempotency_key(
                merchant_id=merchant_id,
                idempotency_key=idempotency_key,
                status_code=response_status,
                response_body=response_data,
            )

        return Response(response_data, status=response_status)


@api_view(['GET'])
def seed_data(request):
    """Temporary endpoint to seed data since console is unavailable."""
    merchant, created = Merchant.objects.get_or_create(
        name='Playto Test Merchant',
        defaults={'email': 'merchant@playto.com'}
    )
    
    BankAccount.objects.get_or_create(
        merchant=merchant,
        account_number='1234567890',
        defaults={
            'account_holder_name': 'Playto Test User',
            'ifsc_code': 'PLAY0001234',
            'is_active': True
        }
    )
    
    # Add some initial balance
    LedgerEntry.objects.create(
        merchant=merchant,
        amount_paise=1000000, # 10,000 INR
        entry_type='CREDIT',
        description='Initial Seeding'
    )
    
    return Response({"message": "Data Seeded Successfully!", "merchant_id": merchant.id})
