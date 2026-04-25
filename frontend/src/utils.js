/**
 * Format paise to INR display string.
 */
export function formatPaise(paise) {
  const rupees = Math.abs(paise) / 100;
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    minimumFractionDigits: 2,
  }).format(rupees);
}

/**
 * Format a date string to a human-readable format.
 */
export function formatDate(dateString) {
  if (!dateString) return '—';
  const date = new Date(dateString);
  return new Intl.DateTimeFormat('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: true,
  }).format(date);
}

/**
 * Format relative time (e.g., "2 min ago").
 */
export function formatRelativeTime(dateString) {
  if (!dateString) return '—';
  const now = new Date();
  const date = new Date(dateString);
  const diffMs = now - date;
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHour = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHour / 24);

  if (diffSec < 60) return 'just now';
  if (diffMin < 60) return `${diffMin}m ago`;
  if (diffHour < 24) return `${diffHour}h ago`;
  if (diffDay < 7) return `${diffDay}d ago`;
  return formatDate(dateString);
}

/**
 * Generate a UUID v4 for idempotency keys.
 */
export function generateUUID() {
  return crypto.randomUUID();
}

/**
 * Get status badge color classes.
 */
export function getStatusColor(status) {
  const colors = {
    pending: {
      bg: 'bg-warning-500/15',
      text: 'text-warning-400',
      dot: 'bg-warning-400',
    },
    processing: {
      bg: 'bg-processing-500/15',
      text: 'text-processing-400',
      dot: 'bg-processing-400',
    },
    completed: {
      bg: 'bg-success-500/15',
      text: 'text-success-400',
      dot: 'bg-success-400',
    },
    failed: {
      bg: 'bg-danger-500/15',
      text: 'text-danger-400',
      dot: 'bg-danger-400',
    },
  };
  return colors[status] || colors.pending;
}

/**
 * Get ledger entry type styling.
 */
export function getLedgerTypeStyle(type) {
  const styles = {
    credit: { icon: '↓', color: 'text-success-400', label: 'Credit', sign: '+' },
    debit: { icon: '↑', color: 'text-danger-400', label: 'Debit', sign: '-' },
    hold: { icon: '⏸', color: 'text-warning-400', label: 'Hold', sign: '-' },
    release: { icon: '↩', color: 'text-processing-400', label: 'Release', sign: '+' },
  };
  return styles[type] || styles.credit;
}
