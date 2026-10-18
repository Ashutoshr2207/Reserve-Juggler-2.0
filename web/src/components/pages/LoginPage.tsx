import React, { useState } from 'react';
import { useAuth } from '../../hooks/useAuth';
import './AuthPages.css';

export const LoginPage: React.FC = () => {
  const { login, authError, setAuthError } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const validate = (): boolean => {
    const errors: Record<string, string> = {};
    if (!email.trim()) {
      errors.email = 'Please enter your work email.';
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      errors.email = 'Please enter a valid email address.';
    }
    if (!password) {
      errors.password = 'Please enter your password.';
    }
    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthError('');
    if (!validate()) return;

    setLoading(true);
    try {
      const ok = await login(email.trim(), password);
      if (!ok) {
        setLoading(false);
      }
    } catch {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <a href="#home" className="auth-back-home">
        ← Back to Reserve Juggler
      </a>

      <div className="auth-card">
        <div className="auth-header">
          <a href="#home" className="auth-brand">
            <span className="auth-brand-logo">RJ</span>
            Reserve Juggler
          </a>
          <h1 className="auth-title">Banker Sign In</h1>
          <p className="auth-subtitle">
            Access your secure institutional treasury workspace
          </p>
        </div>

        {authError && (
          <div className="auth-alert-error" role="alert">
            <span aria-hidden="true">⚠️</span>
            <span>{authError}</span>
          </div>
        )}

        <form className="auth-form" onSubmit={handleSubmit} noValidate>
          <div className="auth-field">
            <label className="auth-label" htmlFor="login-email">
              Work Email
            </label>
            <input
              id="login-email"
              type="email"
              autoComplete="email"
              required
              className={`auth-input ${fieldErrors.email ? 'has-error' : ''}`}
              placeholder="banker@institution.com"
              value={email}
              onChange={(e) => {
                setEmail(e.target.value);
                if (fieldErrors.email) {
                  setFieldErrors((prev) => ({ ...prev, email: '' }));
                }
              }}
              disabled={loading}
            />
            {fieldErrors.email && (
              <span className="auth-field-error">{fieldErrors.email}</span>
            )}
          </div>

          <div className="auth-field">
            <label className="auth-label" htmlFor="login-password">
              Password
            </label>
            <div className="auth-input-wrapper">
              <input
                id="login-password"
                type={showPassword ? 'text' : 'password'}
                autoComplete="current-password"
                required
                className={`auth-input ${fieldErrors.password ? 'has-error' : ''}`}
                placeholder="Enter your password"
                value={password}
                onChange={(e) => {
                  setPassword(e.target.value);
                  if (fieldErrors.password) {
                    setFieldErrors((prev) => ({ ...prev, password: '' }));
                  }
                }}
                disabled={loading}
              />
              <button
                type="button"
                className="auth-toggle-pwd"
                aria-label={showPassword ? 'Hide password' : 'Show password'}
                onClick={() => setShowPassword(!showPassword)}
                tabIndex={-1}
              >
                {showPassword ? 'Hide' : 'Show'}
              </button>
            </div>
            {fieldErrors.password && (
              <span className="auth-field-error">{fieldErrors.password}</span>
            )}
          </div>

          <button
            type="submit"
            className="auth-btn-primary"
            disabled={loading}
          >
            {loading ? 'Signing in…' : 'Sign In'}
          </button>
        </form>

        <div className="auth-footer">
          Don’t have a banker account?{' '}
          <a href="#register">Create Account</a>
        </div>
      </div>
    </div>
  );
};
