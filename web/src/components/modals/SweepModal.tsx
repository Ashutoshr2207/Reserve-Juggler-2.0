import React, { useState } from 'react';
import type { TreasuryState } from '../../types/treasury';
import { money } from '../../utils/formatters';
import { Icon } from '../common/Icon';
import { ModalDialog } from './ModalDialog';
import SpecularButton from '../common/SpecularButton';

interface SweepModalProps {
  isOpen: boolean;
  onClose: () => void;
  state: TreasuryState;
  onSweep: () => Promise<boolean>;
  busy: boolean;
}

export const SweepModal: React.FC<SweepModalProps> = ({
  isOpen,
  onClose,
  state,
  onSweep,
  busy
}) => {
  const [errorMsg, setErrorMsg] = useState('');
  const p = state.plan;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (busy) return;
    setErrorMsg('');
    const success = await onSweep();
    if (!success) {
      setErrorMsg(
        'The sweep was not saved. Close this review and refresh the workspace before retrying.'
      );
    }
  };

  return (
    <ModalDialog isOpen={isOpen} onClose={onClose}>
      <div className="eyebrow">Review allocation</div>
      <h2 id="dialog-title">Put the surplus to work.</h2>
      <p>A simulated transfer from your cash buffer into a locked yield vault.</p>
      <div className="dialog-amount">{money(p.sweep, 2)}</div>
      <dl>
        <dt>Cash retained</dt>
        <dd>{money(p.retained, 2)}</dd>
        <dt>Required reserve</dt>
        <dd>{money(p.required, 2)}</dd>
        <dt>Lock period</dt>
        <dd>{state.policy.lock_hours} hours</dd>
        <dt>Assumed annual yield</dt>
        <dd>{state.policy.annual_yield}%</dd>
      </dl>
      <p>
        Locked principal cannot fund payouts before maturity. The server rechecks
        the reserve and workspace revision before saving.
      </p>
      <form id="sweep-form" onSubmit={handleSubmit}>
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
            radius={18}
            tint="#ffffff"
            tintOpacity={0.04}
            textColor="#f5f5f5"
            lineColor="#ffffff"
            baseColor="#525252"
            intensity={1}
            idleIntensity={0.35}
            shineSize={10}
            shineFade={34}
            thickness={1.2}
            glow={1}
            followMouse
            proximity={250}
            disabled={busy}
          >
            Simulate sweep <Icon name="arrow" />
          </SpecularButton>
        </div>
        <div className="dialog-error" role="alert">
          {errorMsg}
        </div>
      </form>
    </ModalDialog>
  );
};
