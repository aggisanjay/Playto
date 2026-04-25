"""
DRF serializers for the Playto Payout Engine.
"""
from rest_framework import serializers
from payouts.models import Merchant, BankAccount, LedgerEntry, Payout


class BankAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankAccount
        fields = [
            "id", "account_holder_name", "account_number",
            "ifsc_code", "bank_name", "is_primary", "created_at"
        ]


class LedgerEntrySerializer(serializers.ModelSerializer):
    amount_rupees = serializers.SerializerMethodField()

    class Meta:
        model = LedgerEntry
        fields = [
            "id", "entry_type", "amount_paise", "amount_rupees",
            "description", "reference_id", "created_at"
        ]

    def get_amount_rupees(self, obj):
        return f"{obj.amount_paise / 100:.2f}"


class MerchantSerializer(serializers.ModelSerializer):
    bank_accounts = BankAccountSerializer(many=True, read_only=True)

    class Meta:
        model = Merchant
        fields = ["id", "name", "email", "bank_accounts", "created_at", "updated_at"]


class MerchantBalanceSerializer(serializers.Serializer):
    """Serializer for the computed balance (not a model)."""
    available_balance_paise = serializers.IntegerField()
    held_balance_paise = serializers.IntegerField()
    total_credits_paise = serializers.IntegerField()
    total_debits_paise = serializers.IntegerField()
    available_balance_rupees = serializers.SerializerMethodField()
    held_balance_rupees = serializers.SerializerMethodField()

    def get_available_balance_rupees(self, obj):
        return f"{obj['available_balance_paise'] / 100:.2f}"

    def get_held_balance_rupees(self, obj):
        return f"{obj['held_balance_paise'] / 100:.2f}"


class PayoutSerializer(serializers.ModelSerializer):
    amount_rupees = serializers.SerializerMethodField()
    bank_account_display = serializers.SerializerMethodField()

    class Meta:
        model = Payout
        fields = [
            "id", "merchant_id", "bank_account_id", "amount_paise",
            "amount_rupees", "status", "idempotency_key", "attempts",
            "max_attempts", "last_attempted_at", "completed_at",
            "failure_reason", "bank_account_display", "created_at", "updated_at"
        ]

    def get_amount_rupees(self, obj):
        return f"{obj.amount_paise / 100:.2f}"

    def get_bank_account_display(self, obj):
        return f"{obj.bank_account.bank_name} - ****{obj.bank_account.account_number[-4:]}"


class CreatePayoutSerializer(serializers.Serializer):
    """Serializer for payout creation request body."""
    amount_paise = serializers.IntegerField(min_value=100, help_text="Amount in paise, min Rs.1")
    bank_account_id = serializers.UUIDField(help_text="UUID of the bank account")
