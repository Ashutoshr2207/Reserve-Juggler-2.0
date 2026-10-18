import React from 'react';

interface ToastProps {
  message: string;
  visible: boolean;
}

export const Toast: React.FC<ToastProps> = ({ message, visible }) => (
  <div
    id="toast"
    role="status"
    aria-live="polite"
    className={visible ? 'visible' : ''}
  >
    {message}
  </div>
);
