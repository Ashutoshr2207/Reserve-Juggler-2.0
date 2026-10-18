import { ModalDialog } from './ModalDialog';
import SpecularButton from '../common/SpecularButton';

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
            Reset sandbox
          </SpecularButton>
        </div>
      </form>
    </ModalDialog>
  );
};
