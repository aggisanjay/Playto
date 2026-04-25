import { useDashboard } from './hooks/useDashboard';
import MerchantSelector from './components/MerchantSelector';
import BalanceCards from './components/BalanceCards';
import PayoutForm from './components/PayoutForm';
import PayoutTable from './components/PayoutTable';
import LedgerTable from './components/LedgerTable';
import './index.css';

/**
 * Main Playto Payout Engine Dashboard.
 */
export default function App() {
  const {
    merchants,
    selectedMerchant,
    setSelectedMerchant,
    balance,
    ledger,
    payouts,
    bankAccounts,
    loading,
    error,
    refreshData,
  } = useDashboard();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="w-12 h-12 border-2 border-primary-500/30 border-t-primary-500 rounded-full animate-spin mx-auto mb-4" />
          <p className="text-surface-400 text-sm">Loading Playto Pay...</p>
        </div>
      </div>
    );
  }

  if (error && merchants.length === 0) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center max-w-md mx-auto px-6">
          <div className="w-16 h-16 rounded-2xl bg-danger-500/10 flex items-center justify-center mx-auto mb-4">
            <svg className="w-8 h-8 text-danger-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
            </svg>
          </div>
          <h2 className="text-xl font-semibold text-surface-100 mb-2">Connection Error</h2>
          <p className="text-surface-400 text-sm mb-6">{error}</p>
          <p className="text-surface-500 text-xs">
            Make sure the Django backend is running on <code className="text-primary-400">localhost:8000</code>
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      {/* ─── Header ─────────────────────────────────────── */}
      <header className="sticky top-0 z-50 border-b border-surface-700/50 bg-surface-950/80 backdrop-blur-xl">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            {/* Logo */}
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-primary-500 to-primary-700 flex items-center justify-center shadow-lg shadow-primary-500/20">
                <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v12m-3-2.818l.879.659c1.171.879 3.07.879 4.242 0 1.172-.879 1.172-2.303 0-3.182C13.536 12.219 12.768 12 12 12c-.725 0-1.45-.22-2.003-.659-1.106-.879-1.106-2.303 0-3.182s2.9-.879 4.006 0l.415.33M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <div>
                <h1 className="text-lg font-bold text-surface-50 tracking-tight">Playto Pay</h1>
                <p className="text-xs text-surface-500 -mt-0.5">Payout Engine</p>
              </div>
            </div>
          </div>

          {/* Merchant Selector */}
          <MerchantSelector
            merchants={merchants}
            selected={selectedMerchant}
            onSelect={setSelectedMerchant}
          />
        </div>
      </header>

      {/* ─── Main Content ───────────────────────────────── */}
      <main className="max-w-7xl mx-auto px-6 py-8 space-y-8">
        {/* Balance Cards */}
        <section className="animate-fade-in-up">
          <BalanceCards balance={balance} />
        </section>

        {/* Payout Form + Recent Payouts (2-column) */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Payout Form */}
          <section className="lg:col-span-1 animate-fade-in-up" style={{ animationDelay: '100ms' }}>
            <PayoutForm
              merchantId={selectedMerchant?.id}
              bankAccounts={bankAccounts}
              availableBalance={balance?.available_balance_paise || 0}
              onSuccess={() => refreshData(selectedMerchant?.id)}
            />
          </section>

          {/* Payout History */}
          <section className="lg:col-span-2 animate-fade-in-up" style={{ animationDelay: '200ms' }}>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-surface-100">Payout History</h2>
              <div className="flex items-center gap-2 text-xs text-surface-500">
                <span className="w-2 h-2 rounded-full bg-success-400 animate-pulse" />
                Live updates
              </div>
            </div>
            <PayoutTable payouts={payouts} />
          </section>
        </div>

        {/* Ledger */}
        <section className="animate-fade-in-up" style={{ animationDelay: '300ms' }}>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-surface-100">Ledger History</h2>
            <span className="text-xs text-surface-500 font-mono">
              {ledger.length} entries
            </span>
          </div>
          <LedgerTable entries={ledger} />
        </section>
      </main>

      {/* ─── Footer ─────────────────────────────────────── */}
      <footer className="border-t border-surface-800/50 mt-12">
        <div className="max-w-7xl mx-auto px-6 py-6 flex items-center justify-between">
          <p className="text-xs text-surface-600">
            Playto Payout Engine • Built for the Founding Engineer Challenge
          </p>
          <p className="text-xs text-surface-600">
            All amounts in INR (paise precision)
          </p>
        </div>
      </footer>
    </div>
  );
}
