export type AccountId = "small_account_01" | "research_lab_01";
export type Envelope<T> = { success: boolean; data: T | null; error: string | null };

export interface Portfolio {
  portfolio_id: string;
  account_type: string;
  currency: string;
  initial_capital: number;
  total_deposits: number;
  total_cash: number;
  invested_capital: number;
  current_equity: number;
  realized_pnl: number;
  unrealized_pnl: number;
  total_fees_paid: number;
  net_trading_return_pct: number;
  max_drawdown_pct: number;
  is_trading_halted: boolean;
}
export interface Candle { timestamp: string; open: number; high: number; low: number; close: number; volume: number; }
export interface Decision {
  id: string; symbol: string; timestamp: string; decision: string; confidence: number;
  market_regime: string; strategy_signals: Record<string, unknown> | unknown[];
  ml_prediction?: Record<string, unknown> | null; sentiment_summary?: Record<string, unknown> | null;
  risk_approved: boolean; explanation: string;
}
export interface Position { id: string; symbol: string; side: string; status: string; quantity: number; entry_price: number; current_price: number; unrealized_pnl: number; opened_at: string; }
export interface Order { id: string; symbol: string; side: string; order_type: string; quantity: number; price: number | null; status: string; created_at: string; }
export interface Trade { id: string; symbol: string; side: string; price: number; quantity: number; fee: number; timestamp: string; }
export interface Risk { is_tripped: boolean; daily_loss_pct: number; daily_loss_limit_pct: number; consecutive_losses: number; emergency_stop: boolean; is_trading_halted: boolean; }

const apiBase = import.meta.env.VITE_API_BASE_URL ?? "";
async function request<T>(path: string): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${apiBase}${path}`);
  } catch {
    throw new Error("Cannot reach the API at http://127.0.0.1:8000. Start the FastAPI service and retry.");
  }

  const rawBody = await response.text();
  let body: Envelope<T>;
  try {
    body = JSON.parse(rawBody) as Envelope<T>;
  } catch {
    throw new Error(
      response.status === 404
        ? `API route not found: ${path}`
        : `API returned an invalid response (HTTP ${response.status}).`,
    );
  }
  if (!response.ok || !body.success || body.data === null) {
    throw new Error(body.error ?? `Request failed (${response.status})`);
  }
  return body.data;
}
export const api = {
  portfolio: (account: AccountId) => request<Portfolio>(`/api/v1/portfolio?account_id=${account}`),
  candles: (symbol: string) => request<{ candles: Candle[] }>(`/api/v1/market/candles?symbol=${encodeURIComponent(symbol)}&timeframe=1h&limit=60`),
  decisions: (account: AccountId) => request<Decision[]>(`/api/v1/decisions?limit=8`),
  risk: (account: AccountId) => request<Risk>(`/api/v1/risk/status?account_id=${account}`),
  positions: (account: AccountId) => request<Position[]>(`/api/v1/positions?account_id=${account}&status=OPEN`),
  orders: (account: AccountId) => request<Order[]>(`/api/v1/orders?account_id=${account}&limit=8`),
  trades: (account: AccountId) => request<Trade[]>(`/api/v1/trades?account_id=${account}&limit=8`),
};
