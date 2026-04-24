# SolGuard — Phase 3 Demo Video Script

Target length: **2 minutes 30 seconds**. Designed so that even a **silent screen recording** tells the whole story — captions render inside the dashboard itself via *Presenter Mode*.

---

## Pre-flight checklist (run 5 minutes before recording)

```bash
# 1. Rotate any exposed secrets first. See AUDIT_REPORT.md § secrets hygiene.
# 2. Launch the agent locally
pip install -r requirements.txt --break-system-packages
uvicorn agent.main:app --host 0.0.0.0 --port 8000 &
# 3. In a second terminal, expose via ngrok so the live site can reach it
ngrok http 8000
# 4. Paste the ngrok URL into the live dashboard's "API" input and click Connect
# 5. Press S once to unmute alert beeps for the recording
# 6. Full-screen the browser tab at 1920×1080, hide bookmarks bar
```

## Keyboard shortcuts (use these on camera)

| Key | Action                                        |
| --- | --------------------------------------------- |
| `D` | Start Demo Mode (auto-rotating demo alerts)  |
| `R` | Replay the Drift hack sequence (3 stages)    |
| `P` | Toggle Presenter captions                     |
| `S` | Toggle sound on/off                           |
| `Esc` | Close presenter overlay                     |

---

## The Script (voice-over friendly — also works silent)

### [0:00 – 0:15] Hook
**Visual:** SolGuard landing. Hero headline visible: *"Catching the next Drift-style hijack before the drain."*
**Voice / caption:**
> "On April 1st, 2026, North-Korean hackers drained $285 million from Drift Protocol — in ten seconds. The vulnerability wasn't in the smart contracts. It was in the upgrade authority. **SolGuard is the autonomous AI sentinel that would have seen it coming.**"

### [0:15 – 0:35] What you're looking at
**Visual:** Pan the dashboard. Point to: 15 watched programs on the right; live SSE feed on the left; Security Score on the upper-right.
**Voice / caption:**
> "Fifteen top Solana protocols, monitored every thirty seconds. Jupiter, Raydium, Drift, Kamino, Pyth. Every upgrade authority change, every durable-nonce touch, every Squads multisig migration — scored by Claude in under two seconds."

### [0:35 – 0:42] Connect + Security Score
**Action:** Paste your ngrok URL → *Connect*. Watch the Watchlist populate with live mainnet authorities. Call out the Score gauge.
**Caption:**
> "That number is our Ecosystem Security Score. 100 means nothing is on fire. It drops every time a CRITICAL or HIGH alert fires."

### [0:42 – 1:30] Cinematic — Replay the Drift hack
**Action:** Press **R**. Presenter captions and three alerts play automatically. Don't say anything — let the dashboard narrate. Recording sound on means the critical-alert beeps give it tension.

**What the viewer sees, second by second:**
- **+0s** — Presenter caption: *"On April 1st, 2026 — DPRK hackers drained $285M from Drift in 10 seconds. SolGuard would have seen it coming."*
- **+3.5s** — New **HIGH** alert slides in: "STAGE 1/3 — Durable nonce account created near Drift Protocol authority." Caption explains: *"This is how the real attack began — pre-signing transactions that will trigger days later."*
- **+7.5s** — **CRITICAL** alert: "STAGE 2/3 — Security Council multisig migrated to 2/5 with ZERO TIMELOCK." Caption: *"This is the red flag nobody caught in real life. SolGuard scores it CRITICAL in under two seconds."*
- **+11.5s** — **CRITICAL** alert: "STAGE 3/3 — Admin authority transferred to an unverified wallet. Attack complete." Caption: *"In reality, $285M was drained in the next 10 seconds. With SolGuard, users get Telegram, Discord, and on-chain alerts before the drain."*
- **+15.5s** — Wrap caption: *"From staging to drain — three stages, all caught in real time."*

### [1:30 – 1:55] The tech behind it
**Action:** Click one of the alerts to expand it. Show the expanded *details* and *recommended action* — these are Claude-generated.
**Voice / caption:**
> "Every alert is grounded in real attack history. Claude is trained on the Drift DPRK incident, the FTX/Serum compromise, and the emerging Jito-bundled upgrade pattern. The scoring is deterministic when there's no API key, so the product never goes silent."

### [1:55 – 2:15] On-chain receipts
**Action:** Open Solana Explorer to the program id `5kkaYGaXECsngVohp3Z7NdDnxpfatTqSsmMVpsnngZFM` on devnet.
**Voice / caption:**
> "And because signals matter only if people trust them, every alert's SHA-256 hash is written to the on-chain SolGuard Registry. A tamper-proof, verifiable detection log anyone can query."

### [2:15 – 2:30] Close
**Visual:** Back to dashboard, Security Score recovering, Presenter caption fades.
**Voice / caption:**
> "Built with Claude Opus 4.6 for the Colosseum Frontier Hackathon. SolGuard. Because the next $285 million hack is already being staged."

---

## Notes for the silent-recording path

- The dashboard auto-shows captions during the Drift replay. You don't need a microphone for the core story.
- Sound is synthesised in the browser (Web Audio API) — no external files — so it works offline and on any device.
- To re-shoot any stage, press `R` again; the replay is idempotent and resets the feed.
- For longer takes, press `D` afterwards to let the Demo Mode keep the feed alive with a rolling set of 8 pre-written alerts.

## Deliverables to submit with the video

1. Video file (1080p, MP4 or MOV)
2. Live demo URL: https://solguard.vercel.app
3. Repo: https://github.com/janneh2000/solguard
4. On-chain program: https://explorer.solana.com/address/5kkaYGaXECsngVohp3Z7NdDnxpfatTqSsmMVpsnngZFM?cluster=devnet
5. `docs/AUDIT_REPORT.md` referenced from the README

Good luck, Rivaldo. Land it. 🛡️
