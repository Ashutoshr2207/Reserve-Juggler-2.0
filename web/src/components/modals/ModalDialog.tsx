import React, { useEffect, useRef } from 'react';

interface ModalDialogProps {
  isOpen: boolean;
  onClose: () => void;
  children: React.ReactNode;
}

export const ModalDialog: React.FC<ModalDialogProps> = ({
  isOpen,
  onClose,
  children
}) => {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const lastFocusRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    const dialogNode = dialogRef.current;
    if (!dialogNode) {
      if (!isOpen) lastFocusRef.current?.focus();
      return;
    }

    if (isOpen) {
      lastFocusRef.current = document.activeElement as HTMLElement | null;
      if (!dialogNode.open) {
        dialogNode.showModal();
      }
    } else {
      if (dialogNode.open) {
        dialogNode.close();
      }
      lastFocusRef.current?.focus();
    }
  }, [isOpen]);

  useEffect(() => {
    const dialogNode = dialogRef.current;
    if (!dialogNode) return;

    const handleCancel = (event: Event) => {
      event.preventDefault();
      onClose();
    };

    dialogNode.addEventListener('cancel', handleCancel);
    return () => dialogNode.removeEventListener('cancel', handleCancel);
  }, [onClose]);

  if (!isOpen) return null;

  return (
    <dialog
      id="dialog"
      ref={dialogRef}
      aria-labelledby="dialog-title"
    >
      {children}
    </dialog>
  );
};
