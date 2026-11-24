import React, { useState } from 'react';
import { useAuth } from '../../hooks/useAuth';
import { ThemeToggle } from '../common/ThemeToggle';
import SpecularButton from './SpecularButton';
import './AuthPages.css';

export const RegisterPage: React.FC = () => {
  const { register, authError, setAuthError } = useAuth();
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [orgName, setOrgName] = useState('');
  const [jobTitle, setJobTitle] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const validate = (): boolean => {
    const errors: Record<string, string> = {};
    if (!fullName.trim()) {
      errors.fullName = 'Full name is required.';
    }
    if (!email.trim()) {
      errors.email = 'Work email is required.';
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      errors.email = 'Please provide a valid work email address.';
    }
    if (!orgName.trim()) {
      errors.orgName = 'Organization name is required.';
    }
    if (!password) {
      errors.password = 'Password is required.';
    } else if (password.length < 12) {
      errors.password = 'Password must be at least 12 characters long.';
    }
    if (password !== confirmPassword) {
      errors.confirmPassword = 'Passwords do not match.';
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
      const ok = await register({
        full_name: fullName.trim(),
        email: email.trim(),
        organization_name: orgName.trim(),
        job_title: jobTitle.trim() || undefined,
        password,
        confirm_password: confirmPassword
      });
      if (!ok) {
        setLoading(false);
      }
    } catch {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-top-bar">
        <a href="#home" className="auth-back-home">
          ← Back to Reserve Juggler
        </a>
        <ThemeToggle />
      </div>

      <div className="auth-card">
        <div className="auth-header">
          <a href="#home" className="auth-brand">
            <span className="auth-brand-logo">RJ</span>
            Reserve Juggler
          </a>
          <h1 className="auth-title">Create Banker Account</h1>
          <p className="auth-subtitle">
            Institutional liquidity forecasting and reserve management
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
            <label className="auth-label" htmlFor="reg-fullname">
              Full Name *
            </label>
            <input
              id="reg-fullname"
              type="text"
              required
              className={`auth-input ${fieldErrors.fullName ? 'has-error' : ''}`}
              placeholder="e.g. Priya Sharma"
              value={fullName}
              onChange={(e) => {
                setFullName(e.target.value);
                if (fieldErrors.fullName) {
                  setFieldErrors((prev) => ({ ...prev, fullName: '' }));
                }
              }}
              disabled={loading}
            />
            {fieldErrors.fullName && (
              <span className="auth-field-error">{fieldErrors.fullName}</span>
            )}
          </div>

          <div className="auth-field">
            <label className="auth-label" htmlFor="reg-email">
              Work Email *
            </label>
            <input
              id="reg-email"
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
            <label className="auth-label" htmlFor="reg-org">
              Financial Institution / Organization *
            </label>
            <input
              id="reg-org"
              type="text"
              required
              className={`auth-input ${fieldErrors.orgName ? 'has-error' : ''}`}
              placeholder="e.g. State Bank of India"
              value={orgName}
              onChange={(e) => {
                setOrgName(e.target.value);
                if (fieldErrors.orgName) {
                  setFieldErrors((prev) => ({ ...prev, orgName: '' }));
                }
              }}
              disabled={loading}
            />
            {fieldErrors.orgName && (
              <span className="auth-field-error">{fieldErrors.orgName}</span>
            )}
          </div>

          <div className="auth-field">
            <label className="auth-label" htmlFor="reg-title">
              Job Title (Optional)
            </label>
            <input
              id="reg-title"
              type="text"
              className="auth-input"
              placeholder="e.g. Head of Treasury & ALM"
              value={jobTitle}
              onChange={(e) => setJobTitle(e.target.value)}
              disabled={loading}
            />
          </div>

          <div className="auth-field">
            <label className="auth-label" htmlFor="reg-password">
              Password (min. 12 characters) *
            </label>
            <div className="auth-input-wrapper">
              <input
                id="reg-password"
                type={showPassword ? 'text' : 'password'}
                autoComplete="new-password"
                required
                className={`auth-input ${fieldErrors.password ? 'has-error' : ''}`}
                placeholder="Choose a strong passphrase"
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

          <div className="auth-field">
            <label className="auth-label" htmlFor="reg-confirm">
              Confirm Password *
            </label>
            <input
              id="reg-confirm"
              type={showPassword ? 'text' : 'password'}
              autoComplete="new-password"
              required
              className={`auth-input ${fieldErrors.confirmPassword ? 'has-error' : ''}`}
              placeholder="Confirm your password"
              value={confirmPassword}
              onChange={(e) => {
                setConfirmPassword(e.target.value);
                if (fieldErrors.confirmPassword) {
                  setFieldErrors((prev) => ({ ...prev, confirmPassword: '' }));
                }
              }}
              disabled={loading}
            />
            {fieldErrors.confirmPassword && (
              <span className="auth-field-error">{fieldErrors.confirmPassword}</span>
            )}
          </div>

          <SpecularButton
            type="submit"
            size="lg"
            variant="primary"
            radius={18}
            disabled={loading}
            style={{ width: '100%', marginTop: '12px' }}
          >
            {loading ? 'Creating Account…' : 'Create Account'}
          </SpecularButton>
        </form>

        <div className="auth-footer">
          Already have an account? <a href="#login">Sign In</a>
        </div>
      </div>
    </div>
  );
};
