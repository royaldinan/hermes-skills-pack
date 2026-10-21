---
name: ai-gateway-ops
description: "Use when operating a local AI model gateway."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [ai-gateway, openai-compatible, localhost, dashboard, troubleshooting]
    related_skills: [systematic-debugging]
---

# AI Gateway Ops

## When to use

The user runs a local OpenAI-compatible model gateway/router on localhost
(9Router, LiteLLM, or similar — typically port 20128) and needs it verified,
diagnosed, or unlocked: API key checks, dashboard login walls, provider setup,
or figuring out which process actually owns the port.

## Core distinction

The API plane (`/v1/*`, Bearer key) and the dashboard plane (`/dashboard`,
cookie session) authenticate independently. A dashboard login wall says nothing
about API health — verify each plane separately before concluding anything is
down. Bearer auth is required even on loopback; a 401/403 there means auth,
not network.

## Procedure

### 1. Verify the API plane

```bash
curl -s -m 15 http://localhost:<PORT>/v1/models -H "Authorization: Bearer <KEY>"
```

Then a minimal chat completion against one listed model. If both answer, the
gateway serves traffic regardless of dashboard state — say so and move on.
Assert the completion returns non-empty content with a terminal finish reason
(`stop`), not just HTTP 200: combo and reasoning models can answer 200 with
empty content and an in-progress finish reason when the token budget is too
small, so request a generous `max_tokens` on the probe call.

Size the token budget to the production prompt, not the probe: a budget that
returns `stop` with content on a one-line probe can still truncate to empty
content plus an in-progress finish reason on a long system prompt (persona +
JSON schema). Re-run the probe at full production prompt length before
locking a budget in code, and treat `finish_reason != stop` or empty content
as red regardless of HTTP status.

When latency matters on a reasoning-capable combo, sweep `max_tokens` and the
reasoning-effort parameter and record wall time, finish reason, and content
non-emptiness per cell — then ship the cheapest cell that answers fully and
stably. Prefer a reduced reasoning effort (e.g. `low`) over disabling
reasoning: reduced effort cuts thinking tokens with identical answer content,
while fully disabled reasoning is rejected by the router.

### 2. Identify the process behind a localhost port (Windows)

```bat
netstat -ano | findstr LISTENING
tasklist /FI "PID eq <PID>"
powershell.exe -Command "Get-CimInstance Win32_Process -Filter 'ProcessId=<PID>' | Select-Object -ExpandProperty CommandLine"
```

The CommandLine reveals the real binary (e.g. `node .../node_modules/<pkg>/...`),
which tells you the vendor, the install location, and where its data dir lives.
`wmic` no longer ships on current Windows — use `Get-CimInstance`, not `wmic`.

### 3. Recover locked-out dashboard access

Prefer the vendor's own recovery path over hand-editing its database:

1. Read the vendor CLI source for the documented reset flow (default password,
   reset endpoint, token scheme) — it is the spec.
2. If the reset endpoint needs a derived CLI token, reconstruct it exactly as
   the bundled server middleware does; read the bundle, never guess the
   construction. See `references/dashboard-lockout-recovery.md`.
3. Call the reset endpoint, then verify with a real login call asserting
   success plus a session cookie — a `{"success":true}` alone is not proof.
4. Hand the user the default credential and tell them to change it in Settings
   immediately.

### 4. Cross-platform migration of 9Router sessions (e.g. PC to Android/Termux)

9Router stores active OAuth connections (Google Antigravity, Codex, etc.), API keys, and custom model combos inside SQLite:
- Windows: `%APPDATA%/9router/db/data.sqlite`
- Linux / macOS / Android Termux: `~/.9router/db/data.sqlite`

To migrate an existing authenticated 9Router instance to another machine (e.g. running 9Router autonomously in Termux so the PC can be shut down):
1. Install 9Router on the target (`npm install -g 9router`).
2. Create the target database directory (`mkdir -p ~/.9router/db`).
3. Copy `data.sqlite` from `%APPDATA%/9router/db/data.sqlite` to `~/.9router/db/data.sqlite` (and copy `jwt-secret` and `machine-id` to `~/.9router/` if present).
4. Launch 9Router in headless background mode:
   `9router --no-browser --skip-update < /dev/null &> ~/9router.log &`
   *Crucial:* Running bare `9router &` without redirecting stdin or passing flags attaches to TTY and blocks indefinitely on the interactive interface selection prompt (`showInterfaceMenu`). Redirecting `< /dev/null` forces non-TTY daemon mode.
5. All pre-configured OAuth connections, combos, and local API keys load immediately without re-authenticating via browser. Verify port 20128 is listening before sending requests.

## Pitfalls

- Request generous `max_tokens` when probing combo/reasoning models — a small
  budget can return HTTP 200 with empty content and an in-progress finish
  reason, which a status-code-only check misreads as healthy. The mechanism is
  server-side truncation before any content token, not an auth or network
  fault. Always assert non-empty content in the probe.
- Delete provider fallbacks whose keys are invalid instead of keeping them in
  the chain — every call pays the dead provider's timeout first, and the real
  error gets masked behind the fallback's generic response.
- When migrating `data.sqlite`, ensure the target 9Router process is stopped before copying, and verify WAL files (`data.sqlite-wal`) are either checkpointed or included to avoid importing a stale snapshot.
- Never hand-edit the gateway's live sqlite while the server runs when a vendor
  reset API exists — the server may cache settings, so the write can be silently
  lost or WAL-corrupted. Use the reset API; treat direct DB edits as read-only
  forensics (table names, key locations).
- Never persist API keys, tokens, or password hashes into skills, memory, or
  support files — derive them fresh from local files each session.
- Do not confuse "no open management ports on the LAN" with "gateway is down";
  scan loopback listeners separately before reporting anything missing.
