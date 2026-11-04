# CryptoPilot AI: REST API Documentation

## 1. Overview & API Conventions

CryptoPilot AI provides a high-performance REST API powered by **FastAPI** and validated via **Pydantic v2**.
- **Base URL:** `/api/v1`
- **Specification:** OpenAPI 3.1 compatible.
- **Interactive Documentation:** Available at `/docs` (Swagger UI) and `/redoc` (ReDoc).
- **Authentication:** Bearer token (`Authorization: Bearer <API_SECRET>`) required for control, paper deposit injection, and backtesting trigger endpoints. Telemetry and public market read-only endpoints are open in local environments.
- **Timestamp Standard:** Strict ISO 8601 UTC (e.g. `2026-11-04T09:30:00Z`).
- **Response Format:** All responses adhere to the standard envelope structure:

```json
{
  "success": true,
  "data": { ... },
  "error": null,
  "timestamp": "2026-11-04T09:30:00Z"
}
```

---

## 2. API Endpoints Specification

### 2.1 System & Telemetry

#### `GET /api/v1/health`
Health check and daemon heartbeat.
- **Response `200 OK`**:
```json
{
  "success": true,
  "data": {
    "status": "HEALTHY",
    "version": "0.1.0",
    "uptime_seconds": 86420,
    "trading_mode": "paper",
    "database": "CONNECTED",
    "exchange_connectivity": "CONNECTED",
    "circuit_breaker_active": false
  }
}
```

#### `GET /api/v1/status`
Operational status summary across active symbols and background tasks.

---

### 2.2 Market Data

#### `GET /api/v1/market/candles`
Retrieve historical validated OHLCV candles.
- **Query Parameters:**
  - `symbol` (str, required): e.g. `BTC/USDT`
  - `timeframe` (str, required): `1m`, `15m`, `1h`, `4h`
  - `limit` (int, default 100, max 1000)
- **Response `200 OK`**:
```json
{
  "success": true,
  "data": {
    "symbol": "BTC/USDT",
    "timeframe": "1h",
    "candles": [
      {
        "timestamp": "2026-11-04T08:00:00Z",
        "open": 68420.50,
        "high": 68950.00,
        "low": 68310.25,
        "close": 68800.00,
        "volume": 412.85,
        "is_closed": true
      }
    ]
  }
}
```

#### `GET /api/v1/market/ticker`
Returns current public bid, ask, and 24h metrics for a symbol.

---

### 2.3 Portfolio & Accounting

#### `GET /api/v1/portfolio`
Returns current portfolio balances, equity, and separated deposit accounting.
- **Query Parameters:**
  - `account_type` (str, optional, default `small_account`): `small_account` or `research`
- **Response `200 OK`**:
```json
{
  "success": true,
  "data": {
    "portfolio_id": "small_account_01",
    "account_type": "small_account",
    "initial_capital": 30.00,
    "total_deposits": 10.00,
    "total_cash": 22.40,
    "invested_capital": 18.50,
    "current_equity": 40.90,
    "realized_pnl": 0.90,
    "unrealized_pnl": 0.00,
    "total_fees_paid": 0.08,
    "net_trading_return_pct": 2.25,
    "max_drawdown_pct": 0.65,
    "is_trading_halted": false
  }
}
```

#### `GET /api/v1/portfolio/history`
Returns historical equity curve snapshots for charting.

---

### 2.4 Positions & Orders

#### `GET /api/v1/positions`
Returns active positions (max 1 active under micro-account rules) or closed position history.
- **Query Parameters:**
  - `status` (str, optional): `OPEN`, `CLOSED`

#### `GET /api/v1/orders`
Returns list of virtual paper trading orders with lifecycle status.

#### `GET /api/v1/trades`
Returns execution trade history including exact fees and simulated slippage.

---

### 2.5 Autonomous Decisions & Explainability

#### `GET /api/v1/decisions`
Returns recent autonomous trading decisions with transparent rationale logs.
- **Query Parameters:**
  - `limit` (int, default 20)
- **Response `200 OK`**:
```json
{
  "success": true,
  "data": [
    {
      "decision_id": "6a9e1e24-4f81-49b8-a6d1-447a1188d18b",
      "symbol": "BTC/USDT",
      "timestamp": "2026-11-04T08:00:00Z",
      "decision": "BUY",
      "confidence": 0.78,
      "market_regime": "TRENDING_BULL",
      "strategy_signals": [
        {
          "strategy_id": "ema_trend",
          "signal": "BUY",
          "confidence": 0.85,
          "rationale": "EMA 20 crossed above EMA 50 with ADX at 28.4"
        },
        {
          "strategy_id": "rsi_macd",
          "signal": "BUY",
          "confidence": 0.72,
          "rationale": "MACD histogram turned positive with RSI at 54.2"
        }
      ],
      "ml_prediction": {
        "model_version": "xgb_btc_1h_v1.0.0",
        "predicted_label": 1,
        "probability": 0.68,
        "expected_net_return_pct": 1.45
      },
      "sentiment": {
        "sentiment_score": 0.35,
        "decayed_score": 0.28,
        "headline_count": 4
      },
      "risk_assessment": {
        "approved": true,
        "calculated_position_size_usd": 9.00,
        "position_size_asset": 0.0001308,
        "stop_loss_price": 67200.00,
        "risk_amount_usd": 0.30
      },
      "explanation": "Decision to BUY BTC/USDT approved. Strong trend alignment across EMA and MACD confirmed by XGBoost model (68% bullish probability). Risk manager approved allocation of $9.00 (22.0% equity) with $0.30 risk budget."
    }
  ]
}
```

---

### 2.6 Risk & Circuit Breakers

#### `GET /api/v1/risk/status`
Returns real-time risk parameters:
- Daily realized loss vs 2% limit.
- Active position allocation percentage.
- Circuit breaker state.

#### `POST /api/v1/control/emergency-halt`
**Admin Endpoint**: Manually halts trading immediately and cancels all pending virtual orders.

#### `POST /api/v1/control/deposit`
**Admin Endpoint**: Records a simulated monthly capital injection (e.g. $10) into the paper trading portfolio.

