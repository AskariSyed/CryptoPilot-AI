# CryptoPilot AI

[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Type Checked: mypy](https://img.shields.io/badge/type%20checked-mypy-blue.svg)](https://mypy-lang.org/)
[![Status: Phase 0 Architecture](https://img.shields.io/badge/status-Phase%200%20(Docs%20%26%20Arch)-orange.svg)](ROADMAP.md)

**CryptoPilot AI** is a modular, autonomous, AI-powered cryptocurrency spot trading agent engineered for mathematical discipline, zero-lookahead quantitative analysis, risk-first portfolio compounding, and transparent decision-making.

Operating exclusively in **PAPER TRADING** mode in its initial release, CryptoPilot AI provides realistic execution simulation across both a micro-capital portfolio ($30 initial capital, $10 monthly contributions) and an isolated quantitative research environment ($10,000 balance).

---

## Key Features

- **Public Market Data Ingestion:** Modular exchange abstraction built on CCXT. Ingests OHLCV, tickers, and order books for `BTC/USDT`, `ETH/USDT`, and `SOL/USDT` across `1m`, `15m`, `1h`, and `4h` timeframes without requiring private API keys.
- **Pure Indicator Calculation:** Zero-lookahead, mathematically verified implementations of SMA, EMA, RSI, MACD, Bollinger Bands, ATR, ADX, Stochastic, OBV, VWAP, Volatility, and Returns.
- **Multi-Strategy Ensemble:** 5 independent quantitative rule strategies (EMA Trend Following, RSI & MACD Momentum, Bollinger Mean Reversion, Volatility-Adjusted Momentum, and Multi-Timeframe Trend Confirmation).
- **Leak-Free Machine Learning:** Supervised XGBoost predictive pipeline evaluated using purged and embargoed chronological walk-forward splits.
- **Financial News Sentiment:** FinBERT-driven sentiment analysis featuring duplicate content detection, publication decay discounting, and conservative signal weighting.
- **Autonomous Decision Arbiter:** Transparent synthesis of technical signals, ML probabilities, sentiment scores, and market regime states, producing auditable `BUY`, `SELL`, or `HOLD` decisions with natural language rationales.
- **Strict Micro-Capital Risk Engine:** Position sizing dynamically pegged to `Risk Budget / (Stop Loss Distance + Est Fees)`. Strictly enforces:
  - 1% equity risk budget per trade.
  - Maximum 30% single-position portfolio allocation.
  - Maximum 1 simultaneous active position.
  - 2% daily loss circuit breaker with immediate trading halt.
  - Monthly deposit ledgering separate from trading PnL.
  - Automatic compounding of eligible profits without revenge trading.
- **Realistic Paper Trading:** Event-driven virtual execution accounting for exchange maker/taker fees, bid/ask spreads, and order book slippage.
- **Full-Stack Observability:** FastAPI REST endpoints and an interactive React/TypeScript dashboard with clear visual separation between research and micro-capital simulations.

---

## Architecture Overview

CryptoPilot AI is architected as a modular monolith with strictly enforced separation of concerns:

```
src/cryptopilot/
├── config/        # Pydantic v2 application settings & environment validation
├── data/          # CCXT exchange data adapters, candle validation, rate limiting
├── indicators/    # Pure mathematical indicator calculators (zero lookahead)
├── features/      # Time-series feature engineering & normalizers
├── strategies/    # Independent quantitative rule strategies
├── backtesting/   # Event-driven backtester with fee & slippage modeling
├── models/        # XGBoost ML training, calibration, and inference
├── sentiment/     # Financial news ingestion & FinBERT sentiment scoring
├── agent/         # Central autonomous decision arbiter & explainer
├── risk/          # Mathematical risk budget, position sizing, circuit breakers
├── portfolio/     # Cash/equity accounting & monthly contribution ledger
├── execution/     # Virtual paper trading engine & order matching simulator
├── exchange/      # Exchange metadata, precision, and minimum notional helpers
├── database/      # SQLAlchemy 2.0 models, repositories, and Alembic migrations
├── monitoring/    # System health, telemetry, alerts, and structured logging
└── api/           # FastAPI REST application routes and schemas
```

For detailed component designs and data flows, see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and [docs/SYSTEM_DESIGN.md](docs/SYSTEM_DESIGN.md).

---

## Technology Stack

- **Backend Language:** Python 3.12+ (tested on Python 3.13)
- **Framework & Validation:** FastAPI, Pydantic v2
- **Data & Quantitative:** CCXT, Pandas, NumPy
- **Machine Learning:** Scikit-learn, XGBoost
- **Sentiment Analysis:** FinBERT (Hugging Face Transformers / Configurable Adapters)
- **Database & Migrations:** PostgreSQL (Production), SQLite (Unit testing), SQLAlchemy 2.0, Alembic
- **Frontend Dashboard:** React 18, TypeScript, Vite, Tailwind CSS, Lightweight Charts
- **Testing & Quality:** Pytest, Pytest-cov, Pytest-asyncio, Hypothesis, Ruff, MyPy
- **Deployment:** Docker, Docker Compose

---

## Prerequisites

- **Python:** Version 3.12 or 3.13 installed.
- **Node.js:** Version 18+ and npm (for the React dashboard).
- **PostgreSQL:** Version 15+ (optional for local SQLite testing, required for production deployment).
- **Docker & Docker Compose:** (Optional, for containerized execution).

---

## Installation Instructions

### 1. Clone the Repository
```bash
git clone https://github.com/your-username/cryptopilot-ai.git
cd cryptopilot-ai
```

### 2. Set Up Virtual Environment
```bash
python -m venv .venv

# On Windows (PowerShell):
.venv\Scripts\Activate.ps1

# On Linux/macOS:
source .venv/bin/activate
```

### 3. Install Python Dependencies
```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Install Frontend Dependencies (Phase 12)
```bash
cd frontend
npm install
cd ..
```

---

## Environment Configuration

Copy the example environment file and configure your local parameters:

```bash
cp .env.example .env
```

Key environment parameters:
```ini
# Application Mode
CRYPTOPILOT_ENV=development
LOG_LEVEL=INFO

# Trading Mode (Strictly PAPER in initial release)
TRADING_MODE=paper
ENABLE_LIVE_TRADING=false

# Account Environment (small_account or research)
ACCOUNT_TYPE=small_account
INITIAL_CAPITAL=30.0
MONTHLY_CONTRIBUTION=10.0

# Public Exchange Configuration
EXCHANGE_ID=binance
DEFAULT_SYMBOLS=BTC/USDT,ETH/USDT,SOL/USDT
DEFAULT_TIMEFRAMES=1m,15m,1h,4h

# Database Configuration
DATABASE_URL=sqlite+aiosqlite:///./data/cryptopilot_dev.db
# For PostgreSQL: postgresql+asyncpg://user:password@localhost:5432/cryptopilot
```

---

## Database Setup

To run schema migrations using Alembic:

```bash
# Run latest database migrations
alembic upgrade head
```

---

## Running the Application

### Running the FastAPI Backend
```bash
uvicorn cryptopilot.api.main:app --host 0.0.0.0 --port 8000 --reload
```
Interactive API documentation will be available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Starting the React Dashboard
```bash
cd frontend
npm run dev
```
Access the dashboard at `http://localhost:5173`.

---

## Running Tests

Unit tests are mandatory for all components. To execute the test suite with coverage reporting:

```bash
# Run all unit tests
pytest

# Run tests with detailed coverage report
pytest --cov=cryptopilot --cov-report=term-missing --cov-report=html

# Run property-based tests (Hypothesis)
pytest tests/unit/test_risk_property.py
```

Code quality and linting checks:
```bash
# Run Ruff linting
ruff check src tests

# Run Ruff formatting check
ruff format --check src tests

# Run MyPy static type checks
mypy src
```

---

## Running the Backtesting Engine

To run an event-driven backtest on historical market data:

```bash
python -m cryptopilot.backtesting.run --symbol BTC/USDT --timeframe 1h --start 2024-01-01 --end 2024-12-31 --initial-capital 10000
```

---

## Starting Paper Trading

To initiate the autonomous paper trading loop with live public data:

```bash
python -m cryptopilot.agent.runner --account-type small_account --symbols BTC/USDT,ETH/USDT,SOL/USDT
```

---

## Security Instructions

1. **No Live Execution Keys:** The system runs exclusively in paper trading mode. Never input API keys with withdrawal or live trade execution permissions.
2. **Environment Protection:** Never commit `.env` or sensitive configuration files to version control.
3. **Audit Trails:** All simulated orders, balance changes, and risk vetoes are recorded in immutable audit logs.
4. **Failsafe Circuit Breakers:** If data feeds become stale or the 2% daily loss limit is hit, all trading is halted immediately and falls back to `HOLD`.

---

## Troubleshooting

- **CCXT Rate Limits:** If receiving HTTP 429 errors from public exchange endpoints, check `config.yaml` to ensure `ENABLE_RATE_LIMIT=true` and adjust `REQUEST_TIMEOUT_MS`.
- **Database Connection Issues:** Verify your PostgreSQL service is running or check write permissions for SQLite in `./data/`.
- **Stale Market Data Warnings:** Ensure your system clock is synchronized via NTP (UTC).

---

## Development Roadmap & Current Status

Current Status: **Phase 0: Requirements, Architecture & Documentation (Completed)**

Track detailed implementation progress and acceptance criteria across all 15 phases in [ROADMAP.md](ROADMAP.md).
See recent changes in [docs/CHANGELOG.md](docs/CHANGELOG.md).
