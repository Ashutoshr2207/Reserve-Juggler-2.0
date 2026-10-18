import React from 'react';
import ReactDOM from 'react-dom/client';
import { App } from './App';
import { AuthProvider } from './context/AuthContext';
import { TreasuryAssistant } from './components/TreasuryAssistant';
import { TreasuryProvider } from './context/TreasuryContext';
import '../styles.css';
import './workspace.css';
import './visuals.css';

const rootElement = document.getElementById('app');

if (rootElement) {
  ReactDOM.createRoot(rootElement).render(
    <React.StrictMode>
      <AuthProvider>
        <TreasuryProvider>
          <App />
          <TreasuryAssistant />
        </TreasuryProvider>
      </AuthProvider>
    </React.StrictMode>
  );
}
