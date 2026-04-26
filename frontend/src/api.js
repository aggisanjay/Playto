/**
 * API service for the Playto Payout Engine.
 * Handles all communication with the Django backend.
 */

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';
const API_BASE = `${BACKEND_URL}/api/v1`;

async function apiRequest(url, options = {}) {
  const { headers: customHeaders, ...restOptions } = options;
  const response = await fetch(`${API_BASE}${url}`, {
    ...restOptions,
    headers: {
      'Content-Type': 'application/json',
      ...customHeaders,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: 'Request failed' }));
    throw { status: response.status, ...error };
  }

  return response.json();
}

// ─── Merchants ───────────────────────────────────────────────

export async function fetchMerchants() {
  const data = await apiRequest('/merchants/');
  return data.results || data;
}

export async function fetchMerchant(merchantId) {
  return apiRequest(`/merchants/${merchantId}/`);
}

export async function fetchMerchantBalance(merchantId) {
  return apiRequest(`/merchants/${merchantId}/balance/`);
}

export async function fetchMerchantLedger(merchantId) {
  const data = await apiRequest(`/merchants/${merchantId}/ledger/`);
  return data.results || data;
}

export async function fetchBankAccounts(merchantId) {
  return apiRequest(`/merchants/${merchantId}/bank-accounts/`);
}

// ─── Payouts ─────────────────────────────────────────────────

export async function fetchPayouts(merchantId) {
  const data = await apiRequest(`/payouts/?merchant_id=${merchantId}`);
  return data.results || data;
}

export async function fetchPayout(payoutId) {
  return apiRequest(`/payouts/${payoutId}/`);
}

export async function createPayout(merchantId, amountPaise, bankAccountId, idempotencyKey) {
  return apiRequest('/payouts/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Idempotency-Key': idempotencyKey,
    },
    body: JSON.stringify({
      merchant_id: merchantId,
      amount_paise: amountPaise,
      bank_account_id: bankAccountId,
    }),
  });
}
