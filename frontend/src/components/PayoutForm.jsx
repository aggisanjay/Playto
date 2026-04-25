import { useState } from 'react';
import { createPayout } from '../api';
import { formatPaise, generateUUID } from '../utils';

/**
 * Form to request a payout.
 * Generates an idempotency key automatically for each submission.
 */
export default function PayoutForm({ merchantId, bankAccounts, availableBalance, onSuccess }) {
  const [amountRupees, setAmountRupees] = useState('');
  const [selectedAccount, setSelectedAccount] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  const amountPaise = Math.round(parseFloat(amountRupees || '0') * 100);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    if (!amountRupees || amountPaise <= 0) {
      setError('Please enter a valid amount');
      return;
    }

    if (amountPaise < 100) {
      setError('Minimum payout is ₹1.00');
      return;
    }

    if (!selectedAccount) {
      setError('Please select a bank account');
      return;
    }

    if (amountPaise > availableBalance) {
      setError(`Insufficient balance. Available: ${formatPaise(availableBalance)}`);
      return;
    }

    setLoading(true);

    try {
      const idempotencyKey = generateUUID();
      const payout = await createPayout(merchantId, amountPaise, selectedAccount, idempotencyKey);
      setSuccess(`Payout of ${formatPaise(payout.amount_paise)} created successfully!`);
      setAmountRupees('');
      onSuccess?.();
    } catch (err) {
      setError(err.error || 'Failed to create payout. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="rounded-2xl bg-surface-800/40 border border-surface-700/50 backdrop-blur-sm p-6">
      <h3 className="text-lg font-semibold text-surface-100 mb-1">Request Payout</h3>
      <p className="text-sm text-surface-400 mb-6">
        Withdraw funds to your bank account. Available: {formatPaise(availableBalance || 0)}
      </p>

      <form onSubmit={handleSubmit} className="space-y-5">
        {/* Amount input */}
        <div>
          <label htmlFor="payout-amount" className="block text-sm font-medium text-surface-300 mb-2">
            Amount (₹)
          </label>
          <div className="relative">
            <span className="absolute left-4 top-1/2 -translate-y-1/2 text-surface-400 font-medium">₹</span>
            <input
              id="payout-amount"
              type="number"
              step="0.01"
              min="1"
              value={amountRupees}
              onChange={(e) => setAmountRupees(e.target.value)}
              placeholder="0.00"
              className="
                w-full pl-10 pr-4 py-3 rounded-xl
                bg-surface-900/60 border border-surface-600/50
                text-surface-100 placeholder:text-surface-500
                focus:outline-none focus:ring-2 focus:ring-primary-500/50 focus:border-primary-500/50
                transition-all duration-200
                text-lg font-mono
              "
            />
          </div>
          {amountPaise > 0 && (
            <p className="text-xs text-surface-500 mt-1.5 font-mono">
              = {amountPaise.toLocaleString()} paise
            </p>
          )}
        </div>

        {/* Bank account select */}
        <div>
          <label htmlFor="bank-account" className="block text-sm font-medium text-surface-300 mb-2">
            Bank Account
          </label>
          <select
            id="bank-account"
            value={selectedAccount}
            onChange={(e) => setSelectedAccount(e.target.value)}
            className="
              w-full px-4 py-3 rounded-xl
              bg-surface-900/60 border border-surface-600/50
              text-surface-100
              focus:outline-none focus:ring-2 focus:ring-primary-500/50 focus:border-primary-500/50
              transition-all duration-200
              appearance-none cursor-pointer
            "
          >
            <option value="" className="bg-surface-900">Select a bank account</option>
            {bankAccounts?.map((account) => (
              <option key={account.id} value={account.id} className="bg-surface-900">
                {account.bank_name} — ****{account.account_number.slice(-4)} ({account.ifsc_code})
              </option>
            ))}
          </select>
        </div>

        {/* Error message */}
        {error && (
          <div className="flex items-center gap-2 px-4 py-3 rounded-xl bg-danger-500/10 border border-danger-500/20">
            <svg className="w-5 h-5 text-danger-400 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
            </svg>
            <p className="text-sm text-danger-400">{error}</p>
          </div>
        )}

        {/* Success message */}
        {success && (
          <div className="flex items-center gap-2 px-4 py-3 rounded-xl bg-success-500/10 border border-success-500/20">
            <svg className="w-5 h-5 text-success-400 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <p className="text-sm text-success-400">{success}</p>
          </div>
        )}

        {/* Submit button */}
        <button
          type="submit"
          disabled={loading || !amountRupees || !selectedAccount}
          className="
            w-full py-3.5 px-6 rounded-xl
            bg-gradient-to-r from-primary-600 to-primary-500
            hover:from-primary-500 hover:to-primary-400
            disabled:from-surface-700 disabled:to-surface-600 disabled:cursor-not-allowed
            text-white font-semibold text-sm
            transition-all duration-200
            shadow-lg shadow-primary-500/20
            hover:shadow-xl hover:shadow-primary-500/30
            active:scale-[0.98]
            flex items-center justify-center gap-2
          "
        >
          {loading ? (
            <>
              <svg className="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              Processing...
            </>
          ) : (
            <>
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5" />
              </svg>
              Request Payout
            </>
          )}
        </button>
      </form>
    </div>
  );
}
