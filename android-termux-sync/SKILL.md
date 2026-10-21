---
name: android-termux-sync
description: Use when running Termux daemons and Android clipboard sync.
---

# Android Termux Sync & Background Daemons

Comprehensive guide for operating reliable 24/7 Termux background daemons, cross-device clipboard synchronization, and notification bridges across Android 10, 11, 12, 13, and 14 (including aggressive OEM skins like Transsion XOS, Xiaomi HyperOS, and Samsung OneUI).

## 1. Android Background Clipboard Restrictions (Android 10+)

### The `com.termux.api` Background Deadlock Trap
- **The Core Mechanism**:
  In the official `com.termux.api` package (`ClipboardAPI.java`), line 19 unconditionally executes:
  ```java
  final ClipData clipData = clipboard.getPrimaryClip();
  ```
  at the start of `onReceive`, *before* evaluating whether the intent action is a clipboard read (`get`) or write (`set`).
- **Android Framework Security Policy**:
  Starting in Android 10 and reinforced through Android 14, Android `ClipboardService` blocks `getPrimaryClip()` for any application in the background that lacks active window focus or default IME role.
- **The Symptom**:
  When a background Python daemon calls `termux-clipboard-set` while the user is inside another app (e.g. WhatsApp), the Android system suspends/blocks the broadcast intent. The moment the user manually taps and opens Termux on screen, Termux gains window focus, the pending intent unfreezes, and Android flashes the system privacy toast: `"Termux:API ditempelkan ke papan klip"`.
- **The Operational Rules**:
  1. **Never promise zero-tap passive background clipboard writes via CLI `termux-clipboard-set` on Android 10+** without special ADB permissions (`appops set com.termux.api SYSTEM_ALERT_WINDOW allow` or `READ_CLIPBOARD_IN_BACKGROUND`) or an Android Accessibility Service.
  2. **Implement Tri-Modal Clipboard Synchronization**:
     - *Silent Background Sync (Termux)*: Fast polling daemon for when Termux holds wake lock or is brought forward.
     - *In-App Toast (Web UI / Companion APK)*: Web app polls the host `/api/clipboard/text` endpoint and displays a 1-tap copy banner when the companion UI is active.
     - *Direct WhatsApp Auto-Push (`Ctrl + C` & Menu Salin)*: Hook host-side `WindowsClipboardManager` watcher (`GetClipboardSequenceNumber`) to auto-dispatch **two separate WhatsApp messages** via local Baileys bridge:
       - *Message 1 (Header Indicator)*: `📋 *[CLIPBOARD DARI LAPTOP]*\n(Teks disalin di bawah ini...)`
       - *Message 2 (Clean Raw Payload)*: 100% pure text/link without header/footer so mobile users can copy/forward in 1 tap without manual trimming.

---

## 2. Mobile Notification Formatting Rules

### Task Title Prominence Rule
- **The Generic Stage Header Trap**:
  Passing stage mood labels (e.g. `"Mahiru — Pengingat Santai 🌸"`) as the `--title` argument of `termux-notification` pushes the real task name into line 2 of the content. On Android lockscreens and heads-up banners, secondary lines are truncated, making the notification uninformative.
- **The Fix**:
  - Set `--title` directly to the actual task name and priority: `🌸 <Title> (<Priority>)`.
  - Place time remaining, deadline, and context in the content body: `⏳ <Time Remaining> | Batas: <Deadline>\n🎯 Keperluan: <Keperluan>\n💬 <Message>`.

---

## 2. Multi-Daemon Lifecycle & Autostart Management

### Conjunction Process Checking in `~/.bashrc`
- **The Single-Process Zombie Blindness Trap**:
  Guarding background daemon startup in `~/.bashrc` with a single-process check (e.g., `pgrep -f 'notifier.py' || bash start.sh`) causes silent failures. If `clip_sync.py` crashes or is killed by OEM memory cleaners while `notifier.py` stays alive, the check evaluates to true (0) and never restarts `clip_sync.py`.
- **The Conjunction Rule**:
  Always use conjunction checks or independent process monitors:
  ```bash
  (pgrep -f 'python.*notifier.py' >/dev/null && pgrep -f 'python.*clip_sync.py' >/dev/null) || bash $HOME/mahiru/start.sh
  ```
- **Wakelock & Signal Safety**:
  - Always invoke `termux-wake-lock 2>/dev/null || true` at the top of startup scripts.
  - In background runner scripts, append `>/dev/null 2>&1 || true` to all `pkill` invocations to prevent subshells running under `set -e` from aborting with `Terminated`.

---

## 3. Host-Side Win32 Clipboard Watcher Concurrency

### Win32 Sequence Watcher Retry Loop
- **The Concurrency Race Condition**:
  `user32.GetClipboardSequenceNumber()` increments the exact microsecond an application begins writing to the clipboard. Large applications (Chrome, MS Word, VS Code) hold a write lock and take 30–80ms to populate `CF_UNICODETEXT`.
  If a background watcher thread immediately advances `last_seq = curr_seq` while `get_text()` returns `""`, it records the sequence as processed and never retries. The copy event is dropped permanently.
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
      else:
          self.last_seq = curr_seq
  ```

---

## 4. Summary Table of Pitfalls

| Pitfall | Root Cause | Preventive Rule |
| :--- | :--- | :--- |
| **`com.termux.api` Background Deadlock** | `ClipboardAPI.java` unconditionally calls `getPrimaryClip()` on line 19 before checking `get`/`set`. Android blocks `getPrimaryClip()` for background apps without window focus. | Do not rely solely on background CLI `termux-clipboard-set`. Provide WhatsApp bot push (`Ctrl + Alt + C`) or notification actions. |
| **Termux Autostart Single-Process Blindness** | `pgrep -f 'notifier.py'` in `~/.bashrc` ignores whether companion daemons (`clip_sync.py`) are dead. | Check all companion daemons concurrently: `(pgrep -f 'a' && pgrep -f 'b') || bash start.sh`. |
| **Win32 Sequence Watcher Concurrency Drop** | `GetClipboardSequenceNumber()` increments before write completes; immediate `last_seq` advancement drops text. | Retry `get_text()` 3 times with 50-80ms delays before locking sequence number. |
