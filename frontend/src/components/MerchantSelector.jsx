/**
 * Merchant selector dropdown in the header.
 */
export default function MerchantSelector({ merchants, selected, onSelect }) {
  return (
    <div className="flex items-center gap-3">
      <div className="flex items-center gap-2">
        <div className="w-8 h-8 rounded-lg bg-primary-500/20 flex items-center justify-center">
          <svg className="w-4 h-4 text-primary-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
            <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" />
          </svg>
        </div>
        <select
          id="merchant-selector"
          value={selected?.id || ''}
          onChange={(e) => {
            const merchant = merchants.find((m) => m.id === e.target.value);
            onSelect(merchant);
          }}
          className="
            bg-surface-800/60 border border-surface-600/50 rounded-xl
            px-4 py-2 text-sm text-surface-100
            focus:outline-none focus:ring-2 focus:ring-primary-500/40
            cursor-pointer appearance-none pr-8
            min-w-[220px]
          "
        >
          {merchants.map((merchant) => (
            <option key={merchant.id} value={merchant.id} className="bg-surface-900">
              {merchant.name}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}
