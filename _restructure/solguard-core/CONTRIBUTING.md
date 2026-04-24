# Contributing to solguard-core

Thanks for wanting to help catch the next $285M hack before the drain.

## Ground rules

- **Security first.** Core is public and audited. Any PR touching auth, webhook verification, or the on-chain program must include tests and an explanation of the threat model.
- **No secrets in commits.** `.env` is in `.gitignore`. If you accidentally commit a key, rotate it immediately and open an issue.
- **Keep core dependency-light.** Channel-specific clients (Telegram, Discord, SMS, etc.) belong in `solguard-notifiers`, not here.

## What good contributions look like

### New attack-pattern detectors
- Add a pattern name to `VALID_PATTERNS` in `agent/claude_engine.py`.
- Add a deterministic mock-path rule in `_mock_analysis` so CI is green without an API key.
- Add a test in `agent/tests/test_claude_engine.py`.
- Document the real-world incident it protects against in the PR description.

### New chain / runtime adapters
- Put chain-specific polling under `agent/watchers/<chain>/`.
- Expose the same event schema (`type`, `program_id`, `old_authority`, `new_authority`, `tx_signature`, `slot`).
- The risk engine is chain-agnostic — don't leak chain details into `claude_engine.py`.

### Performance improvements
- Anything reducing RPC load or alert latency is welcome.
- Include a benchmark or at least a before/after timing in the PR.

## Dev setup

```bash
git clone https://github.com/janneh2000/solguard-core
cd solguard-core
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt pytest
pytest agent/tests/ -v
```

## Running the Anchor program locally

```bash
cd programs/solguard-registry
anchor build
anchor test --skip-local-validator
```

## Commit style

- Imperative subject ("Add Jito bundle detector" not "Added...").
- Reference an incident or issue where relevant.
- Keep PRs under 400 lines of diff where possible.

## Reporting vulnerabilities

Do not open a public issue for security bugs. Email the maintainer (see GitHub profile) with a description and a PoC if you have one. We aim for 72-hour triage.
