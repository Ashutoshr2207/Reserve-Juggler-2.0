import React, { useRef, useState } from 'react';
import { useTreasury } from '../../hooks/useTreasury';
import { date, number } from '../../utils/formatters';
import { Heading } from '../common/Heading';
import { Icon } from '../common/Icon';
import SpecularButton from './SpecularButton';

export const DataPage: React.FC = () => {
  const { state, mutate, showToast, stopTimer, busy } = useTreasury();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [cash, setCash] = useState(state?.cash ?? 0);
  const [vault, setVault] = useState(state?.vault ?? 0);
  if (!state) return null;
  const locked = state.tranches.length > 0;
  const importCsv = async (e: React.FormEvent) => {
    e.preventDefault();
    if (busy || locked) return;
    const file = fileInputRef.current?.files?.[0];
    if (!file) return;
    if (file.size > 1000000) { showToast('Choose a CSV smaller than 1 MB.'); return; }
    try {
      if (await mutate('import', { csv: await file.text() })) { stopTimer(); showToast('Cashflow history imported.'); }
    } catch (err) { showToast((err as Error).message); }
  };
  const saveBalances = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!busy && !locked && await mutate('planning_balance', { cash: Number(cash), vault: Number(vault) })) showToast('Simulated balances saved.');
  };
  return <>
    <Heading title="Data sources" description="Manage hourly observations used for forecasting."
      actions={<a className="btn secondary" href="/api/template"><Icon name="download" />Download sample CSV</a>} />
    <div className="content-grid">
      <section className="panel"><div className="panel-header"><h2>Import hourly cashflows</h2></div><div className="panel-content">
        <form id="import-form" onSubmit={importCsv}>
          <div className="upload-zone"><Icon name="upload" /><h3>Choose a CSV file</h3><p>168–5,000 hourly rows · INR · Up to 1 MB</p>
            <input type="file" id="csv-file" ref={fileInputRef} accept=".csv,text/csv" aria-label="Choose hourly cashflow CSV" required disabled={busy || locked} />
          </div>
          {locked && <p className="inline-alert">Import is unavailable until current investments mature.</p>}
          <div className="form-actions">
            <SpecularButton
              type="submit"
              size="md"
              variant="primary"
              radius={18}
              disabled={busy || locked}
            >
              Validate & import
            </SpecularButton>
          </div>
          <p className="helper-line">Replaces observations and disables auto-sweep. Simulated balances are preserved.</p>
        </form>
        <details className="inline-details"><summary>CSV format & requirements</summary>
          <pre className="code-sample">timestamp,deposits,withdrawals</pre>
          <p>Use consecutive hourly timestamps with Z or an explicit offset, such as +05:30. Amounts must be finite, nonnegative and no greater than ₹1 trillion. Missing, duplicate or irregular rows are rejected.</p>
          <p>The baseline-error calculation currently needs at least 192 rows. Use the sample CSV for a complete example.</p>
        </details>
      </div></section>
      <section className="panel"><div className="panel-header"><h2>Current data</h2></div><div className="panel-content">
        <dl className="data-facts">
          <div><dt>Source</dt><dd>{state.source}</dd></div><div><dt>Observations</dt><dd>{number(state.history_count)} hours</dd></div>
          <div><dt>Latest observation · IST</dt><dd>{date(state.as_of, true)}</dd></div><div><dt>Bank connection</dt><dd>Not connected</dd></div>
        </dl>
      </div></section>
    </div>
    <details className="panel model-details"><summary>Configure simulated balances</summary>
      <form id="planning-balances" className="panel-content" onSubmit={saveBalances}>
        <p className="helper-line">Demo balances only. Changes are unavailable while investments are locked.</p>
        <div className="form-grid">
          <div className="form-field"><label htmlFor="demo-cash">Liquid funds · ₹</label><input id="demo-cash" type="number" min="0" max="10000000000" step="0.01" value={cash} required disabled={locked} onChange={e => setCash(Number(e.target.value))} /></div>
          <div className="form-field"><label htmlFor="demo-vault">Already invested · ₹</label><input id="demo-vault" type="number" min="0" max="10000000000" step="0.01" value={vault} required disabled={locked} onChange={e => setVault(Number(e.target.value))} /></div>
        </div>
        <div className="form-actions">
          <SpecularButton
            type="submit"
            size="md"
            variant="primary"
            radius={18}
            disabled={busy || locked}
          >
            Save simulated balances
          </SpecularButton>
        </div>
      </form>
    </details>
    <details className="panel model-details"><summary>What is simulated?</summary><div className="panel-content"><p>Balances, investments and payment events are simulated. Importing observations does not connect a bank or establish live balances. Statutory CRR/SLR funds are outside this operational pool.</p></div></details>
  </>;
};
