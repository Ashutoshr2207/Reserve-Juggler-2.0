export interface Policy {
  minimum_buffer: number;
  confidence: number;
  lock_hours: number;
  annual_yield: number;
  withdrawal_stress: number;
  auto_sweep: boolean;
}

export interface Plan {
  required: number;
  sweep: number;
  retained: number;
  shortfall: number;
  daily_yield: number;
}

export interface ForecastRow {
  timestamp: string;
  mean: number;
  lower: number;
  upper: number;
  balance: number;
  lower_balance: number;
  upper_balance: number;
  withdrawals: number;
}

export interface GrossForecast {
  rows: Array<{
    deposits: number;
    withdrawals: number;
  }>;
}

export interface LedgerEntry {
  id: string;
  timestamp: string;
  type: string;
  amount: number;
  description: string;
  status: string;
}

export interface Tranche {
  amount: number;
  matures: string;
  annual_yield: number;
}

export interface OptionDetails {
  id: string;
  name: string;
  hours: number;
  rate: number;
  minimum: number;
  fee: number;
  penalty: number;
  eligible: number;
  suggested: number;
  required: number;
  matures: string;
  interest: number;
  net_return: number;
  risk: string;
  reason: string;
  shortfall: number;
  emergency_funding: number;
  projected_minimum: number;
}

export interface TimelineRow {
  timestamp: string;
  label: string;
  flow: number;
  balance: number;
  status: string;
}

export interface EventItem {
  label: string;
  timestamp: string;
  amount: number;
  status: string;
}

export interface DecisionRecord {
  timestamp: string;
  action: string;
  cash: number;
  before: { required: number; suggested: number };
  after: { required: number; suggested: number };
  reason: string;
}

export interface Intelligence {
  floor: number;
  locked_principal: number;
  projected_minimum: number;
  method: string;
  note: string;
  policy: {
    risk_buffer: number;
    option: string;
    rates: Record<string, number>;
  };
  selected: OptionDetails;
  optimized: OptionDetails;
  options: OptionDetails[];
  timeline: TimelineRow[];
  events: EventItem[];
}

export interface TreasuryState {
  revision: number;
  as_of: string;
  source: string;
  currency: string;
  cash: number;
  vault: number;
  earned: number;
  daily_vault_yield: number;
  model: string;
  history_count: number;
  baseline_mae: number;
  policy: Policy;
  plan: Plan;
  forecast: ForecastRow[];
  gross_forecast: GrossForecast;
  ledger: LedgerEntry[];
  tranches: Tranche[];
  intelligence: Intelligence;
  decisions: DecisionRecord[];
}

export interface ScenarioResult {
  plan: Plan;
  forecast: ForecastRow[];
  policy: Policy;
}

export interface PlanningScenarioResult {
  baseline: {
    selected: OptionDetails;
  };
  stressed: {
    selected: OptionDetails;
  };
}

export interface BacktestStrategyResult {
  strategy: string;
  net_interest: number;
  average_idle_cash: number;
  floor_breaches: number;
  maximum_shortfall: number;
  forecast_mae: number;
  forecast_rmse: number;
}

export interface BacktestReport {
  source: string;
  hours: number;
  model: string;
  results: BacktestStrategyResult[];
  assumptions: string[];
}
