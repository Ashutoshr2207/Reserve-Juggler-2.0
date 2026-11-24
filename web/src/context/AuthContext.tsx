import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState
} from 'react';
import type { BankerProfile, MeResponse, AuthResponse } from '../types/auth';
import { api, setCsrfToken } from '../utils/api';

export interface RegisterData {
  full_name: string;
  email: string;
  organization_name: string;
  job_title?: string;
  password: string;
  confirm_password?: string;
}

interface AuthContextType {
  user: BankerProfile | null;
  loading: boolean;
  authenticated: boolean;
  serviceUnavailable: boolean;
  authError: string;
  setAuthError: (msg: string) => void;
  login: (email: string, password: string) => Promise<boolean>;
  register: (data: RegisterData) => Promise<boolean>;
  logout: () => Promise<void>;
  checkAuth: () => Promise<boolean>;
}

const AuthContext = createContext<AuthContextType | null>(null);

const PROTECTED_ROUTE_LIST = [
  'overview',
  'forecast',
  'scenarios',
  'investments',
  'events',
  'decisions',
  'activity',
  'policy',
  'data'
];

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({
  children
}) => {
  const [user, setUser] = useState<BankerProfile | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [serviceUnavailable, setServiceUnavailable] = useState<boolean>(false);
  const [authError, setAuthError] = useState<string>('');

  const checkAuth = useCallback(async (): Promise<boolean> => {
    try {
      const res = await api<MeResponse>('auth/me');
      if (res && res.authenticated && res.user) {
        setUser(res.user);
        if (res.csrf_token) {
          setCsrfToken(res.csrf_token);
        }
        setServiceUnavailable(false);
        return true;
      }
      setUser(null);
      setServiceUnavailable(false);
      return false;
    } catch (err) {
      setUser(null);
      const isOutage =
        err instanceof TypeError ||
        (err instanceof Error &&
          (err.message.includes('fetch') ||
            err.message.includes('network') ||
            err.message.includes('Failed to fetch') ||
            err.message.includes('502') ||
            err.message.includes('503')));
      setServiceUnavailable(isOutage);
      return false;
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  const login = useCallback(
    async (email: string, password: string): Promise<boolean> => {
      setAuthError('');
      try {
        const res = await api<AuthResponse>('auth/login', { email, password });
        if (res && res.user) {
          setUser(res.user);
          if (res.csrf_token) {
            setCsrfToken(res.csrf_token);
          }
          const redirectTarget = sessionStorage.getItem('rj_auth_redirect');
          sessionStorage.removeItem('rj_auth_redirect');
          if (redirectTarget && PROTECTED_ROUTE_LIST.includes(redirectTarget)) {
            window.location.hash = redirectTarget;
          } else {
            window.location.hash = 'overview';
          }
          return true;
        }
        return false;
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err);
        setAuthError(msg);
        return false;
      }
    },
    []
  );

  const register = useCallback(
    async (data: RegisterData): Promise<boolean> => {
      setAuthError('');
      try {
        const res = await api<AuthResponse>('auth/register', data);
        if (res && res.user) {
          setUser(res.user);
          if (res.csrf_token) {
            setCsrfToken(res.csrf_token);
          }
          sessionStorage.removeItem('rj_auth_redirect');
          window.location.hash = 'overview';
          return true;
        }
        return false;
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err);
        setAuthError(msg);
        return false;
      }
    },
    []
  );

  const logout = useCallback(async () => {
    try {
      await api('auth/logout', {});
    } catch {
      // Ignore network errors on logout
    } finally {
      setUser(null);
      setCsrfToken('');
      sessionStorage.removeItem('rj_auth_redirect');
      window.location.hash = 'home';
    }
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        authenticated: !!user,
        serviceUnavailable,
        authError,
        setAuthError,
        login,
        register,
        logout,
        checkAuth
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
