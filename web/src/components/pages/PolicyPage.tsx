import React, { useState } from 'react';
import { useTreasury } from '../../hooks/useTreasury';
import type { Policy } from '../../types/treasury';
import { Heading } from '../common/Heading';
import SpecularButton from './SpecularButton';

export const PolicyPage: React.FC = () => {
  const { state, mutate, showToast, openResetModal, busy } = useTreasury();
  const [policy, setPolicy] = useState<Policy | null>(state?.policy ?? null);
  if (!state || !policy) return null;
  const update = (key: keyof Policy, value: number | boolean) => setPolicy(prev => prev ? { ...prev, [key]: value } : prev);
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!busy && await mutate('policy', { policy })) showToast('Policy saved.');
  };
  return <>
    <Heading title="Reserve policy" description="Set your cash floor, forecast confidence and automation." />
    <section className="panel settings-layout">
      <div className="panel-header"><h2>Liquidity controls</h2></div>
      <form id="policy-form" className="panel-content" onSubmit={handleSubmit}>
        <div className="form-grid">
          <div className="form-field"><label htmlFor="minimum_buffer">Minimum cash buffer · INR</label><input id="minimum_buffer" type="number" min="0" max="10000000000" step="1000" value={policy.minimum_buffer} required onChange={e => update('minimum_buffer', Number(e.target.value))} /><small>Operational floor, before additional buffers.</small></div>
          <div className="form-field"><label htmlFor="confidence">Forecast confidence</label><select id="confidence" value={policy.confidence} onChange={e => update('confidence', Number(e.target.value))}>{[90, 95, 99].map(v => <option key={v} value={v}>{v}%</option>)}</select><small>Higher confidence widens the planning reserve.</small></div>
          <div className="form-field"><label htmlFor="withdrawal_stress">Additional withdrawals · %</label><input id="withdrawal_stress" type="number" min="0" max="100" step="1" value={policy.withdrawal_stress} required onChange={e => update('withdrawal_stress', Number(e.target.value))} /></div>
        </div>
        <div className="form-section">
          <h3>Automatic investment</h3>
          <label className="checkbox"><input name="auto_sweep" type="checkbox" checked={policy.auto_sweep} onChange={e => update('auto_sweep', e.target.checked)} />Automatically sweep eligible surplus after each simulated hour</label>
        </div>
        <details className="inline-details"><summary>Custom-term sweep settings</summary>
          <p className="helper-line">These settings apply to the custom-term sweep. Product terms are configured in Investment options.</p>
          <div className="form-grid">
            <div className="form-field"><label htmlFor="lock_hours">Vault lock period · hours</label><input id="lock_hours" type="number" min="1" max="72" step="1" value={policy.lock_hours} required onChange={e => update('lock_hours', Number(e.target.value))} /></div>
            <div className="form-field"><label htmlFor="annual_yield">Assumed annual yield · %</label><input id="annual_yield" type="number" min="0" max="20" step="0.01" value={policy.annual_yield} required onChange={e => update('annual_yield', Number(e.target.value))} /></div>
          </div>
        </details>
        <div className="form-actions">
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
            Save policy
          </SpecularButton>
          <span className="muted">Existing investments retain their agreed terms.</span>
        </div>
      </form>
    </section>
    <details className="panel model-details settings-layout"><summary>How the reserve is calculated</summary><div className="panel-content">
      <p>Required reserve combines the minimum cash buffer, additional risk buffer and worst projected drawdown during the investment lock. Payment timing, entry fees and the 72-hour cash path also affect eligibility.</p>
      <p>Forecast uncertainty is a planning estimate, not a payout guarantee. Adjust the additional risk buffer in <a className="text-link" href="#investments">Investment options</a>.</p>
    </div></details>
    <details className="panel model-details danger-section settings-layout"><summary>Reset workspace</summary><div className="panel-content">
      <p>Reset removes imported data, policy changes, balances and history from this simulation. A confirmation is required.</p>
      <div className="form-actions">
        <SpecularButton
          type="button"
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
          onClick={openResetModal}
        >
          Reset sandbox
        </SpecularButton>
      </div>
    </div></details>
  </>;
};
