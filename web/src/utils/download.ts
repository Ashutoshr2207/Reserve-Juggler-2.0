import type { LedgerEntry } from '../types/treasury';

export function downloadLedgerCsv(entries: LedgerEntry[]): void {
  const rows = [
    ['Reference', 'Timestamp IST', 'Type', 'Amount INR', 'Description', 'Status'],
    ...entries.map((r) => [
      r.id,
      new Date(new Date(r.timestamp).getTime() + 19800000)
        .toISOString()
        .replace('Z', '+05:30'),
      r.type,
      r.amount,
      r.description,
      r.status
    ])
  ];

  const csv = rows
    .map((row) =>
      row.map((v) => '"' + String(v).replace(/"/g, '""') + '"').join(',')
    )
    .join('\r\n');

  const url = URL.createObjectURL(
    new Blob([csv], {
      type: 'text/csv;charset=utf-8'
    })
  );
  const a = document.createElement('a');
  a.href = url;
  a.download = 'reserve-juggler-ledger.csv';
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
