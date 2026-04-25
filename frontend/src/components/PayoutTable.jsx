import { formatPaise, formatDate, getStatusColor, formatRelativeTime } from '../utils';

/**
 * Payout history table with live status indicators.
 */
export default function PayoutTable({ payouts }) {
  if (!payouts || payouts.length === 0) {
    return (
      <div className="rounded-2xl bg-surface-800/40 border border-surface-700/50 backdrop-blur-sm p-8">
        <div className="text-center">
          <svg className="w-12 h-12 mx-auto text-surface-600 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1">
            <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 18.75a60.07 60.07 0 0115.797 2.101c.727.198 1.453-.342 1.453-1.096V18.75M3.75 4.5v.75A.75.75 0 013 6h-.75m0 0v-.375c0-.621.504-1.125 1.125-1.125H20.25M2.25 6v9m18-10.5v.75c0 .414.336.75.75.75h.75m-1.5-1.5h.375c.621 0 1.125.504 1.125 1.125v9.75c0 .621-.504 1.125-1.125 1.125h-.375m1.5-1.5H21a.75.75 0 00-.75.75v.75m0 0H3.75m0 0h-.375a1.125 1.125 0 01-1.125-1.125V15m1.5 1.5v-.75A.75.75 0 003 15h-.75M15 10.5a3 3 0 11-6 0 3 3 0 016 0zm3 0h.008v.008H18V10.5zm-12 0h.008v.008H6V10.5z" />
          </svg>
          <p className="text-surface-400 text-sm">No payouts yet</p>
          <p className="text-surface-500 text-xs mt-1">Request your first payout using the form above</p>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-2xl bg-surface-800/40 border border-surface-700/50 backdrop-blur-sm overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-surface-700/50">
              <th className="text-left text-xs font-semibold text-surface-400 uppercase tracking-wider px-6 py-4">Amount</th>
              <th className="text-left text-xs font-semibold text-surface-400 uppercase tracking-wider px-6 py-4">Status</th>
              <th className="text-left text-xs font-semibold text-surface-400 uppercase tracking-wider px-6 py-4">Bank Account</th>
              <th className="text-left text-xs font-semibold text-surface-400 uppercase tracking-wider px-6 py-4">Attempts</th>
              <th className="text-left text-xs font-semibold text-surface-400 uppercase tracking-wider px-6 py-4">Created</th>
              <th className="text-left text-xs font-semibold text-surface-400 uppercase tracking-wider px-6 py-4">Payout ID</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-surface-700/30">
            {payouts.map((payout, index) => {
              const statusStyle = getStatusColor(payout.status);
              const isProcessing = payout.status === 'processing';
              return (
                <tr
                  key={payout.id}
                  className="hover:bg-surface-700/20 transition-colors duration-150 animate-fade-in-up"
                  style={{ animationDelay: `${index * 40}ms` }}
                >
                  <td className="px-6 py-4">
                    <span className="text-sm font-semibold text-surface-100">
                      {formatPaise(payout.amount_paise)}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium ${statusStyle.bg} ${statusStyle.text}`}>
                      <span className={`w-1.5 h-1.5 rounded-full ${statusStyle.dot} ${isProcessing ? 'animate-pulse' : ''}`} />
                      {payout.status.charAt(0).toUpperCase() + payout.status.slice(1)}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-sm text-surface-300">
                    {payout.bank_account_display || '—'}
                  </td>
                  <td className="px-6 py-4 text-sm text-surface-400">
                    {payout.attempts} / {payout.max_attempts}
                  </td>
                  <td className="px-6 py-4">
                    <span className="text-sm text-surface-400" title={formatDate(payout.created_at)}>
                      {formatRelativeTime(payout.created_at)}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <span className="text-xs font-mono text-surface-500">
                      {payout.id?.slice(0, 8)}...
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Footer with failure reasons */}
      {payouts.some(p => p.failure_reason) && (
        <div className="border-t border-surface-700/50 px-6 py-3 bg-danger-500/5">
          {payouts.filter(p => p.failure_reason).map(p => (
            <p key={p.id} className="text-xs text-danger-400/80">
              <span className="font-mono">{p.id?.slice(0, 8)}</span>: {p.failure_reason}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}
