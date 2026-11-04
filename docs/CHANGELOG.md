# Changelog

All notable changes to the CryptoPilot AI project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Planned - Phase 7: Autonomous Decision Engine
- Strict decision schema definition (`Symbol`, `Decision`, `Confidence`, `Signals`, `ML`, `Sentiment`, `Risk`, `Rationale`).
- Central Decision Arbiter combining technical, ML, and sentiment inputs.
- Market regime classifier (Trending Bull, Trending Bear, Ranging, High Volatility).
- Default-to-HOLD safety state on stale data, conflicting signals, or model degradation.
- Transparent explanation generator producing interpretable rationales for every decision.

---

## [0.1.0-alpha.6] - 2026-11-04

### Added - Phase 6: Sentiment Analysis Engine
- Implemented `NewsArticle`, `SentimentScore`, and `AggregatedSentiment` Pydantic models with UTC normalization, polarity, confidence, and bounded probability outputs.
- Implemented `NewsDeduplicator` utilizing SHA-256 cryptographic title hashing and Jaccard token similarity ($\ge 0.80$) with TTL-based pruning and dynamic cache size constraints to eliminate duplicate syndicated wire stories.
- Implemented `AssetRelevanceFilter` with crypto ticker symbol extraction (`BTC/USDT`, `ETH/USDT`, `SOL/USDT`), title and content weighting, and macro cryptocurrency fallback relevance scoring.
- Implemented `RuleBasedFinancialSentimentClassifier` with curated cryptocurrency lexicon, contextual negation handling ("not", "never", "failed", "unlikely"), and calibrated softmax output probabilities.
- Implemented `FinBERTClassifier` with lazy transformer pipeline loading, strict CPU execution fallback, and graceful degradation to rule-based lexicon when optional dependencies are absent.
- Implemented `ExponentialTimeDecay` computing realistic predictive value evaporation ($t_{1/2} = 2.0\text{h}$, cutoff at $24.0\text{h}$) with future clock-drift protections.
- Implemented `SentimentAggregator` calculating composite time-decayed and relevance-weighted polarity scores, active news volume counters, stale period tagging, and already-priced-in discounts (50% reduction when asset price has already moved $\ge 5\%$).
- Implemented `BaseNewsAdapter`, `MockNewsAdapter` for deterministic testing, and `CryptoPanicAdapter` with async `aiohttp` requests, currency filtering, and timeout/error fallbacks.
- Implemented `SentimentEngine` orchestrator integrating ingestion, deduplication, relevance tagging, NLP scoring, and per-symbol query caching.
- Created 31 unit tests across 7 test suites achieving 92% sentiment code coverage (295 total project tests passing, 96% overall project coverage).
- Verified complete zero-error compliance across `ruff check`, `ruff format`, and `mypy` strict type checking across 49 source files.

---

## [0.1.0-alpha.5] - 2026-11-04

### Added - Phase 5: Machine Learning Prediction Engine
- Implemented `TargetLabeler` and `TargetConfig` generating cost-adjusted forward return classification targets ($R_{t, H} > \theta_{\text{fees+edge}}$) with boundary pruning of trailing unobservable horizon bars.
- Implemented `PurgedTimeSeriesSplitter` supporting scikit-learn cross-validation protocol with strict chronological partitioning, forward-return purging, and 24-bar embargo buffers to eliminate data leakage.
- Implemented `MLFeatureTransformer` with selective numeric column extraction, metadata exclusion, median imputation, and chronological `StandardScaler` / `RobustScaler` fitting strictly on training partitions.
- Implemented `XGBoostPredictor` with supervised XGBoost classifier training, class imbalance weighting (`scale_pos_weight`), PR-AUC, ROC-AUC, Brier score, and log-loss evaluation against naive base-rate benchmarks.
- Implemented `MLInferenceEngine` delivering calibrated bullish probabilities, confidence scores ($|P - 0.5| \times 2$), feature attributions, and deterministic safety fallbacks ($P = 0.50$, zero confidence) on missing/corrupt data.
- Implemented `ModelArtifactManager` providing atomic JSON/Joblib model serialization, version tracking, reproducibility metadata, and integrity validation.
- Built 28 comprehensive unit tests across 6 test modules achieving 94% ML code coverage (264 total project tests passing, 96% overall project coverage).
- Passed all `ruff` linting/formatting and `mypy` strict type checking with zero errors across 40 source files.

---

## [0.1.0-alpha.4] - 2026-11-04

### Added - Phase 4: Historical Backtesting Engine
- Implemented typed backtest models (`SimulatedOrder`, `SimulatedPosition`, `Trade`, `EquityPoint`, `PerformanceMetrics`, `BenchmarkComparison`, `BacktestResult`).
- Implemented `SimulatedExecutionEngine` with realistic quadratic volume-dependent slippage, bid/ask half-spread penalties, taker commissions (0.1%), and conservative intrabar bracket order evaluation (Stop-Loss prioritized over Take-Profit on dual-touch candles).
- Implemented `SimulatedPortfolio` with strict micro-capital constraints ($30 capital, $10 monthly contribution ledger separation from trading PnL, 1% risk budget position sizing, 30% max equity allocation cap, and 2% daily loss circuit breaker).
- Implemented `PerformanceMetricsCalculator` computing Net Return, CAGR, Win Rate, Profit Factor, Max Drawdown and duration, Sharpe ratio, Sortino ratio, Expectancy, and Fee drag with zero-division protection.
- Implemented `BenchmarkCalculator` generating passive comparisons against Buy & Hold BTC, Buy & Hold ETH, and risk-free Cash baseline.
- Implemented `WalkForwardPartitioner` supporting rolling and expanding cross-validation folds with strictly enforced purge and embargo windows to prevent lookahead leakage.
- Implemented `BacktestEngine` orchestrating zero-lookahead, bar-by-bar event simulation, intrabar bracket resolution, multi-timeframe alignment, and automatic final bar force-close.
- Built 46 comprehensive unit tests across 7 test suites achieving 98% backtesting line coverage (236 total project tests passing, 97% overall line coverage).
- Passed all `ruff` linting/formatting and `mypy` strict type checking with zero errors across 33 source files.

---

## [0.1.0-alpha.3] - 2026-11-04

### Added - Phase 3: Trading Strategy Development
- Implemented `StrategySignal` Pydantic model with strict validation for `BUY`, `SELL`, and `HOLD` actions, confidence scores, suggested stop-loss, take-profit, and human-readable rationales.
- Implemented `BaseStrategy` abstract base class enforcing DataFrame structural validation, observation sufficiency checks, and standardized signal factory methods.
- Implemented **Strategy A: EMA Trend Following** (`EMATrendFollowingStrategy`) featuring dual fast/slow EMA crossovers, ADX trend strength filtering, ATR-based dynamic stop-loss, and multi-factor confidence scoring.
- Implemented **Strategy B: RSI & MACD Confirmation** (`RSIMACDConfirmationStrategy`) requiring synchronous convergence between MACD histogram crossover, RSI non-overbought zone (50-70), 50-EMA trend alignment, and volume moving average confirmation.
- Implemented **Strategy C: Bollinger Band Mean Reversion** (`BollingerMeanReversionStrategy`) exploiting oversold lower band bounces with strict ADX regime filtering (< 20 ranging market veto) and middle band take-profit targets.
- Implemented **Strategy D: Volatility-Adjusted Momentum** (`VolatilityAdjustedMomentumStrategy`) detecting volatility compression (Bollinger inside Keltner squeeze) followed by expansion breakout and trend momentum.
- Implemented **Strategy E: Multi-Timeframe Trend Confirmation** (`MultiTimeframeTrendStrategy`) combining 1h macro regime direction (Price > 50 EMA, MACD > 0) with 15m micro pullback/resumption entries and volume confirmation.
- Created 39 comprehensive unit tests across 6 test modules covering all 8 testing dimensions, achieving 97% strategy code coverage (190 total tests passing, 96% overall project coverage).
- Validated full static typing with `mypy` and strict code formatting/linting with `ruff`.

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

