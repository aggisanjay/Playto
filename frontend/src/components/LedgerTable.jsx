import { formatPaise, formatRelativeTime, getLedgerTypeStyle } from '../utils';

/**
 * Ledger entries table showing credits, debits, holds, and releases.
 */
export default function LedgerTable({ entries }) {
  if (!entries || entries.length === 0) {
    return (
      <div className="rounded-2xl bg-surface-800/40 border border-surface-700/50 backdrop-blur-sm p-8">
        <div className="text-center">
          <svg className="w-12 h-12 mx-auto text-surface-600 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1">
            <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
          </svg>
          <p className="text-surface-400 text-sm">No ledger entries</p>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-2xl bg-surface-800/40 border border-surface-700/50 backdrop-blur-sm overflow-hidden">
      <div className="divide-y divide-surface-700/30 max-h-96 overflow-y-auto">
        {entries.map((entry, index) => {
          const style = getLedgerTypeStyle(entry.entry_type);
          return (
            <div
              key={entry.id}
              className="flex items-center justify-between px-6 py-4 hover:bg-surface-700/20 transition-colors duration-150 animate-fade-in-up"
              style={{ animationDelay: `${index * 30}ms` }}
            >
              <div className="flex items-center gap-4 min-w-0">
                {/* Type icon */}
                <div className={`flex-shrink-0 w-10 h-10 rounded-xl bg-surface-700/50 flex items-center justify-center text-lg ${style.color}`}>
                  {style.icon}
                </div>
                {/* Details */}
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className={`text-xs font-semibold uppercase tracking-wider ${style.color}`}>
                      {style.label}
                    </span>
                  </div>
                  <p className="text-sm text-surface-300 truncate max-w-md mt-0.5">
                    {entry.description || 'No description'}
                  </p>
                </div>
              </div>

              {/* Amount & time */}
              <div className="text-right flex-shrink-0 ml-4">
                <div className={`text-sm font-semibold ${style.color}`}>
                  {style.sign}{formatPaise(entry.amount_paise)}
                </div>
                <div className="text-xs text-surface-500 mt-0.5">
                  {formatRelativeTime(entry.created_at)}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
