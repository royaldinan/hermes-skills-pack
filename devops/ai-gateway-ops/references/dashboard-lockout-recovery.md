# Dashboard Lockout Recovery (local AI gateways)

Topical recipe for regaining dashboard access when the login password is lost.
General pattern first, one worked example second.

## General pattern

1. Identify the process (SKILL.md step 2) and locate its data dir: look beside
   the module path and in per-user app-data locations for `auth/`, `db/`,
   `jwt-secret`-style entries.
2. Inspect the datastore read-only (e.g. sqlite `settings` row) to confirm
   which credential the dashboard checks — this tells you what a reset must
   rewrite.
3. Find the vendor CLI's own reset flow in its source: default password,
   reset endpoint, and any CLI-token header it sends.
4. If the server middleware derives the CLI token (e.g. hash of machine-id +
   salt + secret file), reimplement that exact derivation — read the bundled
   middleware source for field order, encoding, digest, and truncation.
5. POST the reset with the derived token, then POST a login with the default
   password and assert an auth cookie comes back.

## Worked example: 9Router (npm global install)

- Process: `node .../npm/node_modules/9router/app/custom-server.js`, port 20128.
- Data dir: per-user app-data `9router/` containing `auth/cli-secret`,
  `machine-id`, `db/data.sqlite`.
- CLI source documents the default dashboard password and a
  `POST /api/auth/reset-password` endpoint using header `x-9r-cli-token`.
- The bundled middleware (`app/.next-cli-build/server/middleware.js`) derives
  the accepted token as `sha256(machine-id + "9r-cli-auth" + cli-secret)`
  hex, truncated to 16 chars; machine-id and cli-secret are read trimmed
  from the data-dir files.
- After reset, `POST /api/auth/login {"password": <default>}` returns success
  plus an `auth_token` cookie. Change the default in dashboard Settings.
