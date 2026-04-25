import { formatPaise } from '../utils';

/**
 * Balance cards showing available balance, held balance, and totals.
 * Uses glassmorphism with gradient accents.
 */
export default function BalanceCards({ balance }) {
  if (!balance) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="rounded-2xl bg-surface-800/50 border border-surface-700/50 p-6 animate-shimmer h-32" />
        ))}
      </div>
    );
  }

  const cards = [
    {
      label: 'Available Balance',
      value: balance.available_balance_paise,
      icon: (
        <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
          <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 18.75a60.07 60.07 0 0115.797 2.101c.727.198 1.453-.342 1.453-1.096V18.75M3.75 4.5v.75A.75.75 0 013 6h-.75m0 0v-.375c0-.621.504-1.125 1.125-1.125H20.25M2.25 6v9m18-10.5v.75c0 .414.336.75.75.75h.75m-1.5-1.5h.375c.621 0 1.125.504 1.125 1.125v9.75c0 .621-.504 1.125-1.125 1.125h-.375m1.5-1.5H21a.75.75 0 00-.75.75v.75m0 0H3.75m0 0h-.375a1.125 1.125 0 01-1.125-1.125V15m1.5 1.5v-.75A.75.75 0 003 15h-.75M15 10.5a3 3 0 11-6 0 3 3 0 016 0zm3 0h.008v.008H18V10.5zm-12 0h.008v.008H6V10.5z" />
        </svg>
      ),
      gradient: 'from-primary-600/20 to-primary-800/20',
      borderColor: 'border-primary-500/30',
      iconBg: 'bg-primary-500/20 text-primary-400',
    },
    {
      label: 'Held for Payouts',
      value: balance.held_balance_paise,
      icon: (
        <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
          <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z" />
        </svg>
      ),
      gradient: 'from-warning-500/15 to-warning-600/10',
      borderColor: 'border-warning-500/30',
      iconBg: 'bg-warning-500/20 text-warning-400',
    },
    {
      label: 'Total Credited',
      value: balance.total_credits_paise,
      icon: (
        <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
          <path strokeLinecap="round" strokeLinejoin="round" d="M3 4.5h14.25M3 9h9.75M3 13.5h5.25m5.25-.75L17.25 9m0 0L21 12.75M17.25 9v12" />
        </svg>
      ),
      gradient: 'from-success-500/15 to-success-600/10',
      borderColor: 'border-success-500/30',
      iconBg: 'bg-success-500/20 text-success-400',
    },
    {
      label: 'Total Debited',
      value: balance.total_debits_paise,
      icon: (
        <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
          <path strokeLinecap="round" strokeLinejoin="round" d="M3 4.5h14.25M3 9h9.75M3 13.5h9.75m4.5-4.5v12m0 0l-3.75-3.75M17.25 21L21 17.25" />
        </svg>
      ),
      gradient: 'from-danger-500/15 to-danger-600/10',
      borderColor: 'border-danger-500/30',
      iconBg: 'bg-danger-500/20 text-danger-400',
    },
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      {cards.map((card, index) => (
        <div
          key={card.label}
          className={`
            relative overflow-hidden rounded-2xl
            bg-gradient-to-br ${card.gradient}
            backdrop-blur-xl
            border ${card.borderColor}
            p-6 transition-all duration-300
            hover:scale-[1.02] hover:shadow-lg hover:shadow-primary-500/5
            animate-fade-in-up
          `}
          style={{ animationDelay: `${index * 80}ms` }}
        >
          {/* Subtle glow effect */}
          <div className="absolute -top-12 -right-12 w-24 h-24 bg-white/[0.03] rounded-full blur-2xl" />
          
          <div className="flex items-center justify-between mb-4">
            <span className="text-sm font-medium text-surface-400">{card.label}</span>
            <div className={`p-2 rounded-xl ${card.iconBg}`}>
              {card.icon}
            </div>
          </div>
          <div className="text-2xl font-bold tracking-tight text-surface-50">
            {formatPaise(card.value)}
          </div>
        </div>
      ))}
    </div>
  );
}
