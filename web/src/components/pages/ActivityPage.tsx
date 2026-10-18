import React, { useState } from 'react';
import { useTreasury } from '../../hooks/useTreasury';
import { downloadLedgerCsv } from '../../utils/download';
import { date, money } from '../../utils/formatters';
import { Heading } from '../common/Heading';
import { Icon } from '../common/Icon';

const MOVEMENT_TYPES = [
  'All',
  'Failed sweep',
  'Investment',
  'Fee',
  'Decision',
  'Scheduled event',
  'Sweep',
  'Cashflow',
  'Maturity',
  'Interest',
  'Shortfall',
  'Policy',
  'Import'
];

export const ActivityPage: React.FC = () => {
  const { state, viewLedgerDetail } = useTreasury();

  const [ledgerQuery, setLedgerQuery] = useState('');
  const [ledgerType, setLedgerType] = useState('All');
  const [ledgerOrder, setLedgerOrder] = useState<'newest' | 'oldest'>('newest');
  const [ledgerPage, setLedgerPage] = useState(1);

  if (!state) return null;

  const filtered = state.ledger.filter((r) => {
    const matchesType = ledgerType === 'All' || r.type === ledgerType;
    const matchesText = `${r.id} ${r.type} ${r.description}`
      .toLowerCase()
      .includes(ledgerQuery.toLowerCase());
    return matchesType && matchesText;
  });

  const rows = ledgerOrder === 'oldest' ? [...filtered].reverse() : filtered;
  const pages = Math.max(1, Math.ceil(rows.length / 10));
  const currentPage = Math.min(ledgerPage, pages);

  const displayedRows = rows.slice((currentPage - 1) * 10, currentPage * 10);

  const handleExport = () => {
    downloadLedgerCsv(rows);
  };

  const headingActions = (
    <button
      className="btn secondary"
      data-action="export-ledger"
      onClick={handleExport}
    >
      <Icon name="download" /> Export ledger
    </button>
  );

  return (
    <>
      <Heading
        eyebrow="An accountable treasury"
        title="Sweep activity"
        description="Track movements, investment maturities and credited interest."
        actions={headingActions}
      />

      <section className="panel">
        <div className="table-tools">
          <input
            type="search"
            id="ledger-search"
            aria-label="Search activity"
            placeholder="Search reference, type, or description…"
            value={ledgerQuery}
            onChange={(e) => {
              setLedgerQuery(e.target.value);
              setLedgerPage(1);
            }}
          />
          <select
            id="ledger-type"
            aria-label="Filter movement type"
            value={ledgerType}
            onChange={(e) => {
              setLedgerType(e.target.value);
              setLedgerPage(1);
            }}
          >
            {MOVEMENT_TYPES.map((v) => (
              <option key={v} value={v}>
                {v}
              </option>
            ))}
          </select>
          <select
            id="ledger-order"
            aria-label="Sort activity"
            value={ledgerOrder}
            onChange={(e) => {
              setLedgerOrder(e.target.value as 'newest' | 'oldest');
              setLedgerPage(1);
            }}
          >
            <option value="newest">Newest first</option>
            <option value="oldest">Oldest first</option>
          </select>
        </div>

        <div id="ledger-table">
          {rows.length > 0 ? (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Reference / time · IST</th>
                    <th>Movement</th>
                    <th>Amount · INR</th>
                    <th>Details</th>
                  </tr>
                </thead>
                <tbody>
                  {displayedRows.map((r) => (
                    <tr key={r.id}>
                      <td>
                        <span className="mono">{r.id}</span>
                        <p className="muted">{date(r.timestamp)}</p>
                      </td>
                      <td>{r.type}</td>
                      <td>{money(r.amount, 2)}</td>
                      <td>
                        <button
                          className="text-link"
                          data-detail={r.id}
                          aria-label={`View ${r.id} details`}
                          onClick={() => viewLedgerDetail(r)}
                        >
                          View <Icon name="arrow" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="empty">
              <Icon name="activity" />
              <h3>
                {state.ledger.length
                  ? 'No matching movements.'
                  : 'No activity yet'}
              </h3>
              <p>
                {state.ledger.length
                  ? 'Try a different search or movement type.'
                  : 'Movements appear here after a simulated event or investment.'}
              </p>
            </div>
          )}

          <div className="pagination">
            <span>{rows.length} matching movements</span>
            <div>
              <button
                className="btn secondary small"
                data-page="-1"
                disabled={currentPage <= 1}
                aria-label="Previous page"
                onClick={() => setLedgerPage((p) => Math.max(1, p - 1))}
              >
                ←
              </button>
              <span>
                {currentPage} / {pages}
              </span>
              <button
                className="btn secondary small"
                data-page="1"
                disabled={currentPage >= pages}
                aria-label="Next page"
                onClick={() => setLedgerPage((p) => Math.min(pages, p + 1))}
              >
                →
              </button>
            </div>
          </div>
        </div>
      </section>

      <section className="panel model-details">
        <h2>Locked sweep principal</h2>
        {state.tranches.length > 0 ? (
          <div className="table-wrap subsection">
            <table>
              <thead>
                <tr>
                  <th>Principal</th>
                  <th>Matures · IST</th>
                  <th>Contracted annual rate</th>
                </tr>
              </thead>
              <tbody>
                {state.tranches.map((t, idx) => (
                  <tr key={`tranche-${t.matures}-${idx}`}>
                    <td>{money(t.amount, 2)}</td>
                    <td>{date(t.matures, true)}</td>
                    <td>{t.annual_yield}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p>No new sweeps are currently locked.</p>
        )}
        <p>
          Credited interest: {money(state.earned, 2)}. New investments return at maturity.
        </p>
        <details className="inline-details"><summary>About opening vault holdings</summary><p>Opening vault balances have no contractual redemption schedule and are excluded from available cash.</p></details>
      </section>
    </>
  );
};
