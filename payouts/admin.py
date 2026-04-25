"""
Django admin configuration for the Playto Payout Engine.
"""
from django.contrib import admin
from payouts.models import Merchant, BankAccount, LedgerEntry, Payout, IdempotencyKey


@admin.register(Merchant)
class MerchantAdmin(admin.ModelAdmin):
    list_display = ["name", "email", "created_at"]
    search_fields = ["name", "email"]
    readonly_fields = ["id", "created_at", "updated_at"]


@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    list_display = ["merchant", "bank_name", "account_number", "ifsc_code", "is_primary"]
    list_filter = ["bank_name", "is_primary"]
    search_fields = ["account_number", "merchant__name"]


@admin.register(LedgerEntry)
class LedgerEntryAdmin(admin.ModelAdmin):
    list_display = ["merchant", "entry_type", "amount_paise", "description", "created_at"]
    list_filter = ["entry_type", "merchant"]
    search_fields = ["description", "merchant__name"]
    readonly_fields = ["id", "created_at"]


@admin.register(Payout)
class PayoutAdmin(admin.ModelAdmin):
    list_display = ["id", "merchant", "amount_paise", "status", "attempts", "created_at"]
    list_filter = ["status", "merchant"]
    search_fields = ["idempotency_key", "merchant__name"]
    readonly_fields = ["id", "created_at", "updated_at"]


@admin.register(IdempotencyKey)
class IdempotencyKeyAdmin(admin.ModelAdmin):
    list_display = ["key", "merchant", "is_processing", "created_at"]
    list_filter = ["is_processing"]
    readonly_fields = ["id", "created_at"]
