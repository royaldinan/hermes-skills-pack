---
name: cross-device-local-sync
description: Use when building cross-device sync between PC and phone.
---

# Cross-Device Local Sync & Messaging Bridges

Comprehensive guide for operating reliable background clipboard synchronization, mobile notification bridges, and local messaging relays across Windows and Android devices (Android 10 through 15, including Transsion XOS, HyperOS, and OneUI).

## 1. Android Background Clipboard Restrictions (Android 10 to 15)

### The Google Clipboard Sandbox Lock
- **The Framework Security Mechanism**:
  Starting in Android 10 and reinforced through Android 15 (`ClipboardService.isCallerDefaultImeOrFocused()`), the Android OS framework unconditionally blocks background applications from accessing or modifying `ClipboardManager` unless they have active window focus or the default IME (keyboard) role.
- **The `com.termux.api` Deadlock**:
  In `com.termux.api` (`ClipboardAPI.java`), line 19 unconditionally calls `getPrimaryClip()` before evaluating whether the request is a read or write. Calling `termux-clipboard-set` from a background daemon while inside another app (e.g. WhatsApp) hangs until the user manually opens Termux.
- **The Operational Rules**:
  1. **Never promise zero-tap background clipboard writes via CLI `termux-clipboard-set` on Android 10+** without root/LSPosed.
  2. **Explicit Hotkey Gating vs. Auto-Push Trap**:
     - NEVER auto-dispatch network/messaging pushes (e.g. WhatsApp messages) on generic OS clipboard change events (`Ctrl + C` / `GetClipboardSequenceNumber`). Users copy continuously during normal editing, resulting in unwanted notification spam.
     - Gate outgoing clipboard relay strictly behind an explicit global hotkey (e.g. `Ctrl + Alt + C` registered via Win32 `RegisterHotKey(None, HOTKEY_ID, MOD_CONTROL | MOD_ALT, VK_C)`) or a dedicated UI trigger.
     - When explicitly triggered, dispatch **two separate messages** via the local messaging bridge:
       - *Message 1 (Header Indicator)*: `📋 *[CLIPBOARD DARI LAPTOP]*\n(Teks disalin di bawah ini...)`
       - *Message 2 (Clean Raw Payload)*: 100% pure text/link without any header/footer so the user can copy or forward from mobile WhatsApp in 1 tap without manual trimming.

---

## 2. Host-Side Win32 Clipboard Watcher Concurrency

### Win32 Sequence Watcher Retry Loop
- **The Concurrency Race Condition**:
  `user32.GetClipboardSequenceNumber()` increments the exact microsecond an application begins writing to the clipboard. Large applications (Chrome, MS Word, VS Code) hold a write lock and take 30–80ms to populate `CF_UNICODETEXT`.
  If a background watcher thread immediately advances `last_seq = curr_seq` while `get_text()` returns `""`, it records the sequence as processed and drops the copy event permanently.
- **The Fix**:
  ```python
  curr_seq = user32.GetClipboardSequenceNumber()
  if curr_seq != self.last_seq:
      curr_text = ""
      for _ in range(3):
          curr_text = self.get_text()
          if curr_text:
              break
          time.sleep(0.08)
      if curr_text and curr_text != self.last_synced_text:
          with self.lock:
              self.last_synced_text = curr_text
              self.last_change_ts = time.time()
              self.last_seq = curr_seq
          for cb in list(self.on_change_callbacks):
              cb(curr_text)
      else:
          self.last_seq = curr_seq
  ```

---

## 3. Mobile Notification Formatting Rules

### Task Title Prominence Rule
- **The Generic Stage Header Trap**:
  Passing stage mood labels (e.g. `"Mahiru — Pengingat Santai 🌸"`) as the `--title` argument of `termux-notification` pushes the real task name into line 2 of the content. On Android lockscreens and heads-up banners, secondary lines are truncated, making the notification uninformative.
- **The Fix**:
  - Set `--title` directly to the actual task name and priority: `🌸 <Title> (<Priority>)`.
  - Place time remaining, deadline, and context in the content body: `⏳ <Time Remaining> | Batas: <Deadline>\n🎯 Keperluan: <Keperluan>\n💬 <Message>`.

---

## 4. Multi-Daemon Lifecycle & Autostart Management

### Conjunction Process Checking in `~/.bashrc`
- Always use conjunction checks for companion daemons:
  ```bash
  (pgrep -f 'python.*notifier.py' >/dev/null && pgrep -f 'python.*clip_sync.py' >/dev/null) || bash $HOME/mahiru/start.sh
  ```
- Always invoke `termux-wake-lock 2>/dev/null || true` at the top of startup scripts.
- Append `>/dev/null 2>&1 || true` to all `pkill` invocations in background scripts so subshells under `set -e` do not abort with `Terminated`.

---

## 5. Android WebView Hybrid Client Resilience

### Silent SSL Cancellation Trap
- **The Failure Mechanism**:
  Android's default `WebViewClient` unconditionally cancels requests (`handler.cancel()`) on any SSL error (e.g. Tailscale `*.ts.net` MagicDNS certs, self-signed IP certificates, or local root CAs). Unlike standard desktop browsers, Android WebView displays **no warning, error dialog, or fallback screen** by default—the viewport simply stays completely blank/black while native toolbars appear normal.
- **The Fix**:
  Override `onReceivedSslError` in `WebViewClient` and invoke `handler?.proceed()` for verified private mesh/local subnets (`100.x.y.z`, `ts.net`, `192.168.x.x`):
  ```kotlin
  override fun onReceivedSslError(view: WebView?, handler: SslErrorHandler?, error: SslError?) {
      Log.w("HybridWebView", "SSL Error bypassed for local mesh: ${error?.toString()}")
      handler?.proceed()
  }
  ```

### WebView Console & Remote Debugging Visibility
- **The Blind Spot**:
  Client-side JavaScript exceptions, CSS layout crashes, and WebSocket handshake errors inside an Android WebView do not appear in `adb logcat` unless explicitly routed through `WebChromeClient`.
- **The Fix**:
  Always enable remote DevTools inspection and route console logs to Logcat:
  ```kotlin
  WebView.setWebContentsDebuggingEnabled(true)
  webView.webChromeClient = object : WebChromeClient() {
      override fun onConsoleMessage(cm: ConsoleMessage?): Boolean {
          Log.e("WebViewConsole", "${cm?.message()} [${cm?.sourceId()}:${cm?.lineNumber()}]")
          return true
      }
  }
  ```

### Stale Node Hostname Migration Trap
- **The Failure Mechanism**:
  Hardcoding a static MagicDNS hostname (e.g. `laptop-xxxx.ts.net`) or writing startup logic that blindly overwrites user-entered IPs with a default hostname causes complete connection failure when a device is renamed or re-authenticated on Tailscale.
- **The Fix**:
  Preserve direct mesh IPs (`http://100.x.y.z:port`) in SharedPreferences. Only perform automatic migration if the stored target explicitly matches a known dead/stale hostname string, never when the stored target is a valid numeric Tailscale IPv4 address.

---

## 6. Process Lifecycle & Concurrency Resilience

### Backend Orphan Children on Master Crash (`Errno 10048`)
- **The Failure Mechanism**:
  When a master backend process (e.g. FastAPI on port 8000) spawns helper child daemons (e.g. Node.js messaging bridge on 8001 or GPU audio agent on 8002) and later crashes or terminates unexpectedly, the child daemons remain running as orphaned processes holding their sockets. When the startup script or restart routine runs, child processes throw socket bind conflicts (`[Errno 10048] address already in use`).
- **The Fix**:
  1. Kill all tracked child process PIDs and inspect listening ports (`netstat -aon | findstr ":8001"`) before starting the master server.
  2. On Windows, socket release is not instantaneous—always insert a mandatory 2-second cooldown (`timeout /t 2 /nobreak >nul` in batch, or `time.sleep(2)` in Python) after killing processes before attempting to rebind.
  3. Ensure child autostart logic checks socket readiness (`connect_ex`) before spawning to prevent multiple parallel instances.

### Dual Pydantic v1 & v2 Serialization Safety
- **The Failure Mechanism**:
  Calling `.model_dump()` in environments with Pydantic v1 (`<2.0`, common in older or fixed Python virtualenvs) throws an unhandled `AttributeError: '<Model>' object has no attribute 'model_dump'`, failing PUT/POST update requests with 500 Internal Server Error.
- **The Fix**:
  Use a version-agnostic extractor for model dictionary conversion:
  ```python
  data = model_obj.model_dump(exclude_unset=True) if hasattr(model_obj, "model_dump") else model_obj.dict(exclude_unset=True)
  ```

---

## 7. Offline-First Sync State Presentation

### The Cached Timestamp Illusion
- **The Trap**:
  In offline-first mobile apps, displaying a static "Last Synced: HH:MM" banner derived from local SQLite timestamps tricks users into assuming the current connection to the laptop/PC is healthy and active.
- **The Rule**:
  Separate **data freshness** from **transport connectivity**. The UI must display a live, ping-verified connection badge (`🟢 Online` / `🔴 Offline`) alongside the timestamp of the last successful data exchange so users can immediately diagnose broken servers versus up-to-date offline data.

---

## 8. Mobile Cellular Connectivity & Zero-Cost Cloud Relay

### Mobile Cellular vs Tailscale Direct IP Trap
- **The Failure Mechanism**:
  Hardcoding direct Tailscale mesh IPs (`http://100.x.y.z:port`) in mobile apps fails with 100% packet loss whenever the phone switches to cellular data (e.g. `ccmni1`) or an untrusted Wi-Fi network without the Tailscale Android client running in the background.
- **The Fix**:
  Expose host machine services (such as 9Router or local AI gateways) via Tailscale Funnel (`tailscale serve` / `tailscale funnel` to port 8000/443). This produces a public, valid HTTPS URL (`https://<node>.ts.net/api/...`) that mobile clients reach globally from any network without requiring a VPN toggle on the phone. In the mobile client, configure the fallback order: (1) Custom Endpoint if user-defined, (2) 24/7 Cloud Funnel URL, (3) Direct Mesh IP (`100.x.y.z`), and (4) Standalone API key fallback (e.g. Gemini).

### Hugging Face Spaces Free Tier SDK Gating
- **The Failure Mechanism**:
  Hugging Face blocks free personal accounts from creating Gradio or Docker spaces on CPU-basic, returning `HTTP 402 Payment Required` ("Static Spaces are free for everyone, but hosting Gradio and Docker Spaces on free cpu-basic requires a PRO subscription"). Additionally, running `hf upload <ns>/<name> . --repo-type space` on an existing space may invoke repo creation logic and fail with 402 if SDK is unspecified.
- **The Fix**:
  1. For zero-budget cloud companions and documentation demos, create Spaces strictly with `sdk: static` via the REST API (`POST https://huggingface.co/api/repos/create` with `{"name": "...", "type": "space", "sdk": "static"}`).
  2. Static Spaces serve single-page HTML/JS applications at `https://<ns>-<name>.static.hf.space` without compute costs or credit cards.
  3. Upload folders safely to existing static Spaces via the Python Hub API rather than the CLI wrapper:
     ```python
     from huggingface_hub import HfApi
     HfApi().upload_folder(folder_path="<dir>", repo_id="<ns>/<name>", repo_type="space")
     ```

