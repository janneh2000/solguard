# solguard-dashboard

**Private.** The SolGuard dashboard — single-page HTML app that connects to `solguard-core`'s SSE + REST API.

Primary deploy: [Vercel](https://solguard.vercel.app). The Dockerfile here is a portable fallback (nginx static serve) for docker-compose, Railway, Fly, or Kubernetes deploys.

---

## Features

- Hero section with ecosystem Security Score gauge (0-100) + 24h SVG sparkline.
- Cinematic Drift hack replay (press `R`): 5-stage scripted alert sequence with Presenter captions and Web-Audio-synthesised beeps.
- Keyboard shortcuts: `D` demo, `R` replay, `P` presenter, `S` sound, `Esc` close.
- Live SSE feed from `solguard-core`.
- Works offline — no external image or font dependencies.

## Development

```bash
# Local: just open the file
open index.html
# or serve over http so SSE works correctly:
python3 -m http.server 8080
```

Point the "API" field in the UI at your running `solguard-core` instance (default `http://localhost:8000`).

## Docker

```bash
docker build -t solguard-dashboard .
docker run -p 8080:80 solguard-dashboard
# → http://localhost:8080
```

## Deployment

### Vercel (current production)

- `vercel.json` pins security headers and cache policy.
- Root is this repo; no build step.
- Auto-deploys from `main`.

### Docker / VPS

`nginx.conf` ships the same security headers as the Vercel config. `docker-compose.yml` in the top-level `_restructure/` wires the dashboard in alongside `solguard-core` and `solguard-notifiers` for local full-stack development.

## Pointing at a different core

The dashboard has an "API" input at the top. Paste any `solguard-core` URL (ngrok tunnel, production URL, self-hosted) and it will:
- Fetch `/api/watchlist` to populate the right-hand program list.
- Stream `/api/stream` (SSE) for live alerts.
- Expect CORS to be configured on core to allow this dashboard's origin (`SOLGUARD_CORS_ORIGINS` env on core).
