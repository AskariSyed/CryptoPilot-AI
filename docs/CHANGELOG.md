# Changelog

All notable changes to the CryptoPilot AI project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Planned - Phase 1: Foundation & Market Data Collection
- Setup of `pyproject.toml`, dependencies, and linting tools (`ruff`, `mypy`).
- Core Pydantic configuration (`cryptopilot.config`).
- Base domain models (`Candle`, `Ticker`, `OrderBook`, `Symbol`, `Timeframe`).
- CCXT market data ingestion with exponential backoff and rate-limiting.
- Data validation pipeline (timestamp monotonicity, gap detection, duplicate handling).
- Unit and mock integration test suite.

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
