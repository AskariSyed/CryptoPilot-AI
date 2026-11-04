# CryptoPilot AI: Security & Threat Modeling

## 1. Security Architecture Principles

CryptoPilot AI is designed with defensive depth, ensuring that even under severe software faults, invalid inputs, or external API exploits, financial capital cannot be drained or compromised.

---

## 2. Threat Modeling & Mitigations

| Threat Vector | Risk Scenario | Architectural Mitigation |
|---|---|---|
| **Accidental Real-Money Orders** | System routes trades to a real exchange account with real funds. | **Hard-Coded Barrier:** Live trading execution is disabled at the code level. The CCXT exchange adapter is initialized without private API keys, only calling public read endpoints. |
| **Withdrawal Key Theft** | Exchange credentials exposed and funds stolen. | **Absolute Zero-Withdrawal Mandate:** The architecture explicitly rejects any configuration or key with withdrawal capabilities. API keys are completely unnecessary for public paper trading. |
| **Credential Leakage in Logs** | Secrets printed to stdout or log files. | Structured logging filter sanitizes all strings against environment variables, tokens, and authorization headers. |
| **Unbounded Prompt Injection / Hallucination** | An LLM generates an extreme position size or overrides risk rules. | **Architectural Isolation:** AI/LLM components have **zero** execution authority. All orders must pass deterministic Python risk constraints (`Pydantic` validation, mathematical sizing formula, 30% cap). |
| **Stale / Spoofed Market Data** | Attackers feed artificial candle flash crashes. | Strict sanity checks verify $High \ge Low$, monotonic timestamps, and cross-reference multiple exchange feeds if necessary. Candles older than tolerance are rejected. |
| **Unauthorized Administrative Actions** | Attackers trigger fake deposits or halt daemon remotely. | Administrative FastAPI endpoints require Bearer token authentication with SHA-256 constant-time comparison. |

---

## 3. Secret Management & Configuration Hygiene

1. `.gitignore` explicitly prevents `.env`, `.pem`, `.key`, and database files from being committed to git.
2. `.env.example` provides a sanitized, fully documented template for environment variables.
3. System settings are loaded into strictly typed Pydantic models with validation at application startup.

---

## 4. Graceful & Safe Shutdown Protocol

When receiving `SIGINT` (Ctrl+C) or `SIGTERM`:
1. The background scheduler stops polling new candle cycles.
2. Active paper trading orders in `PENDING` state are cleanly transitioned to `CANCELED`.
3. Open database connections and sessions are committed or rolled back cleanly.
4. Telemetry logs record the clean shutdown event.

