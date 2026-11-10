import { useEffect, useMemo, useState } from "react";
import { api, type AccountId, type Candle, type Decision, type Order, type Portfolio, type Position, type Risk, type Trade } from "./api";

const money = (value: number) => `$${value.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const date = (value: string) => new Date(value).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
const tone = (value: number) => value >= 0 ? "text-cyan" : "text-rose";

function Sparkline({ candles, trades }: { candles: Candle[]; trades: Trade[] }) {
  if (!candles.length) return <div className="flex h-48 items-center justify-center text-sm text-slate-500">No candle data available.</div>;
  const prices = candles.flatMap((c) => [c.high, c.low]), min = Math.min(...prices), max = Math.max(...prices), range = max - min || 1;
  const y = (price: number) => 92 - ((price - min) / range) * 80;
  const x = (index: number) => 4 + (index / Math.max(candles.length - 1, 1)) * 92;
  const tradeMarkers = trades.map((trade) => {
    let index = 0;
    candles.forEach((candle, candidate) => { if (Math.abs(new Date(candle.timestamp).getTime() - new Date(trade.timestamp).getTime()) < Math.abs(new Date(candles[index].timestamp).getTime() - new Date(trade.timestamp).getTime())) index = candidate; });
    return <circle key={trade.id} cx={x(index)} cy={y(trade.price)} r="1.8" fill={trade.side === "BUY" ? "#52e0d0" : "#ff718b"} stroke="#070b16" strokeWidth=".8" vectorEffect="non-scaling-stroke" />;
  });
  return <svg viewBox="0 0 100 100" className="h-48 w-full overflow-visible" preserveAspectRatio="none" aria-label="BTC USDT hourly candlestick chart">
    {candles.map((candle, index) => {
      const candleWidth = Math.max(0.35, 38 / candles.length), top = y(Math.max(candle.open, candle.close)), bottom = y(Math.min(candle.open, candle.close));
      return <g key={candle.timestamp}><line x1={x(index)} x2={x(index)} y1={y(candle.high)} y2={y(candle.low)} stroke={candle.close >= candle.open ? "#52e0d0" : "#ff718b"} strokeWidth=".5" vectorEffect="non-scaling-stroke" /><rect x={x(index) - candleWidth / 2} y={top} width={candleWidth} height={Math.max(bottom - top, .8)} fill={candle.close >= candle.open ? "#52e0d0" : "#ff718b"} opacity=".8" /></g>;
    })}
    {tradeMarkers}
  </svg>;
}

function Stat({ label, value, detail, positive }: { label: string; value: string; detail?: string; positive?: boolean }) {
  return <div className="rounded-2xl border border-line bg-panel/80 p-4 shadow-xl shadow-black/10">
    <div className="text-xs uppercase tracking-[.16em] text-slate-500">{label}</div>
    <div className={`mt-2 text-xl font-semibold ${positive === undefined ? "text-white" : positive ? "text-cyan" : "text-rose"}`}>{value}</div>
    {detail && <div className="mt-1 text-xs text-slate-500">{detail}</div>}
  </div>;
}

function Panel({ title, action, children, className = "" }: { title: string; action?: string; children: React.ReactNode; className?: string }) {
  return <section className={`rounded-2xl border border-line bg-panel/80 p-5 shadow-xl shadow-black/10 ${className}`}>
    <div className="mb-5 flex items-center justify-between"><h2 className="text-sm font-semibold tracking-wide text-slate-200">{title}</h2>{action && <span className="text-xs text-slate-500">{action}</span>}</div>
    {children}
  </section>;
}

function Empty({ message }: { message: string }) { return <div className="rounded-xl border border-dashed border-line p-6 text-center text-sm text-slate-500">{message}</div>; }

export default function App() {
  const [account, setAccount] = useState<AccountId>("small_account_01");
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [candles, setCandles] = useState<Candle[]>([]);
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [risk, setRisk] = useState<Risk | null>(null);
  const [positions, setPositions] = useState<Position[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshToken, setRefreshToken] = useState(0);

  useEffect(() => {
    let active = true;
    setLoading(true); setError(null);
    Promise.all([api.portfolio(account), api.candles("BTC/USDT"), api.decisions(account), api.risk(account), api.positions(account), api.orders(account), api.trades(account)])
      .then(([nextPortfolio, nextCandles, nextDecisions, nextRisk, nextPositions, nextOrders, nextTrades]) => {
        if (!active) return;
        setPortfolio(nextPortfolio); setCandles(nextCandles.candles); setDecisions(nextDecisions); setRisk(nextRisk);
        setPositions(nextPositions); setOrders(nextOrders); setTrades(nextTrades);
      })
      .catch((reason: unknown) => { if (active) setError(reason instanceof Error ? reason.message : "Unable to load dashboard data."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [account, refreshToken]);

  const mode = account === "research_lab_01" ? "RESEARCH" : "SMALL ACCOUNT";
  const chartDelta = useMemo(() => candles.length > 1 ? candles[candles.length - 1].close - candles[0].close : 0, [candles]);

  return <div className="relative min-h-screen overflow-hidden">
    <div className="grid-pattern pointer-events-none absolute inset-0" />
    <main className="relative mx-auto max-w-[1500px] px-4 py-6 sm:px-8 lg:py-10">
      <header className="mb-8 flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
        <div><div className="mb-3 flex items-center gap-3"><span className="h-2 w-2 rounded-full bg-cyan shadow-[0_0_14px_#52e0d0]" /><span className="text-xs font-medium uppercase tracking-[.24em] text-cyan">Autonomous spot trading</span></div>
          <h1 className="text-3xl font-semibold tracking-tight text-white sm:text-4xl">CryptoPilot <span className="text-slate-500">/ cockpit</span></h1>
          <p className="mt-2 max-w-xl text-sm text-slate-400">Transparent performance telemetry, strategy consensus, and execution audit.</p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <select value={account} onChange={(event) => setAccount(event.target.value as AccountId)} className="rounded-xl border border-line bg-panel px-4 py-2.5 text-sm text-slate-200 outline-none focus:border-cyan">
            <option value="small_account_01">Small account · $30</option><option value="research_lab_01">Research · $10,000</option>
          </select>
          <span className={`rounded-xl border px-3 py-2 text-xs font-semibold tracking-wide ${account === "research_lab_01" ? "border-amber/40 bg-amber/10 text-amber" : "border-rose/40 bg-rose/10 text-rose"}`}>⚠ {mode} MODE</span>
        </div>
      </header>

      {error && <div role="alert" className="mb-6 flex items-center justify-between rounded-xl border border-rose/40 bg-rose/10 px-4 py-3 text-sm text-rose"><span>API unavailable: {error}</span><button className="text-xs underline" onClick={() => setRefreshToken((current) => current + 1)}>Retry</button></div>}
      {loading && <div className="mb-6 rounded-xl border border-cyan/20 bg-cyan/5 px-4 py-3 text-sm text-cyan">Syncing telemetry…</div>}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-7">
        <Stat label="Equity" value={portfolio ? money(portfolio.current_equity) : "—"} detail={portfolio?.account_type} />
        <Stat label="Cash" value={portfolio ? money(portfolio.total_cash) : "—"} />
        <Stat label="Deposits" value={portfolio ? money(portfolio.total_deposits) : "—"} />
        <Stat label="Realized PnL" value={portfolio ? money(portfolio.realized_pnl) : "—"} positive={portfolio ? portfolio.realized_pnl >= 0 : undefined} />
        <Stat label="Unrealized PnL" value={portfolio ? money(portfolio.unrealized_pnl) : "—"} positive={portfolio ? portfolio.unrealized_pnl >= 0 : undefined} />
        <Stat label="Return" value={portfolio ? `${portfolio.net_trading_return_pct.toFixed(2)}%` : "—"} positive={portfolio ? portfolio.net_trading_return_pct >= 0 : undefined} />
        <Stat label="Drawdown" value={portfolio ? `${portfolio.max_drawdown_pct.toFixed(2)}%` : "—"} positive={false} />
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-[1.65fr_1fr]">
        <Panel title="BTC / USDT · 1H" action={candles.length ? `${candles.length} candles · ${chartDelta >= 0 ? "+" : ""}${chartDelta.toFixed(2)}` : "Waiting for data"}>
          <Sparkline candles={candles} trades={trades} />
          <div className="mt-3 flex justify-between text-xs text-slate-500"><span>Price action</span><span>{candles.at(-1) ? money(candles.at(-1)!.close) : "—"}</span></div>
        </Panel>
        <Panel title="Risk monitor" action={risk?.is_tripped ? "TRIPPED" : "Within limits"}>
          <div className="space-y-4">
            <div className="flex items-center justify-between"><span className="text-sm text-slate-400">Daily loss</span><span className="font-medium text-white">{risk ? `${(risk.daily_loss_pct * 100).toFixed(2)}% / ${(risk.daily_loss_limit_pct * 100).toFixed(2)}%` : "—"}</span></div>
            <div className="h-2 overflow-hidden rounded-full bg-slate-800"><div className={`h-full rounded-full ${risk?.is_tripped ? "bg-rose" : "bg-cyan"}`} style={{ width: `${Math.min((risk?.daily_loss_pct ?? 0) / Math.max(risk?.daily_loss_limit_pct ?? 1, 0.01) * 100, 100)}%` }} /></div>
            <div className="grid grid-cols-2 gap-3 text-sm"><div className="rounded-xl bg-slate-900/70 p-3"><div className="text-xs text-slate-500">Consecutive losses</div><div className="mt-1 text-lg text-white">{risk?.consecutive_losses ?? "—"}</div></div><div className="rounded-xl bg-slate-900/70 p-3"><div className="text-xs text-slate-500">Circuit breaker</div><div className={`mt-1 text-lg ${risk?.is_tripped ? "text-rose" : "text-cyan"}`}>{risk?.is_tripped ? "TRIPPED" : "READY"}</div></div></div>
          </div>
        </Panel>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Panel title="Live strategy signals" action="Latest arbiter decisions">
          <div className="space-y-3">{decisions.length ? decisions.slice(0, 4).map((decision) => <div key={decision.id} className="rounded-xl border border-line/80 bg-slate-950/30 p-3"><div className="flex items-center justify-between"><div className="flex items-center gap-3"><span className={`rounded-md px-2 py-1 text-xs font-bold ${decision.decision === "BUY" ? "bg-cyan/10 text-cyan" : decision.decision === "SELL" ? "bg-rose/10 text-rose" : "bg-slate-700 text-slate-300"}`}>{decision.decision}</span><span className="text-sm text-white">{decision.symbol}</span></div><span className="text-xs text-slate-500">{date(decision.timestamp)}</span></div><div className="mt-2 flex items-center justify-between text-xs text-slate-400"><span>{decision.market_regime.replaceAll("_", " ")}</span><span className="text-cyan">{(decision.confidence * 100).toFixed(0)}% confidence</span></div>{decision.sentiment_summary && <div className="mt-2 text-xs text-slate-500">Sentiment: <span className="text-slate-300">{String(decision.sentiment_summary.sentiment_score ?? "—")}</span></div>}</div>) : <Empty message="No strategy decisions recorded yet." />}</div>
        </Panel>
        <Panel title="Decision transparency" action="AI rationale log">
          {decisions[0] ? <div><div className="mb-4 flex items-center justify-between"><span className="text-xs uppercase tracking-[.14em] text-cyan">Most recent · {decisions[0].decision}</span><span className="text-xs text-slate-500">{date(decisions[0].timestamp)}</span></div><p className="text-sm leading-6 text-slate-300">{decisions[0].explanation}</p><div className="mt-5 grid grid-cols-2 gap-3"><div className="rounded-xl bg-slate-900/70 p-3"><div className="text-xs text-slate-500">ML prediction</div><div className="mt-1 text-sm text-white">{String(decisions[0].ml_prediction?.predicted_label ?? "Unavailable")}</div></div><div className="rounded-xl bg-slate-900/70 p-3"><div className="text-xs text-slate-500">Risk approval</div><div className={`mt-1 text-sm ${decisions[0].risk_approved ? "text-cyan" : "text-rose"}`}>{decisions[0].risk_approved ? "Approved" : "Rejected"}</div></div></div></div> : <Empty message="No explanation logs recorded yet." />}
        </Panel>
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-3">
        <Panel title="Active positions">{positions.length ? <div className="overflow-x-auto"><table className="w-full text-left text-xs"><thead className="text-slate-500"><tr><th className="pb-3">Pair</th><th className="pb-3">Side</th><th className="pb-3">Qty</th><th className="pb-3 text-right">PnL</th></tr></thead><tbody>{positions.map((position) => <tr key={position.id} className="border-t border-line/70"><td className="py-3 text-white">{position.symbol}</td><td className="py-3 text-cyan">{position.side}</td><td className="py-3 text-slate-300">{position.quantity}</td><td className={`py-3 text-right ${tone(position.unrealized_pnl)}`}>{money(position.unrealized_pnl)}</td></tr>)}</tbody></table></div> : <Empty message="No open positions." />}</Panel>
        <Panel title="Open orders">{orders.length ? <div className="space-y-2">{orders.slice(0, 5).map((order) => <div key={order.id} className="flex items-center justify-between border-b border-line/70 py-2 text-xs last:border-0"><span className="text-white">{order.side} {order.symbol}</span><span className="text-slate-400">{order.status}</span><span className="text-slate-300">{order.price ? money(order.price) : "Market"}</span></div>)}</div> : <Empty message="No orders recorded." />}</Panel>
        <Panel title="Trade audit" action="Most recent fills">{trades.length ? <div className="space-y-2">{trades.slice(0, 5).map((trade) => <div key={trade.id} className="flex items-center justify-between border-b border-line/70 py-2 text-xs last:border-0"><span className="text-slate-500">{date(trade.timestamp)}</span><span className={trade.side === "BUY" ? "text-cyan" : "text-rose"}>{trade.side}</span><span className="text-white">{money(trade.price)}</span></div>)}</div> : <Empty message="No fills recorded." />}</Panel>
      </div>
      <footer className="mt-8 flex flex-col justify-between gap-2 border-t border-line/70 pt-5 text-xs text-slate-600 sm:flex-row"><span>CryptoPilot AI · paper execution only</span><span>Research and Small-Account ledgers are strictly isolated.</span></footer>
    </main>
  </div>;
}
