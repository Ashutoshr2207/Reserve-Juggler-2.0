export const money = (value: number, digits = 0): string =>
  new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: digits,
    minimumFractionDigits: digits
  }).format(value);

export const compact = (value: number): string => {
  const absolute = Math.abs(value);
  const sign = value < 0 ? '−' : '';
  if (absolute >= 1e7) {
    return `${sign}₹${new Intl.NumberFormat('en-IN', { maximumFractionDigits: 2 }).format(absolute / 1e7)} crore`;
  }
  if (absolute >= 1e5) {
    return `${sign}₹${new Intl.NumberFormat('en-IN', { maximumFractionDigits: 2 }).format(absolute / 1e5)} lakh`;
  }
  return money(value);
};

export const number = (value: number): string =>
  new Intl.NumberFormat('en-IN').format(value);

export const date = (value: string | number | Date, full = false): string =>
  new Intl.DateTimeFormat('en-IN', {
    timeZone: 'Asia/Kolkata',
    day: '2-digit',
    month: 'short',
    ...(full ? { year: 'numeric' } : {}),
    hour: '2-digit',
    minute: '2-digit',
    hour12: false
  }).format(new Date(value));

export const hour = (value: string | number | Date): string =>
  new Intl.DateTimeFormat('en-IN', {
    timeZone: 'Asia/Kolkata',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false
  }).format(new Date(value));

export const escapeHtml = (value: string | number): string =>
  String(value).replace(/[&<>"']/g, (c) => {
    switch (c) {
      case '&': return '&amp;';
      case '<': return '&lt;';
      case '>': return '&gt;';
      case '"': return '&quot;';
      case "'": return '&#39;';
      default: return c;
    }
  });
