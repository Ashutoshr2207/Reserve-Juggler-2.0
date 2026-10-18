import React from 'react';
import { ModalDialog } from './ModalDialog';

interface ResetModalProps {
  isOpen: boolean;
  onClose: () => void;
  onReset: () => Promise<boolean>;
  busy: boolean;
}

export const ResetModal: React.FC<ResetModalProps> = ({
  isOpen,
  onClose,
  onReset,
  busy
}) => {
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (busy) return;
    const success = await onReset();
    if (success) {
      onClose();
    }
  };

  return (
    <ModalDialog isOpen={isOpen} onClose={onClose}>
      <div className="eyebrow">Sandbox controls</div>
      <h2 id="dialog-title">Start with a clean slate?</h2>
      <p>
        This clears your local imported history, ledger, policy, and simulated
        positions, restoring the original demonstration.
      </p>
      <form id="reset-form" onSubmit={handleSubmit}>
        <div className="dialog-actions">
          <button
            type="button"
            className="btn secondary"
            data-action="close-dialog"
            onClick={onClose}
          >
            Keep workspace
          </button>
          <button type="submit" className="btn danger" disabled={busy}>
            Reset sandbox
          </button>
        </div>
      </form>
    </ModalDialog>
  );
};
