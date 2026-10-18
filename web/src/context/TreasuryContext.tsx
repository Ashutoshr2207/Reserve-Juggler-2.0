import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState
} from 'react';
import type { LedgerEntry, TreasuryState } from '../types/treasury';
import { api, ApiError } from '../utils/api';
import { useAuth } from '../hooks/useAuth';

interface TreasuryContextType {
  state: TreasuryState | null;
  loading: boolean;
  loadError: string;
  busy: boolean;
  timerActive: boolean;
  toast: { message: string; visible: boolean };
  showToast: (message: string) => void;
  loadState: () => Promise<void>;
  mutate: (action: string, extra?: Record<string, unknown>) => Promise<boolean>;
  advanceHour: () => Promise<boolean>;
  toggleTimer: () => void;
  stopTimer: () => void;

  // Modals
  isSweepModalOpen: boolean;
  openSweepModal: () => void;
  closeSweepModal: () => void;

  investModalState: { isOpen: boolean; optimized: boolean };
  openInvestModal: (optimized?: boolean) => void;
  closeInvestModal: () => void;

  isResetModalOpen: boolean;
  openResetModal: () => void;
  closeResetModal: () => void;

  selectedLedgerEntry: LedgerEntry | null;
  viewLedgerDetail: (entry: LedgerEntry) => void;
  closeLedgerDetail: () => void;
}

const TreasuryContext = createContext<TreasuryContextType | null>(null);

function isValidTreasuryState(data: unknown): data is TreasuryState {
  if (!data || typeof data !== 'object') return false;
  const s = data as Record<string, unknown>;
  return (
    typeof s.cash === 'number' &&
    typeof s.currency === 'string' &&
    typeof s.revision === 'number' &&
    s.policy !== null &&
    typeof s.policy === 'object' &&
    s.plan !== null &&
    typeof s.plan === 'object' &&
    Array.isArray(s.forecast) &&
    s.intelligence !== null &&
    typeof s.intelligence === 'object'
  );
}

export const TreasuryProvider: React.FC<{ children: React.ReactNode }> = ({
  children
}) => {
  const { authenticated } = useAuth();
  const [state, setState] = useState<TreasuryState | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [loadError, setLoadError] = useState<string>('');
  const [busy, setBusy] = useState<boolean>(false);
  const [timerActive, setTimerActive] = useState<boolean>(false);
  const [toast, setToast] = useState<{ message: string; visible: boolean }>({
    message: '',
    visible: false
  });

  // Modals state
  const [isSweepModalOpen, setIsSweepModalOpen] = useState(false);
  const [investModalState, setInvestModalState] = useState<{
    isOpen: boolean;
    optimized: boolean;
  }>({ isOpen: false, optimized: false });
  const [isResetModalOpen, setIsResetModalOpen] = useState(false);
  const [selectedLedgerEntry, setSelectedLedgerEntry] =
    useState<LedgerEntry | null>(null);

  const toastTimeoutRef = useRef<number | null>(null);
  const timerRef = useRef<number | null>(null);
  const stateRef = useRef<TreasuryState | null>(null);
  stateRef.current = state;
  const busyRef = useRef<boolean>(busy);
  busyRef.current = busy;
  const loadSeqRef = useRef<number>(0);
  const loadingRef = useRef<boolean>(false);

  const showToast = useCallback((message: string) => {
    if (toastTimeoutRef.current) {
      clearTimeout(toastTimeoutRef.current);
    }
    setToast({ message, visible: true });
    toastTimeoutRef.current = window.setTimeout(() => {
      setToast((prev) => ({ ...prev, visible: false }));
    }, 5500);
  }, []);

  const loadState = useCallback(async () => {
    if (loadingRef.current) return;
    loadingRef.current = true;
    const seq = ++loadSeqRef.current;
    setLoading(true);
    setLoadError('');
    try {
      const data = await api<TreasuryState>('state');
      if (seq !== loadSeqRef.current) return;
      if (!isValidTreasuryState(data)) {
        throw new Error('Workspace state response is missing required treasury data.');
      }
      setState(data);
      setLoadError('');
    } catch (err) {
      if (seq !== loadSeqRef.current) return;
      if (err instanceof ApiError && err.status === 401) {
        setLoadError('Session expired or authentication required.');
        const currentRoute = window.location.hash.replace(/^#\/?/, '').trim();
        const publicPages = ['home', 'method', 'login', 'register'];
        if (!publicPages.includes(currentRoute)) {
          showToast('Your session has expired. Please sign in to continue.');
          window.location.hash = 'login';
        }
        return;
      }
      const message = (err as Error).message;
      setLoadError(message);
      if (stateRef.current) {
        showToast('Refresh failed: ' + message);
      }
    } finally {
      if (seq === loadSeqRef.current) {
        loadingRef.current = false;
        setLoading(false);
      }
    }
  }, [showToast]);

  const stopTimer = useCallback(() => {
    if (timerRef.current !== null) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    setTimerActive(false);
  }, []);

  const mutate = useCallback(
    async (
      action: string,
      extra: Record<string, unknown> = {}
    ): Promise<boolean> => {
      if (busyRef.current) return false;
      const currentState = stateRef.current;
      if (!currentState) return false;

      setBusy(true);
      try {
        const updated = await api<TreasuryState>(action, {
          revision: currentState.revision,
          request_id: crypto.randomUUID(),
          ...extra
        });
        setState(updated);
        if (action === 'reset') {
          stopTimer();
        }
        return true;
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) {
          showToast('Your session has expired. Please sign in to continue.');
          window.location.hash = 'login';
          return false;
        }
        showToast((err as Error).message);
        return false;
      } finally {
        setBusy(false);
      }
    },
    [showToast, stopTimer]
  );

  const advanceHour = useCallback(async (): Promise<boolean> => {
    const success = await mutate('advance');
    if (success) {
      showToast('One simulated hour processed. Reserve and ledger updated.');
    }
    return success;
  }, [mutate, showToast]);

  const toggleTimer = useCallback(() => {
    if (timerRef.current !== null) {
      stopTimer();
      showToast('Continuous simulation paused.');
    } else {
      setTimerActive(true);
      timerRef.current = window.setInterval(async () => {
        const dialogOpen = !!document.querySelector('dialog[open]');
        const isFormActive = !!document.activeElement?.closest('form');
        if (busyRef.current || dialogOpen || document.hidden || isFormActive) {
          return;
        }
        const ok = await mutate('advance');
        if (!ok) {
          stopTimer();
        }
      }, 60000);
      showToast(
        'Simulation started. One hour will advance every 60 seconds while this tab is visible.'
      );
    }
  }, [mutate, showToast, stopTimer]);

  useEffect(() => {
    if (authenticated) {
      loadState();
    } else {
      setState(null);
      stopTimer();
    }
    return () => {
      stopTimer();
      if (toastTimeoutRef.current) clearTimeout(toastTimeoutRef.current);
    };
  }, [authenticated, loadState, stopTimer]);

  const openSweepModal = useCallback(() => setIsSweepModalOpen(true), []);
  const closeSweepModal = useCallback(() => setIsSweepModalOpen(false), []);

  const openInvestModal = useCallback((optimized = false) => {
    setInvestModalState({ isOpen: true, optimized });
  }, []);
  const closeInvestModal = useCallback(() => {
    setInvestModalState({ isOpen: false, optimized: false });
  }, []);

  const openResetModal = useCallback(() => setIsResetModalOpen(true), []);
  const closeResetModal = useCallback(() => setIsResetModalOpen(false), []);

  const viewLedgerDetail = useCallback((entry: LedgerEntry) => {
    setSelectedLedgerEntry(entry);
  }, []);
  const closeLedgerDetail = useCallback(() => {
    setSelectedLedgerEntry(null);
  }, []);

  return (
    <TreasuryContext.Provider
      value={{
        state,
        loading,
        loadError,
        busy,
        timerActive,
        toast,
        showToast,
        loadState,
        mutate,
        advanceHour,
        toggleTimer,
        stopTimer,
        isSweepModalOpen,
        openSweepModal,
        closeSweepModal,
        investModalState,
        openInvestModal,
        closeInvestModal,
        isResetModalOpen,
        openResetModal,
        closeResetModal,
        selectedLedgerEntry,
        viewLedgerDetail,
        closeLedgerDetail
      }}
    >
      {busy && <div className="busy-strip" id="busy-strip" />}
      {children}
    </TreasuryContext.Provider>
  );
};

export const useTreasuryContext = (): TreasuryContextType => {
  const context = useContext(TreasuryContext);
  if (!context) {
    throw new Error('useTreasuryContext must be used within TreasuryProvider');
  }
  return context;
};
