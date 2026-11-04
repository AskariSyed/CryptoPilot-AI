# Changelog

All notable changes to the CryptoPilot AI project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Planned - Phase 3: Trading Strategy Development
- Strategy base interface and `StrategySignal` schema.
- Strategy A: EMA Trend Following.
- Strategy B: RSI & MACD Confirmation.
- Strategy C: Bollinger Band Mean Reversion.
- Strategy D: Volatility-Adjusted Momentum.
- Strategy E: Multi-Timeframe Trend Confirmation.
- Unit tests for all strategy signal generations and confidence calculations.

---

## [0.1.0-alpha.2] - 2026-11-04

### Added - Phase 2: Technical Indicators & Feature Engineering Engine
- Built pure, zero-lookahead moving averages (`calculate_sma`, `calculate_ema`, `calculate_wma`, `calculate_volume_ma`).
- Built momentum indicators (`calculate_rsi` with Wilder's smoothing, `calculate_stochastic` %K and %D).
- Built trend & volatility indicators (`calculate_macd`, `calculate_bollinger_bands` with bandwidth and %B, `calculate_atr`, `calculate_adx` with +DI/-DI, `calculate_historical_volatility`).
- Built volume indicators (`calculate_obv` with directional accumulation, `calculate_vwap` with typical price weighting and rolling window support).
- Built returns indicators (`calculate_returns`, `calculate_log_returns`).
- Implemented `BaseIndicator` abstract class enforcing input DataFrame validation and warmup period contracts.
- Built `FeaturePipeline` transforming OHLCV into an aligned, zero-lookahead ML feature matrix with warmup pruning.
- Added 69 new unit tests (151 total passing) with zero-lookahead mathematical invariance proofs, achieving 96% test coverage.
- Fully passed static type checks with `mypy` and linting/formatting checks with `ruff`.

---

## [0.1.0-alpha.1] - 2026-11-04

### Added - Phase 1: Foundation & Market Data Collection
- Configured packaging, dependency pinning, and linters in `pyproject.toml` and `requirements.txt`.
- Implemented `cryptopilot.config.Settings` using Pydantic Settings with strict `enable_live_trading=False` enforcement.
- Created typed domain models (`Candle`, `Ticker`, `OrderBook`, `OrderBookLevel`, `MarketMetadata`, `Symbol`, `Timeframe`) in `cryptopilot.data.models`.
- Built resilient asynchronous `ExchangeClient` wrapping CCXT public endpoints with rate-limiting, exponential backoff, retry mechanisms, and UTC normalization.
- Implemented the 4-Stage `CandleValidator` covering timestamp monotonicity, price consistency, duplicate detection, gap detection, and incomplete candle filtering.
- Implemented atomic file-based persistence in `MarketDataStorage` segregating raw (`data/historical/`) from validated (`data/processed/`) datasets.
- Implemented 82 comprehensive unit and integration tests across 8 testing dimensions achieving 97% line coverage.
- Fully passed static type checks with `mypy` and linting/formatting checks with `ruff`.

---

## [0.1.0-alpha.0] - 2026-11-04

### Added
- Comprehensive project roadmap covering all 15 phases (`ROADMAP.md`).
- Master project README (`README.md`).
- Core architectural design and data flow documentation (`docs/ARCHITECTURE.md`).
- Detailed system design and concurrency model (`docs/SYSTEM_DESIGN.md`).
- Complete relational database schema with PostgreSQL/SQLite specifications (`docs/DATABASE_SCHEMA.md`).
- REST API specification with OpenAPI/Swagger conventions (`docs/API_DOCUMENTATION.md`).
- Quantitative specifications for all 5 trading strategies (`docs/TRADING_STRATEGY.md`).
- Quantitative risk management and position sizing mathematical framework (`docs/RISK_MANAGEMENT.md`).
- Event-driven backtester architecture and walk-forward validation guide (`docs/BACKTESTING.md`).
- Machine learning pipeline specification with zero-leakage guarantees (`docs/MACHINE_LEARNING.md`).
- FinBERT news sentiment engine design and time-decay model (`docs/SENTIMENT_ANALYSIS.md`).
- Paper trading virtual execution engine design (`docs/PAPER_TRADING.md`).
- Security architecture and threat model (`docs/SECURITY.md`).
- Comprehensive testing strategy with the 8-Point Method Standard (`docs/TESTING.md`).
- Dockerized deployment guide and disaster recovery plan (`docs/DEPLOYMENT.md`).
- Architecture Decision Records ADR-001 through ADR-007 (`docs/DECISIONS.md`).

