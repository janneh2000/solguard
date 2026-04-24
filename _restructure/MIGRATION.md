# Migration Playbook — Monorepo → 3-Repo Architecture

Read this end-to-end before running any commands. Each stage has a rollback.

**Do not start until Phase 3 is submitted.** The current `~/Desktop/solguard/` repo is your hackathon submission. This migration must not disturb it until after Sunday.

---

## Stage 0 — Lock the Phase 3 snapshot (5 min)

From `~/Desktop/solguard`:

```bash
# Make sure everything is committed + pushed first
git status                # must be clean
git push origin main

# Tag the submission — this is your rollback point forever
git tag -a phase3-submission -m "Phase 3 hackathon submission (v2 audit pass)"
git push origin phase3-submission
```

If anything in this migration goes sideways, you can always do:

```bash
git reset --hard phase3-submission
```

and be back at a recordable state.

---

## Stage 1 — Reserve the umbrella names (15 min, optional)

You chose "SolGuard-visible, xguard dormant". So this is just land-grabbing to stop someone else taking the names:

1. **GitHub org.** Go to https://github.com/organizations/new → create `xguard` (free plan is fine). You don't migrate anything yet. Repos stay under `janneh2000`.
2. **Domain.** Check availability for `xguard.xyz`, `xguard.dev`, `xguard.io` on Namecheap or similar. Register one. Point it nowhere for now.
3. **Do nothing else.** No branding changes, no README edits, nothing that affects the hackathon submission.

Skip this stage entirely if you want — it costs ~$20/yr for the domain and zero for the org. Purely defensive.

---

## Stage 2 — Create the three new empty GitHub repos (5 min)

On github.com, create (under `janneh2000` for now):

| Repo name              | Visibility | Description                                                                      |
|------------------------|------------|----------------------------------------------------------------------------------|
| `solguard-core`        | **Public** | Autonomous AI sentinel for Solana program upgrades — open-source engine          |
| `solguard-dashboard`   | Private    | Hosted dashboard for SolGuard alerts (enterprise UI)                              |
| `solguard-notifiers`   | Private    | HMAC-authenticated alert fanout — Telegram, Discord, future channels              |

Don't add README, LICENSE, or .gitignore via GitHub — we're pushing them from the scaffold. Leave the repos empty.

Copy the three SSH URLs. You'll need them in Stage 3.

---

## Stage 3 — Copy scaffold out and push (20 min)

From `~/Desktop/`:

```bash
cd ~/Desktop

# Lift the three scaffolded repos out of the staging folder
cp -R solguard/_restructure/solguard-core .
cp -R solguard/_restructure/solguard-dashboard .
cp -R solguard/_restructure/solguard-notifiers .
```

You now have four sibling directories: `solguard/` (old monorepo), `solguard-core/`, `solguard-dashboard/`, `solguard-notifiers/`.

### Initialize and push each

```bash
# ── solguard-core ──
cd ~/Desktop/solguard-core
git init -b main
git add -A
git commit -m "Initial import from solguard monorepo (post-Phase-3 split)"
git remote add origin git@github.com:janneh2000/solguard-core.git
git push -u origin main

# ── solguard-dashboard ──
cd ~/Desktop/solguard-dashboard
git init -b main
git add -A
git commit -m "Initial import from solguard monorepo (post-Phase-3 split)"
git remote add origin git@github.com:janneh2000/solguard-dashboard.git
git push -u origin main

# ── solguard-notifiers ──
cd ~/Desktop/solguard-notifiers
git init -b main
git add -A
git commit -m "Initial import from solguard monorepo (post-Phase-3 split)"
git remote add origin git@github.com:janneh2000/solguard-notifiers.git
git push -u origin main
```

**Verify in GitHub UI:** each repo now has the scaffold committed. Actions tab should show CI starting to run.

---

## Stage 4 — Freeze the old monorepo (5 min)

From `~/Desktop/solguard`:

```bash
# Update README to point to the new repos
cat > FROZEN.md <<'EOF'
# This repository is frozen at Phase 3 submission (tag: phase3-submission)

Continued development has moved to three focused repositories:

- **solguard-core** (public) — https://github.com/janneh2000/solguard-core
- **solguard-dashboard** (private) — https://github.com/janneh2000/solguard-dashboard
- **solguard-notifiers** (private) — https://github.com/janneh2000/solguard-notifiers

The Anchor on-chain program id is unchanged: `5kkaYGaXECsngVohp3Z7NdDnxpfatTqSsmMVpsnngZFM` (devnet).
The live dashboard is unchanged: https://solguard.vercel.app

This repo remains as the hackathon submission record and will not receive further changes.
EOF

git add FROZEN.md
git commit -m "Freeze monorepo — development moved to 3-repo architecture"
git push
```

On GitHub, consider checking "Archive this repository" in repo Settings → Danger Zone once you're comfortable the migration succeeded end-to-end.

---

## Stage 5 — Wire up inter-service auth (10 min)

Generate a single shared secret used by `solguard-core` (to sign) and `solguard-notifiers` (to verify):

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
# → e.g. 3a7f...
```

- In **solguard-core** `.env`: set `NOTIFIER_HMAC_SECRET=<that value>` and `NOTIFIER_URLS=http://notifiers:8001/alert` (for compose) or the production notifier URL.
- In **solguard-notifiers** `.env`: set the same `NOTIFIER_HMAC_SECRET=<that value>`.

Rotate this any time the list of people with access changes.

---

## Stage 6 — Local full-stack smoke test (10 min)

```bash
cd ~/Desktop/solguard/_restructure

# Create .env files for each service from the examples
cp solguard-core/.env.example solguard-core/.env
cp solguard-notifiers/.env.example solguard-notifiers/.env
# Edit both files — fill HELIUS_RPC_URL, channel creds, and the shared NOTIFIER_HMAC_SECRET

docker compose up --build
```

Expected output in three parallel log streams:

```
solguard-core       | INFO: Uvicorn running on 0.0.0.0:8000
solguard-notifiers  | INFO: Uvicorn running on 0.0.0.0:8001
solguard-dashboard  | nginx/1.27.x
```

### Smoke commands

```bash
# Core health
curl http://localhost:8000/health
# → {"status":"ok","version":"2.0.0",...}

# Notifier health (channel configuration readback)
curl http://localhost:8001/health
# → {"status":"ok","channels":{"telegram_client":true,"discord_client":false}}

# Dashboard up
curl -I http://localhost:8080
# → HTTP/1.1 200 OK

# End-to-end: fire the Drift replay and watch it flow through core → notifiers
curl -X POST http://localhost:8000/api/replay/drift
# Then in another terminal, watch the notifier logs — you should see "delivered: N"
```

Open http://localhost:8080 and paste `http://localhost:8000` into the API field. Click Connect. Press `R` to trigger the cinematic replay.

---

## Stage 7 — Production deployment (60-90 min)

### Option A — Dashboard stays on Vercel (recommended)

1. On Vercel, disconnect the old `solguard` project from the old repo.
2. Connect a new Vercel project to `solguard-dashboard`.
3. Deploy. Set custom domain if you have one.
4. In **solguard-core**'s production env, update `SOLGUARD_CORS_ORIGINS` to include the new dashboard URL.

### Option B — Dockerize everything on a VPS

Provision a VPS (Hetzner CPX11 = €4/mo is plenty). Copy `_restructure/` onto the box (or clone the three repos there), set up a top-level `.env` with `NOTIFIER_HMAC_SECRET`, and run:

```bash
docker compose up -d --build
```

Put Caddy or Traefik in front for TLS.

### Either way — the core service

`solguard-core` is the piece that genuinely needs to run 24/7 with outbound internet access. Options:

- **Railway** — `railway up` from the solguard-core dir. Deploys straight from Dockerfile. Easiest path. ~$5/mo.
- **Fly.io** — `fly launch` then `fly deploy`. Needs a volume for the SQLite db. ~$2-5/mo.
- **DigitalOcean App Platform** — connect repo, set env vars, done.
- **Self-hosted VPS** — docker compose up, systemd, or a bare `uvicorn` behind nginx.

Whichever you pick, remember to:

1. Set all env vars from `solguard-core/.env.example` — especially `HELIUS_RPC_URL`, `HELIUS_WEBHOOK_SECRET`, `SOLGUARD_ADMIN_TOKEN`, `NOTIFIER_HMAC_SECRET`, `NOTIFIER_URLS`.
2. Persist `/data` (the SQLite alert ledger) across restarts — a volume or managed disk.
3. Lock outbound egress: core only needs Solana RPC and the notifier URLs.

---

## Stage 8 — Rotate any exposed secrets (mandatory)

See [`../docs/AUDIT_REPORT.md`](../docs/AUDIT_REPORT.md) § secrets hygiene. Values that appeared in earlier work:

- `ANTHROPIC_API_KEY`
- Helius RPC API key
- `TELEGRAM_BOT_TOKEN`

Rotate all three **before** pointing production at the new stack. Set new values in:
- **solguard-core** env: `ANTHROPIC_API_KEY`, `HELIUS_RPC_URL`
- **solguard-notifiers** env: `TELEGRAM_BOT_TOKEN`, `DISCORD_WEBHOOK_URL`

---

## Rollback matrix

| If this fails...                           | Rollback                                                              |
|--------------------------------------------|-----------------------------------------------------------------------|
| Stage 3 push breaks something              | `rm -rf ~/Desktop/solguard-{core,dashboard,notifiers}`; re-copy from `_restructure/` |
| New production core is broken              | Keep old `solguard.vercel.app` + old agent running until new is green |
| CI fails on one of the 3 repos             | Fix in that repo. Others are unaffected (fully decoupled).            |
| Everything on fire                         | `git checkout phase3-submission` in the monorepo. Submission is intact. |

---

## Post-migration checklist

- [ ] All three repos have green CI on first push.
- [ ] `docker compose up` from `_restructure/` boots all three services.
- [ ] `/api/replay/drift` on core produces a log line on the notifier.
- [ ] New Vercel (or whatever) deploy of the dashboard loads and connects to new core URL.
- [ ] Old monorepo has `FROZEN.md` and is optionally archived.
- [ ] All three previously-exposed secrets are rotated.
- [ ] `xguard` GitHub org + domain reserved (optional, defensive).
- [ ] `docs/AUDIT_REPORT.md` + `docs/DEMO_SCRIPT.md` copied into `solguard-core/docs/` for public visibility.

When every box is checked, you're done. The `_restructure/` staging folder can be deleted from the old repo.
