"""
URL configuration for the payouts API.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from payouts.views import MerchantViewSet, PayoutViewSet, seed_data

router = DefaultRouter()
router.register(r"merchants", MerchantViewSet, basename="merchant")
router.register(r"payouts", PayoutViewSet, basename="payout")

urlpatterns = [
    path("", include(router.urls)),
    path("seed/", seed_data, name="seed-data"),
]
