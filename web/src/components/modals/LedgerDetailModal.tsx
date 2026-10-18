import React from 'react';
import type { LedgerEntry } from '../../types/treasury';
import { date, money } from '../../utils/formatters';
import { ModalDialog } from './ModalDialog';

interface LedgerDetailModalProps {
  entry: LedgerEntry | null;
  onClose: () => void;
}

export const LedgerDetailModal: React.FC<LedgerDetailModalProps> = ({
  entry,
  onClose
}) => {
  if (!entry) return null;

  return (
    <ModalDialog isOpen={!!entry} onClose={onClose}>
      <div className="eyebrow">Simulation ledger</div>
      <h2 id="dialog-title">{entry.type}</h2>
      <p>{entry.description}</p>
      <div className="dialog-amount">{money(entry.amount, 2)}</div>
      <dl>
        <dt>Reference</dt>
        <dd>{entry.id}</dd>
        <dt>Timestamp · IST</dt>
        <dd>{date(entry.timestamp)}</dd>
        <dt>Status</dt>
        <dd>Simulated</dd>
      </dl>
      <div className="dialog-actions">
        <button
          type="button"
          className="btn"
          data-action="close-dialog"
          onClick={onClose}
        >
          Close
        </button>
      </div>
    </ModalDialog>
  );
};
