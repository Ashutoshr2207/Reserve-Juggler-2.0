import React, { useState } from 'react';
import type { TreasuryState } from '../../types/treasury';
import { date, money } from '../../utils/formatters';
import { ModalDialog } from './ModalDialog';
import SpecularButton from '../common/SpecularButton';

interface InvestModalProps {
  isOpen: boolean;
  onClose: () => void;
  state: TreasuryState;
  optimized: boolean;
  onInvest: (optimized: boolean, execution: string) => Promise<boolean>;
  busy: boolean;
}

export const InvestModal: React.FC<InvestModalProps> = ({
  isOpen,
  onClose,
  state,
  optimized,
  onInvest,
  busy
}) => {
  const [execution, setExecution] = useState('success');
  const c = optimized
    ? state.intelligence.optimized
    : state.intelligence.selected;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (busy) return;
    await onInvest(optimized, execution);
  };

  return (
    <ModalDialog isOpen={isOpen} onClose={onClose}>
      <h2 id="dialog-title">Review simulated investment</h2>
      <p>
        {c.name} · {c.hours} hours · {c.rate}% illustrative annual yield
      </p>
      <div className="dialog-amount">{money(c.suggested, 2)}</div>
      <p>
        Entry fee {money(c.fee)}. Funds return {date(c.matures)} IST. Estimated
        net earnings {money(c.net_return, 2)}.
      </p>
      <p className="subsection">{c.reason}</p>
      <form
        id="planning-invest"
        data-optimized={String(optimized)}
        onSubmit={handleSubmit}
      >
        <label htmlFor="execution">Simulated execution outcome</label>
        <select
          id="execution"
          name="execution"
          value={execution}
          onChange={(e) => setExecution(e.target.value)}
        >
          <option value="success">Success</option>
          <option value="failure">Execution failure</option>
          <option value="timeout">Timeout before execution</option>
        </select>
        <div className="dialog-actions">
          <button
            type="button"
            className="btn secondary"
            data-action="close-dialog"
            onClick={onClose}
          >
            Cancel
          </button>
          <SpecularButton
            type="submit"
            size="md"
            variant="primary"
            radius={18}
            disabled={busy}
          >
            Confirm simulation
          </SpecularButton>
        </div>
      </form>
    </ModalDialog>
  );
};
