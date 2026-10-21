---
name: vercel-deployment
description: Use when deploying web apps to Vercel via CLI.
---

# Vercel CLI Deployment & Cardless Cloud Hosting

Complete workflow for deploying Single Page Applications (Vite, React, Next.js, Vue) to Vercel using the Vercel CLI (`vercel` / `npx vercel`), resolving routing pitfalls, disabling team-scope SSO deployment protection, and assigning custom subdomain aliases.

## 1. Authentication & Device Flow

When deploying from terminal or Windows environments where interactive browser popups may stall:
1. Run `npx vercel login --no-color` in a tracked background process or inspect the stdout stream.
2. Extract the device code authorization URL:
   ```text
   https://vercel.com/oauth/device?user_code=XXXX-YYYY
   ```
3. Open the verification URL in the system default browser:
   - On Windows: `cmd.exe /c start "" "https://vercel.com/oauth/device?user_code=XXXX-YYYY"`
   - On macOS: `open "https://vercel.com/oauth/device?user_code=XXXX-YYYY"`
   - On Linux: `xdg-open "https://vercel.com/oauth/device?user_code=XXXX-YYYY"`
4. Verify CLI session completion:
   ```bash
   npx vercel whoami
   ```

---

## 2. SPA Routing Configuration (`vercel.json`)

Single Page Applications (Vite, React Router, Vue Router) render all views client-side. Direct navigation or browser refreshes on sub-routes (e.g. `/stats`, `/goals`) will return `404: NOT_FOUND` unless Vercel is instructed to rewrite all requests to `index.html`.

Place `vercel.json` in the web project root:
```json
{
  "framework": "vite",
  "rewrites": [
    {
      "source": "/(.*)",
      "destination": "/"
    }
  ]
}
```

If deploying from a multi-project monorepo root (e.g. repo containing `android/` and `web/`), place `vercel.json` at repository root with build and output directory specifications:
```json
{
  "buildCommand": "cd web && npm install && npm run build",
  "outputDirectory": "web/dist",
  "framework": "vite",
  "rewrites": [
    {
      "source": "/(.*)",
      "destination": "/"
    }
  ]
}
```

---

## 3. Production Deployment Execution

Execute production build and deployment non-interactively:
```bash
cd web
npx vercel deploy --prod --yes
```
The command outputs:
- Deployment inspection URL
- Unique production deployment URL (`https://<project>-<hash>-<team>.vercel.app`)
- Default alias URL (`https://<project>.vercel.app`)

---

## 4. The Team-Scope SSO / Deployment Protection Trap

### The Issue
When a project is created under a Vercel Team Scope (even on Free / Hobby plans), Vercel automatically sets:
`ssoProtection: {"deploymentType": "all_except_custom_domains"}`.

As a result:
- Visiting `https://<project>.vercel.app` returns `HTTP 302 Found` with `Location: https://vercel.com/sso-api?url=...`.
- Mobile users and public visitors are blocked by a mandatory Vercel login wall.

### The Fix
Disable `ssoProtection` directly via the Vercel REST API using the CLI authentication bearer token:
1. Locate the token:
   - Windows: `C:\Users\<User>\AppData\Roaming\com.vercel.cli\Data\auth.json`
   - POSIX: `~/.vercel/auth.json` or `~/.local/share/com.vercel.cli/auth.json`
2. Send a `PATCH` request to update project settings:
   ```bash
   curl -X PATCH "https://api.vercel.com/v9/projects/<project_name>" \
     -H "Authorization: Bearer <token>" \
     -H "Content-Type: application/json" \
     -d '{"ssoProtection": null}'
   ```
3. In Python:
   ```python
   import json, urllib.request

   token = json.load(open(auth_path))["token"]
   req = urllib.request.Request(
       f"https://api.vercel.com/v9/projects/{project_name}",
       data=json.dumps({"ssoProtection": None}).encode(),
       headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
       method="PATCH"
   )
   with urllib.request.urlopen(req) as resp:
       print("ssoProtection disabled:", json.loads(resp.read().decode()).get("ssoProtection") is None)
   ```
4. Verify unauthenticated public access:
   ```bash
   curl -I "https://<project>.vercel.app"
   ```
   Must return `HTTP/1.1 200 OK`.

---

## 5. Custom Subdomain Aliasing

Assign clean, memorable production URLs under `.vercel.app` without purchasing a custom domain:
```bash
npx vercel alias set "https://<generated-deployment-url>.vercel.app" "<clean-subdomain>.vercel.app"
```
Verify the alias routing immediately via `curl -I "https://<clean-subdomain>.vercel.app"`.

---

## 6. Client-Side Database Configuration Pattern

To maintain zero cloud hosting costs and avoid managing server-side environment variables across deployment environments:
- Provide an in-app settings UI modal that stores third-party credentials (e.g. Supabase `Project URL` and `Anon Public Key`) in `localStorage`.
- This decouples the static frontend from specific cloud backends, enabling instant redeployments without rebuilding bundle configurations.
