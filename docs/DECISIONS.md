# CryptoPilot AI: Architecture Decision Records (ADR)

## ADR-001: Selection of Modular Monolith Architecture
- **Status:** Accepted
- **Context:** Building an autonomous trading agent involves multiple interacting subsystems (market data, indicators, ML, sentiment, risk, execution, REST API, UI). Introducing microservices at this stage would introduce distributed network latency, operational overhead, serialization costs, and complex transaction rollbacks.
- **Decision:** Build CryptoPilot AI as a clean **Modular Monolith** within a single codebase using Python 3.12+. Enforce strict module boundaries via explicit interfaces, typed domain models (`Pydantic v2`), and dependency injection.
- **Consequences:** Simple deployment, unified transaction boundaries, zero cross-service RPC overhead, and rapid end-to-end testing, while retaining the freedom to split individual modules into independent microservices later if scaling necessitates.

---

## ADR-002: Hard-Coded Live Trading Prohibition (Paper-Only Initial Release)
- **Status:** Accepted
- **Context:** Cryptocurrency trading involves severe financial risks. Deploying untested code or autonomous AI logic to live exchange order routing risks immediate capital loss due to bugs, bad predictions, or network disconnects.
- **Decision:** Live trading order execution is hard-coded to be disabled in the initial release. Public exchange connectivity via CCXT is strictly restricted to read-only market data collection (tickers, order books, OHLCVs). The execution engine routes orders solely to an in-memory/database virtual paper broker.
- **Consequences:** Eliminates the risk of real-world fund loss. Real money execution can only be introduced in a future release following formal code reviews and security audits.

---

## ADR-003: Strict Separation of $30 Micro-Account and $10,000 Research Lab
- **Status:** Accepted
- **Context:** The user requested trading with an initial real capital of $30 and $10 monthly contributions, as well as a separate research environment with a virtual starting balance of $10,000. Mixing these contexts would lead to distorted performance reporting and dangerous sizing assumptions.
- **Decision:** Architect the portfolio engine with distinct account types:
  1. `small_account`: Models the $30 capital base, $10 monthly deposits, max 1 position, 30% allocation cap, 1% risk budget, and exchange minimum notional checks.
  2. `research`: Configurable $10,000 balance for parameter optimization and statistical backtesting without micro-lot quantization constraints.
- **Consequences:** Guaranteed financial transparency. Research results cannot be confused with the user's micro-account reality.

---

## ADR-004: Pure Functional Indicator Calculations with Zero-Lookahead Guarantees
- **Status:** Accepted
- **Context:** Many trading libraries accidentally introduce lookahead bias (e.g. centering rolling windows, using future bar closes, or calculating features on incomplete candles), creating backtests that look phenomenal but fail live.
- **Decision:** Implement technical indicators as pure, deterministic functions operating on closed candles (`is_closed == True`). Indicator calculations must never peek ahead, and must define explicit warm-up periods.
- **Consequences:** True mathematical reproducibility and zero lookahead bias across backtesting, paper trading, and live simulation.

---

## ADR-005: Event-Driven Backtesting with Real-World Slippage & Fee Frictions
- **Status:** Accepted
- **Context:** Vectorized backtesting often overstates profitability by assuming instant fills at exact closing prices with zero spread, slippage, or commission drag.
- **Decision:** Implement an event-driven backtesting engine that steps through bars chronologically, simulating orders at the subsequent bar's open price, applying bid/ask spreads, variable volume-based slippage, and maker/taker commissions ($0.10\%$).
- **Consequences:** Highly realistic, conservative backtest figures that closely match live paper execution.

---

## ADR-006: Supervised ML as Probabilistic Filter (No Autonomous Execution)
- **Status:** Accepted
- **Context:** Machine learning models in financial markets are susceptible to regime shifts, hallucination, and spurious correlations. Giving an ML model direct order-placement authority is unsafe.
- **Decision:** Machine learning models (XGBoost) function strictly as probabilistic filters. They evaluate whether forward returns will exceed round-trip costs and output calibrated probabilities. The Central Decision Arbiter combines this with technical strategies, and the Risk Manager retains ultimate veto power.
- **Consequences:** Prevents rogue model trades; ensures multiple layers of confirmation before any capital is committed.

---

## ADR-007: Risk Engine as Supreme Veto Authority & Mathematical Sizing
- **Status:** Accepted
- **Context:** Traders fail predominantly due to poor risk management, over-allocation, and revenge trading after losses.
- **Decision:** The Risk Manager is the supreme gatekeeper. Position sizes are mathematically derived: $\text{Size} = \frac{\text{Risk Budget}}{\text{Stop Loss Distance} + \text{Fees}}$. The 30% max allocation, 1% risk budget, and 2% daily loss limit are non-negotiable. If sizing cannot safely meet exchange minimum notional, the trade is rejected.
- **Consequences:** Prevents catastrophic drawdowns, protects micro-capital accounts, and guarantees disciplined compounding.

