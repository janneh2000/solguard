<p align="center">
  <img src="docs/solguard-banner.svg" alt="SolGuard" width="600">
</p>

<h1 align="center">SolGuard</h1>
<p align="center">
  <strong>Autonomous AI Sentinel for Solana Program Upgrades</strong>
</p>

<p align="center">
  <a href="#how-it-works">How It Works</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#architecture">Architecture</a> •
  <a href="#api-reference">API</a> •
  <a href="#demo">Demo</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Solana-Mainnet-9945FF?style=flat-square&logo=solana" />
  <img src="https://img.shields.io/badge/AI-Claude_Sonnet_4-D97706?style=flat-square&logo=anthropic" />
  <img src="https://img.shields.io/badge/Python-3.13-3776AB?style=flat-square&logo=python" />
  <img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" />
  <img src="https://img.shields.io/badge/Hackathon-Colosseum_Frontier-FF6B35?style=flat-square" />
</p>

---

## The Problem

Every Solana program is **upgradeable by default**. The holder of a program's *upgrade authority* key can redeploy new bytecode at any time — silently replacing the code that controls billions in user funds.

This is exactly what happened during the **FTX collapse** (November 2022), when Serum's upgrade authority was compromised, putting the entire Solana DeFi ecosystem at risk.

**Today, there is no real-time monitoring system** that watches for these authority changes across major protocols and alerts the community before damage is done.

## The Solution

**SolGuard** is an autonomous AI sentinel that monitors Solana program upgrade authority changes in real time and uses Claude AI to assess the risk of each event.

It watches the upgrade authorities of major DeFi protocols on Solana mainnet and instantly alerts users via a live dashboard, Discord, and Telegram when something changes — with an AI-powered risk assessment explaining *what happened* and *what to do about it*.

## How It Works

```
┌─────────────────────────────────────────────────────────────────┐
│                        SOLANA MAINNET                           │
│  Jupiter · Raydium · Orca · Kamino · Drift · Marinade          │
└──────────────────────────┬──────────────────────────────────────┘
                           │
              ┌────────────┴────────────┐
              │                         │
     ┌────────▼────────┐     ┌─────────▼─────────┐
     │  Polling Engine  │     │  Helius Webhooks   │
     │  (every 30s)     │     │  (real-time push)  │
     └────────┬─────────┘     └─────────┬──────────┘
              │                         │
              └────────────┬────────────┘
                           │
                  ┌────────▼────────┐
                  │  Event Router   │
                  │  SET_AUTHORITY   │
                  │  UPGRADE         │
                  │  INIT_BUFFER     │
                  └────────┬────────┘
                           │
                  ┌────────▼────────┐
                  │  Claude AI      │
                  │  Risk Engine    │
                  │                 │
                  │  → CRITICAL     │
                  │  → HIGH         │
                  │  → MEDIUM       │
                  │  → LOW          │
                  └────────┬────────┘
                           │
           ┌───────────────┼───────────────┐
           │               │               │
    ┌──────▼──────┐ ┌──────▼──────┐ ┌──────▼──────┐
    │  Dashboard  │ │  Discord    │ │  Telegram   │
    │  (SSE live) │ │  Webhook    │ │  Bot        │
    └─────────────┘ └─────────────┘ └─────────────┘
```

### Detection Methods

1. **Polling Engine** — Reads the ProgramData PDA of each watched program every 30 seconds via Solana RPC, extracting the current upgrade authority from the raw account data layout.

2. **Helius Webhooks** — Receives real-time push notifications for `SET_AUTHORITY`, `UPGRADE`, and `INITIALIZE_BUFFER` transaction types on watched programs.

### AI Risk Scoring

Every detected event is sent to **Claude AI** with full context:

- Program ID, old authority, new authority, transaction signature
- Known high-risk patterns (unknown wallet, no governance vote, market volatility)
- Historical context from the Solana ecosystem

Claude returns a structured risk assessment with a severity level, human-readable summary, technical details, and recommended actions for protocol users.

## Watched Protocols (15 programs)

| Protocol | Program ID | Category |
|----------|-----------|----------|
| Jupiter v6 | `JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4` | DEX |
| Jupiter Perps | `PERPHjGBqRHArX4DySjwM6UJHiR3sWAatqfdBS2qQJu` | Perps |
| Raydium AMM | `675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8` | DEX |
| Raydium CLMM | `CAMMCzo5YL8w4VFF8KVHr7wifgk7jfhELM25LNNrsEgc` | DEX |
| Orca Whirlpool | `whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc` | DEX |
| Meteora DLMM | `LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo` | DEX |
| Kamino Lending | `KLend2g3cP87fffoy8q1mQqGKjrL1AMLkohkowi9oec` | Lending |
| Marginfi | `MFv2hWf31Z9kbCa1snEPYctwafyhdvnV7FZnsebVacA` | Lending |
| Drift Protocol | `dRiftyHA39MWEi3m9aunc5MzRF1JYuBsbn6VPcn33UH` | Perps |
| Marinade Finance | `MarBmsSgKXdrN1egZf5sqe1TMai9K1rChYNDJgjq7aD` | Staking |
| Sanctum (Infinity) | `5ocnV1qiCgaQR8Jb8xWnVbApfaygJ8tNoZfgPwsgx9kx` | Staking |
| PumpFun | `6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P` | Launchpad |
| Pyth Oracle | `FsJ3A3u2vn5cTVofAjvy6y5kwABJAqYWpe4975bi2epH` | Oracle |
| Wormhole | `worm2ZoG2kUd4vFXhvjh93UUH596ayRfgQ2MgjNMTth` | Bridge |
| Squads v4 | `SQDS4ep65T869zMMBKyuUq6aD6EgTu8psMjkvj52pCf` | Governance |

## Quick Start

### Prerequisites

- Python 3.11+
- [Anthropic API key](https://console.anthropic.com/) (for AI risk scoring)
- [Helius API key](https://helius.dev/) (for RPC + webhooks)

### Local Setup

```bash
# Clone
git clone https://github.com/janneh2000/solguard.git
cd solguard

# Environment
cp .env.example .env
# Edit .env with your API keys

# Install dependencies
pip install -r requirements.txt

# Run the agent
uvicorn agent.main:app --reload --port 8000

# Open the dashboard
open dashboard/index.html
```

### With Docker

```bash
cp .env.example .env
# Edit .env with your API keys

docker compose up --build
```

### Expose for Helius Webhooks

```bash
ngrok http 8000
# Copy the HTTPS URL → set as your Helius webhook endpoint
# Webhook path: https://your-ngrok-url/webhooks/helius
```

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check + agent status |
| `/api/watchlist` | GET | Current watchlist with authority info |
| `/api/alerts` | GET | Historical alerts (query: `?limit=50&risk_level=CRITICAL`) |
| `/api/stats` | GET | Dashboard statistics |
| `/api/stream` | GET | SSE real-time event stream |
| `/api/trigger-test` | POST | Simulate an authority change for demo |
| `/webhooks/helius` | POST | Helius webhook receiver |

## Architecture

```
solguard/
├── agent/
│   ├── main.py                 # FastAPI app, polling loop, SSE, webhooks
│   ├── claude_engine.py        # Claude AI risk scoring engine
│   ├── database.py             # SQLite persistent alert storage
│   ├── metrics.py              # Prometheus metrics
│   ├── onchain_writer.py       # Bridge to on-chain Anchor registry
│   └── watchers/
│       └── upgrade_authority.py # Solana PDA reader, watchlist, Squads detection
├── programs/
│   └── solguard-registry/
│       ├── Cargo.toml
│       └── src/lib.rs          # Anchor program: on-chain alert registry
├── dashboard/
│   └── index.html              # Real-time monitoring dashboard (Vercel-ready)
├── scripts/
│   └── setup_telegram.sh       # Telegram bot setup helper
├── docs/
│   └── solguard-banner.svg     # Project banner
├── Anchor.toml                 # Anchor configuration
├── docker-compose.yml
├── Dockerfile
├── vercel.json
├── requirements.txt
└── .env.example
```

## Key Features

- **15 DeFi protocols** monitored on Solana mainnet
- **Dual detection**: Helius webhooks (real-time push) + RPC polling (every 30s)
- **Claude AI risk scoring** with Solana-specific exploit pattern knowledge
- **Squads multisig detection** — automatically identifies security upgrades vs threats
- **On-chain alert registry** (Anchor program) — immutable, verifiable detection history
- **Live dashboard** with SSE streaming, expandable alerts, demo mode
- **Multi-channel alerts**: Discord webhooks, Telegram Bot API
- **SQLite persistence** with WAL mode for fast writes

## Tech Stack

- **Runtime**: Python 3.13, FastAPI, Uvicorn
- **AI**: Claude Sonnet 4 via Anthropic API
- **Blockchain**: Solana mainnet via Helius RPC
- **On-chain**: Anchor framework (Rust) for alert registry program
- **Real-time**: Helius webhooks + Server-Sent Events (SSE)
- **Storage**: SQLite (WAL mode) + on-chain PDAs
- **Security**: Squads v3/v4 multisig detection
- **Monitoring**: Prometheus metrics
- **Notifications**: Discord webhooks, Telegram Bot API
- **Infrastructure**: Docker, Vercel, ngrok

## Demo

### Trigger a Test Alert

```bash
curl -X POST http://localhost:8000/api/trigger-test
```

This simulates a suspicious authority change on Jupiter v6, triggering the full pipeline: event detection → Claude AI analysis → dashboard update → Discord/Telegram notification.

## Roadmap

- [x] On-chain alert registry (Anchor program for immutable alert history)
- [x] Squads multisig detection (automatic security upgrade recognition)
- [x] Expanded watchlist (15 major protocols across DEX, lending, staking, oracles)
- [ ] Deploy registry program to devnet/mainnet
- [ ] Governance vote cross-referencing (Realms, Squads proposals)
- [ ] Historical authority change timeline per program
- [ ] Multi-chain support (Ethereum, Base, Arbitrum)
- [ ] Community-driven watchlist submissions via on-chain voting
- [ ] Browser extension for real-time alerts
- [ ] Bytecode diffing on UPGRADE events

## Built For

**Colosseum Frontier Hackathon** (April 6 – May 11, 2026)

Track: Security & Infrastructure

## License

MIT — see [LICENSE](LICENSE) for details.

---

<p align="center">
  Built with 🛡️ by <a href="https://github.com/janneh2000">Alie Rivaldo Janneh</a>
</p>
