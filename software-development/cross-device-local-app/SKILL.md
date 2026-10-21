---
name: cross-device-local-app
description: Use when building local apps synced across PC and mobile.
---

# Cross-Device Local Apps (PC & Mobile Sync)

Comprehensive workflow for building lightweight, responsive full-stack applications hosted on a personal computer (Windows/macOS/Linux) and accessed/controlled seamlessly from mobile devices (Android) over local Wi-Fi or Tailscale mesh networks, featuring native WebView integration, background push notifications, and autonomous agent orchestration.

## 1. Architecture & Network Binding

### Host Binding & Multi-Interface Resolution
- **Bind backend to `0.0.0.0`**: Never bind to `127.0.0.1` or `localhost` when mobile devices must connect over LAN or VPN mesh. Loopback binds reject external packets.
- **Probe host LAN & Tailscale Mesh IPs dynamically**:
  - Wi-Fi LAN IP via UDP socket probe (no external packets sent):
    ```python
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        local_ip = s.getsockname()[0]
    finally:
        s.close()
    ```
  - Tailscale Mesh IPv4 (`100.x.y.z`) via CLI:
    ```python
    import subprocess
    try:
        res = subprocess.run(["tailscale", "ip", "-4"], capture_output=True, text=True, timeout=2)
        tailscale_ip = res.stdout.strip().splitlines()[0] if res.returncode == 0 else None
    except Exception:
        tailscale_ip = None
    ```
- **Tailscale Hostname Renaming & Ingress Domain Re-binding**:
  When a host machine is renamed in Tailscale or re-authenticated:
  - Check active MagicDNS domain via `tailscale status --json` (`Self.DNSName` / `CertDomains`) and test domain resolution via `nslookup <name>.<tailnet>.ts.net`.
  - Re-bind Funnel/Serve background proxy to the new domain:
    ```bash
    tailscale funnel reset && tailscale funnel --bg <port>
    ```
  - In Android WebViews, sanitize `SharedPreferences` on `onCreate` to invalidate deprecated hostnames and auto-migrate saved connection URLs to `DEFAULT_SERVER_URL`.
- **Windows Firewall Port Opening**:
  When deploying a new listening port (e.g. 8000, 8001, 8002), verify Windows Defender Firewall allows incoming TCP:
  ```powershell
  New-NetFirewallRule -DisplayName "Mahiru Backend" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow
  ```

---

## 2. Android WebView Container & WebRTC Permissions

### WebChromeClient & Audio Recording
In Android WebView applications capturing microphone audio (WebRTC voice calls, audio recording):
1. **Declare Permissions in `AndroidManifest.xml`**:
   ```xml
   <uses-permission android:name="android.permission.INTERNET" />
   <uses-permission android:name="android.permission.RECORD_AUDIO" />
   <uses-permission android:name="android.permission.MODIFY_AUDIO_SETTINGS" />
   ```
2. **Grant WebRTC Permissions via `WebChromeClient`**:
   Android WebViews require explicit permission granting in `onPermissionRequest`:
   ```kotlin
   webView.webChromeClient = object : WebChromeClient() {
       override fun onPermissionRequest(request: PermissionRequest) {
           request.grant(request.resources)
       }
   }
   ```
3. **Android Studio JBR for Gradle APK Compilation**:
   When building APKs from Windows terminal without system Java on PATH:
   ```bash
   export JAVA_HOME="/c/Program Files/Android/Android Studio/jbr"
   export PATH="$JAVA_HOME/bin:$PATH"
   ./gradlew assembleDebug --no-daemon
   ```

### Android WebView Universal File Downloads (Attachment Routing)
- **The Anchor-Click Download Drop in WebViews**:
  In Android WebView, creating an in-memory anchor `<a href="..." download>` and calling `a.click()` does NOT trigger Android's native `DownloadListener` unless actual page navigation occurs or the scheme is intercepted. Blob URLs (`blob:...`) also fail silently because Android's `DownloadManager` only accepts `http://` and `https://` URIs.
- **The Universal Direct Download Pattern**:
  Serve downloadable files directly from the backend with `Content-Disposition: attachment; filename="..."`. In client JavaScript, implement a dual-trigger pattern:
  ```javascript
  function triggerUniversalDownload(url, filename) {
    // 1. Desktop / standard browser anchor click
    try {
      const a = document.createElement("a");
      a.style.display = "none";
      a.href = url;
      a.setAttribute("download", filename);
      document.body.appendChild(a);
      a.click();
      setTimeout(() => { try { document.body.removeChild(a); } catch (e) {} }, 400);
    } catch (e) {}

    // 2. Android WebView / Mobile DownloadListener trigger
    // Because the response has Content-Disposition: attachment, Android WebView invokes
    // DownloadListener.onDownloadStart() into DownloadManager without navigating away!
    setTimeout(() => {
      window.location.href = url;
    }, 150);
  }
  ```

### Real-Time Mobile Remote Keyboard (Keystroke Delta Streaming)
- **The Form Submit / Buffer Trap**:
  Requiring users to type into an `<input>`, press Enter, or tap a "Ketik / Kirim" button breaks the seamless physical keyboard illusion when controlling a remote PC.
- **Instant Keystroke Delta Bridge**:
  Listen to the `input` event on the text field. Compare current string length against a `liveTypingBuffer`:
  ```javascript
  let liveTypingBuffer = "";
  input.addEventListener("input", () => {
    const currentVal = input.value;
    if (currentVal.length > liveTypingBuffer.length) {
      // New characters typed -> stream immediately to host /api/keyboard/type
      const addedChars = currentVal.slice(liveTypingBuffer.length);
      sendInstantKeystroke(addedChars);
    } else if (currentVal.length < liveTypingBuffer.length) {
      // Backspace pressed in mobile keyboard -> stream backspace key to host
      const deletedCount = liveTypingBuffer.length - currentVal.length;
      for (let i = 0; i < deletedCount; i++) sendLaptopKeySilent("backspace");
    }
    liveTypingBuffer = currentVal;
    if (input.value.length > 50) {
      input.value = "";
      liveTypingBuffer = "";
    }
  });
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      sendLaptopKeySilent("enter");
      input.value = "";
      liveTypingBuffer = "";
    }
  });
  ```

### The Insecure Context Trap (WebRTC & Silent HTTPS Auto-Upgrade)
- **Root Cause**: On Chromium Android WebView, any HTTP origin other than `localhost` (e.g., `http://100.x.y.z:8000` or `http://192.168.1.x:8000`) is treated as an **Insecure Context** (`window.isSecureContext === false`).
- **Why Flags Fail**: `chrome://flags` (`Insecure origins treated as secure`) applies **strictly to the standalone Google Chrome browser process**. Android system WebViews run inside their own APK sandbox and **do not inherit or parse Chrome flags**.
- **Rules**:
  1. For WebRTC microphone/audio streams on Android WebViews, always route traffic through an authenticated **Tailscale HTTPS Funnel** (`https://<node>.<tailnet>.ts.net`) with a valid TLS certificate.
  2. In the Android APK (`MainActivity.kt`), set `DEFAULT_SERVER_URL` to the Tailscale HTTPS address:
     ```kotlin
     private val DEFAULT_SERVER_URL = "https://laptop-name.tailnet.ts.net"
     ```
  3. **Never render manual HTTP warning popups or redirect buttons**: Rendering error banners or buttons (e.g. "Mic Diblokir", "Beralih ke HTTPS") creates a jarring, broken UX. Instead, execute an **instant silent auto-upgrade in `<head>`** before DOM render:
     ```html
     <script>
       if (location.protocol === 'http:' && location.hostname !== 'localhost' && location.hostname !== '127.0.0.1') {
         if (location.hostname.startsWith('100.') || location.hostname.includes('.ts.net')) {
           window.location.replace('https://<node>.<tailnet>.ts.net' + location.pathname + location.search);
         }
       }
     </script>
     ```

### Realtime Voice Call Mode (VAD, Echo Cancellation & Dual-Engine STT)
When building interactive duplex voice calls between mobile devices and a local backend:
1. **Mandatory Microphone Constraints**:
   Never request bare `{ audio: true }`. Always declare hardware audio processing constraints:
   ```javascript
   navigator.mediaDevices.getUserMedia({
     audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true }
   })
   ```
   Without `echoCancellation`, assistant audio played through phone loudspeakers feeds back into the microphone, triggering self-interruption (barge-in loop) and killing playback within 100ms.
2. **Robust VAD & State Transition (Prevent Endless Listening)**:
   - Dynamic baseline estimation: sample room noise on call startup to compute a dynamic speech threshold (`Math.max(16, baseline + 10)`).
   - Silence timeout: cut utterance after 650–800ms of consecutive sub-threshold audio.
   - Enforce a **hard maximum utterance duration** (e.g., 5–6 seconds) that forces a chunk cut and dispatch regardless of ambient room noise.
3. **Dual-Action Push-to-Send Mic Control**:
   - When the user taps the mic button while actively speaking, treat it as **Push-to-Send** (flush utterance): immediately stop `MediaRecorder`, dispatch the recorded chunk to the backend, and transition UI state to "Thinking / Processing".
   - Never merely toggle track enablement (`track.enabled = false`) without flushing, which traps the UI in "Listening..." indefinitely.
   - If assistant audio is playing, tapping the mic button must perform immediate barge-in (stop assistant audio and listen to user).
4. **Dual-Engine Speech-to-Text (STT) Ingestion**:
   - **Do NOT rely on client-side Web Speech API (`webkitSpeechRecognition`) on Android WebViews**: in Android Chromium WebViews, `window.webkitSpeechRecognition` exists in memory but fails silently or hangs without firing speech events because the WebView sandbox lacks native integration to Google Speech Services.
   - **Dual-Engine Pipeline (Ultra-Fast Cloud API + Local CPU Fallback)**:
     - Primary: Query Groq API `whisper-large-v3-turbo` with multipart/form-data. Latency drops from ~1500ms to ~200-300ms with near-perfect phoneme transcription on conversational slang and Indonesian.
     - Secondary Fallback: Fall back to local `faster-whisper-tiny` on CPU if network or API keys fail, passing `condition_on_previous_text=False` to prevent hallucination repetition loops, and filter single-phrase artifacts (`terima kasih`, `amara.org`).
   - **Never wrap audio in `{"type": "image_url", "image_url": {"url": "data:audio/..."}}`** for OpenAI-compatible chat endpoints; chat APIs discard audio in image payloads, causing the LLM to hallucinate on system prompt examples (e.g. apps like Discord).
5. **Autoplay Policy Lock & Web Audio API Buffer Playback**:
   - On Android Chrome and WebViews, calling `new Audio(url).play()` inside an asynchronous network callback (`await fetch`) fails with `NotAllowedError` because the initial user gesture expired during network round-trips.
   - **Solution**: Play assistant voice through `AudioContext.decodeAudioData(arrayBuffer)` via a `BufferSourceNode` connected to `AudioContext.destination`. Because `AudioContext` is already primed and running during call startup (user gesture), Web Audio API buffer playback is 100% immune to autoplay restrictions and has zero latency. In Android native code (`MainActivity.kt`), also set `settings.mediaPlaybackRequiresUserGesture = false`.
6. **Acoustic Feedback Isolation (Prevent Self-Mute Loop)**:
   - When the assistant's voice plays through the phone's loudspeaker, the microphone (located millimeters away) picks up the loudspeaker audio within 15–20ms. If VAD evaluates mic decibels during assistant playback, it mistakes the assistant's own voice for user interruption (barge-in) and immediately pauses playback.
   - **Rule**: Set `isSpeaking = true` during assistant audio playback. In the VAD animation loop, **completely bypass microphone decibel checks while `isSpeaking` is true**. Support barge-in via manual user tap on the screen or mic button.
7. **Session History & Dual Subtitle Display**:
   - Display dual synchronized bubbles: `Kamu: "<user text>"` and `Assistant: "<reply text>"`.
   - Save both user transcripts and assistant replies into the database (`chat_history` with `source = 'voice_call'`) to prevent multi-turn context amnesia during live calls.

### Reasoning Model Latency Trap & Duplex Audio Pipelining
1. **Reasoning Model Latency Trap**:
   Never use models configured with high reasoning / chain-of-thought tokens (e.g. `gemini-3.8-flash-high`) for interactive voice calls. High thinking generates thousands of hidden reasoning tokens before outputting the first word, introducing 7–10 seconds of Time-To-First-Token (TTFT) latency and creating awkward 10–13 second dead silences per conversational turn.
   - **Dual-Brain Strategy**: Reserve high-reasoning models for autonomous agent tasks, coding, and heavy file debugging; route duplex voice calls strictly to zero-thinking / low-latency inference (e.g. Groq LPUs with `qwen/qwen3.8-27b` providing ~350ms TTFT, or zero-thinking Gemini Flash).
2. **Bypass Complex Structured JSON in Voice Calls**:
   Do not force 10-field structured JSON output (`action`, `action_param`, `task_title`, `task_notes`, `mood`, `reply`, `japanese_voice`) during live voice calls. Enforcing JSON syntax doubles completion token generation and delays playback. Use a minimal dual-line format (`[ID]: ... \n [JP]: ...`) to cut generation tokens in half.
3. **In-Memory Audio Buffer Direct Pipelining**:
   Avoid writing incoming mobile audio chunks to disk (`temp_in.bin`), spawning a blocking external `ffmpeg` subprocess to convert to `.wav`, and reading back from disk. Pipe the in-memory audio buffer directly to Groq Whisper Turbo via `io.BytesIO(raw_audio)` with a named file tuple, eliminating 400ms of disk I/O and process spawn overhead.

4. **Phoneme Alignment in Fine-Tuned Voice Models (Zero-Shot / RVC / GPT-SoVITS)**:
   When synthesizing character vocals using models fine-tuned on native-language speech corpora (e.g. Japanese anime voice actors), feeding translated/foreign text (e.g. Indonesian/English) produces garbled phonemes or forces the engine into generic fallback voices.
   - **Dual-Field Synthesis & Subtitle Separation**: Have the fast LLM output two synchronized fields:
     - `japanese_voice`: A concise, natural Japanese sentence tailored to character mannerisms (e.g., using affectionate particles like *〜ね*, *〜よ*, *ダーリン*), fed directly to the speech synthesis model.
     - `reply`: The localized meaning/translation, rendered on-screen as synchronized subtitles.
   - **Latency Budget via Phrasing Length**: Cap the spoken Japanese phrase to 10–20 kana/kanji characters. Consumer GPUs (e.g. RTX 3050) synthesize 15 characters in ~1.8–2.2s, maintaining sub-3s total turn latency in duplex calls.

### Interactive Companion Voice Pre-Rendering (Instant 0ms Feedback)
- **The On-the-Fly TTS Delay Trap**:
  For frequent tactile interaction buttons (e.g. Sapa, Merajuk, Puji, Teh), on-the-fly zero-shot TTS and RVC inference on consumer GPUs introduces 2–4s latency per tap, degrading what should be an instant emotional response.
- **Pre-Rendered Voice Audio Pool**:
  Pre-synthesize an authentic pool of character voice clips for each interactive intent directly on the host GPU (OmniVoice + RVC). Save them to static assets (`/static/audio/interact/<intent>_<id>.mp3`). On interaction, return the corresponding dialogue text and pre-rendered audio URL; client immediately executes `new Audio(data.audio_url).play()` for 0ms audio playback paired with visual animations.

---

## 3. WhatsApp Gateway & Standby Architecture

### Fast Intent Engine vs Autonomous Agent Delegation
When controlling a local system via WhatsApp, decouple instant casual conversation from heavy autonomous tasks:
1. **Instant Chat (<2s response)**:
   Casual conversation, queries, reminders, and quick laptop actions (volume, mute, lock) are handled directly by the conversational persona and fast-path intent engine.
   - **Guard Against Substring Hijacking**: Fast-path keyword matchers (e.g. `setel`, `putar`, `dengerin` for YouTube/Spotify) must NOT trigger if the message exceeds 12–15 words or contains problem descriptions, troubleshooting phrases, or compound instructions. Otherwise, conversational complaints like "suara harus dengerin dan jawab kek bingung jadinya" get hijacked into YouTube searches.
2. **Autonomous Agent Background Worker**:
   Heavy reasoning, coding, system updates, debugging, or document generation tasks must never block the gateway or hit conversational timeouts:
   - **Global Search over Rigid Prefix**: Real user commands frequently include preambles or greetings ("Udah bisa ngobrol tapi ... ini tolong suruh hermes benerin"). Never use `re.match(r"^hermes")` with strict beginning-of-string anchors. Use `re.search(r"\b(hermes|suruh hermes|lewat hermes|tugas hermes|delegasi hermes|mau hermes)\b", msg, re.I)` to capture delegation anywhere in the message.
   - **Cleaned Task Prompt Sanitization**: Strip conversational filler ("Coba mau ngetes aku mau hermes buatin pdf puisi tapi hermes yang buat" -> "buatin pdf puisi") before invoking the agent CLI to avoid wasting agent turns debating conversational preambles.
   - **Evaluate Delegation BEFORE Fast Media Intents**: Check for agent delegation before any media/YouTube/app matchers to ensure user requests to fix code or debug bugs are never stolen by music keywords.
   - **Register Delegation in LLM Actions**: Include `delegate_hermes` in the LLM's system prompt actions so that natural language requests not caught by regex can still trigger autonomous jobs.
   - **Immediate WhatsApp Acknowledgment**: Send a reassuring conversational reply in <1 second informing the user the task has been handed off to the agent in the background.
   - **Structured Stream-JSON Runner over Raw Terminal Dump**: Never pipe raw interactive CLI stdout into chat logs; ANSI escape codes, terminal spinner animations, and tool invocations exceed chat message limits (>2500 chars). Truncating stdout from the front drops the final answer and generated file paths. Run the agent with `--format stream-json --yolo`, parse JSON lines to extract clean text replies, and display clean progress on the host console (`creationflags=subprocess.CREATE_NEW_CONSOLE`).
   - **Dual-Layer Artifact Detection & Native Document Dispatch**: When the agent generates files (`.pdf`, `.docx`, `.xlsx`, `.zip`), do not merely return text paths. Snapshot target directories (`Desktop`, `Downloads`, `Documents`) before vs after execution to detect newly created or modified files. If an artifact is detected, dispatch it as a native document via the WhatsApp bridge (`document_path` parameter) along with the completion summary.
   - **Database Completion State Recording & Follow-up Fast-Path**: Record the agent's completion state and artifact paths into the message history database (`chat_history`) immediately upon worker exit. If the user follows up with "mana filenya" / "mana hasilnya", intercept it via `fast_intent_detection` to immediately re-dispatch the cached artifact from the latest job, preventing the assistant from hallucinating that the agent is still running.

### Contact Resolver & Parameter Decoupling Rules
When accepting commands like "kirim pesan ke [Nama Kontak]" via natural language:
- **LLM Parameter Decoupling**: Never assume the LLM populates `action_param` with phone numbers. LLMs frequently place contact names or phone numbers in secondary keys (`extra_data.get("target_phone")`). Always inspect both fields and invoke contact resolution if the string is non-numeric.
- **Prefix & Honorific Cleaning**: Strip conversational prefixes and honorifics before querying the contact database:
  - Remove conversational fillers: `"ngomong ke"`, `"bilang ke"`, `"sampaikan ke"`, `"chat ke"`.
  - Remove honorific titles: `"kak"`, `"bang"`, `"mas"`, `"mbak"`, `"bro"`, `"pak"`, `"bu"`, `"si"`.
- **Sanitize Internal Identifiers**: Filter out WhatsApp internal `@lid` identifiers from contact phone numbers; `@lid` is an internal account ID, not a routable E.164 phone number.
- **Deduplication & Ambiguity Handling**:
  - Keep contacts unique by normalized phone number in SQLite.
  - If a search query matches multiple contacts with distinct phone numbers, do not pick arbitrarily. Halt execution and return a confirmation prompt listing the matching contacts for the user to choose.

### Quoted Context Ingestion & Demonstrative Pronoun Guards
When handling commands that reference previous messages ("kirim vn ini ke laptop", "simpan foto ini ke folder"):
1. **Baileys Quoted Context Extraction (`contextInfo.quotedMessage`)**:
   - In the Baileys message listener, inspect `message.extendedTextMessage.contextInfo.quotedMessage`.
   - Detect quoted media types: `audioMessage` (VN), `imageMessage`, `videoMessage`, `documentMessage`.
   - Download the quoted media buffer immediately and attach as a `quoted_media` payload along with `quoted_text` so downstream intent handlers receive the full target media.
2. **Demonstrative Pronoun Hijack Guard in Contact Forwarding**:
   - Contact resolution regexes (e.g. `kirim\s+(?:pesan|wa)?\s*(?:ke|kepada)\s+([a-zA-Z0-9_\s]+)`) greedily capture demonstrative pronouns (`ini`, `itu`, `tersebut`) as contact names, triggering false-positive address book searches.
   - **Rules**:
     - Evaluate desktop routing keywords (`ke laptop`, `ke desktop`, `ke pc`, `di desktop`) BEFORE contact forwarding patterns.
     - Filter out standalone pronouns (`ini`, `itu`, `sini`, `situ`, `tersebut`) from contact candidate names.
     - If `quoted_media` is present in the message payload, route directly to media save & clipboard handlers.
3. **Multi-Type Media Ingestion (Video, Photo, Audio, Documents)**:
   - Handle `videoMessage` alongside `imageMessage` and `audioMessage`.
   - For photos: save to `Documents/clipboard mahiru/foto/` and inject `CF_DIB` bitmap into host clipboard.
   - For videos: save to `Documents/clipboard mahiru/video/` and copy the absolute local file path to host clipboard.
   - For documents/audio: save to dedicated folders and copy paths to host clipboard.

### WhatsApp Multi-Modal Outgoing Dispatch (Text + Native Voice Note PTT)
When enabling the assistant to forward messages to contacts or third parties ("kirim pesan dan VN ke [nama]: [pesan]"):
1. **Compound Intent Parsing & Trigger Sanitization**:
   - Match compound forwarding intents (`kirim pesan dan vn`, `kirim vn ke`, `vn si [nama]`, `kirim wa ... sekalian vn nya`).
   - Strip conversational trigger tails (e.g. `sekalian vn nya`, `sama vn nya juga`) from the message payload before passing to speech synthesis and text dispatch, ensuring the assistant only voices the intended message content.
2. **Native WhatsApp PTT (Voice Note) Conversion via FFmpeg**:
   - WhatsApp renders standard `.mp3` or `.m4a` attachments as rectangular audio files, not authentic voice notes with waveform scrubbing.
   - Convert synthesized audio to WhatsApp-native Opus OGG:
     ```bash
     ffmpeg -y -i input.mp3 -c:a libopus -b:a 32k -vn output.ogg
     ```
   - Dispatch via Baileys with `{ audio: buffer, mimetype: 'audio/ogg; codecs=opus', ptt: true }`.
3. **Automated Testing Target Isolation**:
   - Strictly route automated test dispatches to dedicated test contacts or internal numbers during development to prevent accidental spamming of user contacts.

---

## 4. Hardware Remote Control & Bidirectional Ringing

### Bidirectional Device Ringing ("Saling Mengontrol")
In personal cross-device setups where either the PC or phone may be misplaced:
1. **Ringing Laptop from Phone**:
   - Maximize Windows system volume via virtual keystrokes:
     ```python
     import ctypes
     VK_VOLUME_UP = 0xAF
     for _ in range(50):
         ctypes.windll.user32.keybd_event(VK_VOLUME_UP, 0, 0, 0)
         ctypes.windll.user32.keybd_event(VK_VOLUME_UP, 0, 2, 0)
     ```
   - **Never use `winsound.Beep()`**: Modern Windows 10/11 laptops have no motherboard piezoelectric buzzers and modern audio drivers (Realtek/Intel) do not route kernel beeps to audio endpoints, executing in total silence.
   - Use Windows Multimedia API `winsound.PlaySound()` pointing to standard Windows system sound files (`C:\Windows\Media\Ring01.wav` or `Alarm01.wav`):
     ```python
     import winsound, os, threading, time
     def start_ring_laptop(timeout_secs=45):
         global _ringing_active
         _ringing_active = True
         wav_path = r"C:\Windows\Media\Ring01.wav"
         if not os.path.exists(wav_path):
             wav_path = r"C:\Windows\Media\Alarm01.wav"
         winsound.PlaySound(wav_path, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_LOOP)
         def _auto_stop():
             time.sleep(timeout_secs)
             stop_ring_laptop()
         threading.Thread(target=_auto_stop, daemon=True).start()

     def stop_ring_laptop():
         global _ringing_active
         _ringing_active = False
         winsound.PlaySound(None, winsound.SND_PURGE)
     ```
2. **Ringing Phone from Laptop (3-Way Audible Emergency Alert)**:
   - Visual push notifications or silent WhatsApp messages are easily missed when a phone is lost or muted. Implement a 3-way parallel alert:
     1. **Web Frontend Siren (Immediate Loud Audible Tone)**: When phone UI / browser is open, poll `/api/phone/alarm_status`. If `ringing: true`, trigger Web Audio API dual-tone siren (alternating 880Hz and 1200Hz every 250ms) connected to `AudioContext.destination` and trigger continuous haptic vibration via `navigator.vibrate([400, 200, 400, 200])`.
     2. **Termux Background Poller**: Mobile polling daemon checks `/api/phone/alarm_status`. When active, forces device media and ring volume to maximum (`termux-volume stream music 15` and `termux-volume stream ring 15`) and speaks an alert loop via `termux-tts-speak`.
     3. **WhatsApp Emergency PTT**: Simultaneously send an emergency WhatsApp alert and native voice note to ensure user gets notified even if web and Termux pollers are asleep.

### Remote PC Actions via Agent Daemon
- **Lock PC**: `ctypes.windll.user32.LockWorkStation()`
- **Media Keys**: Simulate virtual keys (`VK_MEDIA_PLAY_PAUSE`, `VK_MEDIA_NEXT_TRACK`, `VK_VOLUME_MUTE`).
- **Power Management**: Wrap `shutdown /s /t 60` and `shutdown /a` with clear user feedback.

### Remote Media Queueing & Tab Hygiene (YouTube & Spotify)
- **Zero-Tab Proliferation on Queued Tracks**:
  When a user queues songs ("tambahkan ke antrean", "nambahin ke playlist youtube [lagu]"), never invoke `webbrowser.open()` immediately to prevent spawning duplicate background tabs that play simultaneously or clutter the browser.
  - Ingest track metadata (video ID, title, and duration in seconds via lightweight watch-page scraping).
  - If a track is actively playing, push to an in-memory queue.
  - Run a background worker tracking `time.time() >= current_track["end_at"]`. When advancing, focus the browser window and send `Ctrl+W` (`press_combination(VK_CONTROL, 0x57)`) to close the previous video tab before opening the next track URL.
  - For batch multi-song playlists ("masukin lagu A sama B dengan nama playlist X"), construct YouTube dynamic playlist URLs:
    ```text
    https://www.youtube.com/watch_videos?video_ids=id1,id2,id3
    ```
    YouTube natively handles sequential playback without third-party API keys or OAuth.
- **Reentrant Lock (`threading.RLock`) in Player State Machines**:
  In player state managers where `add_to_queue()` checks `if not self.current_track:` and calls `self.play_track()` under a lock, using standard non-reentrant `threading.Lock()` causes an instant **deadlock** on the second lock acquisition, locking the server worker thread indefinitely until request timeout. Always initialize with `self.lock = threading.RLock()`.
- **Fast-Path Action Feedback vs Status Keywords**:
  Avoid generic checks like `if "status" not in reply.lower():` when appending real-time detail payloads. If the fast-path template contains the word "status" ("Mengecek status lagu..."), the real detail message is dropped. Explicitly check `if action in ("view_queue", "view_playlist")` and overwrite `reply_text = action_info["detail"]` directly.

### Mobile File & Media Export: Gateway Dispatch over Local Downloads
- **The WebView Download Drop & Storage Permission Friction**:
  Serving files (CCTV snapshots, screenshots, screen recordings, generated docs) via client-side download buttons (`<a download>`, blob URLs) on mobile WebViews suffers from expired user gesture locks, silent download drops, and file management friction on phones.
  - Replace local download buttons with a 1-tap **Direct Messaging Dispatch** button (e.g. `sendMediaToMyWa('cctv')`).
  - The backend sends the file directly to the user's WhatsApp/Telegram thread with clean metadata captions.
  - This eliminates UI button crowding on mobile cards (<400px viewports), bypasses mobile browser download sandboxes, and keeps media files permanently organized in chat history.

### Windows Window Focusing & Presentation Controls
- **Never Call `ShowWindow(hwnd, SW_RESTORE)` (9) on Maximized Windows**: In Win32 API, `SW_RESTORE` restores both minimized AND maximized windows back to un-maximized size. Calling it when focusing causes maximized windows to "Restore Down" into small floating windows. Only invoke `SW_RESTORE` if `IsIconic(hwnd)` is true (minimized). If not minimized, bring it to front safely with `SetForegroundWindow(hwnd)`.
- **PowerPoint Dual Window Architecture (`screenClass` vs `PPTFrameClass`)**: When Slide Show is running, PowerPoint has two distinct top-level windows: `screenClass` (the full-screen projection) and `PPTFrameClass` (the editor behind it). Generic title searching matches the editor first, pulling it to the front and breaking the presentation. Always prioritize `screenClass` when slideshow is running; send navigation keys (`VK_RIGHT`, `VK_LEFT`, `VK_SPACE`, `VK_ESCAPE`) directly to `screenClass`. Only send `F5` / `Shift+F5` to `PPTFrameClass` when no `screenClass` exists.
- **Deep Browser Tab Tree Scanning (Windows UI Automation vs Window Title Match)**:
  Matching active window titles fails when multiple tabs share a domain (e.g. two YouTube tabs: "Playlist Lagu Rohani" vs "Mazmur Tanggapan") or run on localhost ("9Router"). The OS window title only exposes the currently active tab.
  *Pattern*: Use `uiautomation` (`win.TabControl().GetChildren()` / `WalkTree` with `ControlType.TabItemControl`) to inspect all open tab names across all Chrome/Edge windows in memory. Match the query keywords against tab names, bring the parent window to the foreground via `user32.AttachThreadInput` + `SetForegroundWindow`, and activate the target tab directly via `tab.GetSelectionItemPattern().Select()` or `tab.Click()`.
- **Autonomous Worker Keyword Guard on Window Switching Commands**:
  Natural language intent routing that intercepts keywords like "hermes" or "cmd" for autonomous code execution must exclude navigation/window-switching verbs (e.g. `pindah ke tab hermes`, `fokus ke terminal hermes`, `buka window cmd`). Otherwise, window switching commands get hijacked into background coding tasks that spawn empty terminals.

### Autonomous Server-Side Alt+Tab Cycling
- Stepping Alt+Tab by sending discrete HTTP requests every 400ms across mobile networks (Tailscale/LAN) causes network jitter, drops on Android long-press touch cancellation (`contextmenu`), and gets trapped on the first step.
- Implement an autonomous server-side thread loop (`_run_alt_tab_cycle`):
  1. On touch/mouse down (`alt_tab_press` / `alt_tab_hold`), the server holds `VK_MENU` (Alt), presses `VK_TAB` once to open the Task Switcher, waits an initial repeat delay (500ms), and then automatically cycles `VK_TAB` every ~400ms in a background loop.
  2. On touch/mouse up (`alt_tab_release`), the server immediately sets a stop event and releases `VK_MENU` within <50ms, instantly locking onto the selected window.
  3. Prevent Android long-press context menus using `oncontextmenu="event.preventDefault()"` and bind both touch (`touchstart`, `touchend`, `touchcancel`) and mouse events (`mousedown`, `mouseup`, `mouseleave`).

### Live Desktop Stream Full-Resolution Capture (gdigrab) & Self-Healing MJPEG Parsing
- **The Hardcoded 720p Crop Trap**:
  Hardcoding `-video_size 1280x720` on `ffmpeg -f gdigrab -i desktop` does NOT scale the screen; it crops a fixed 1280x720 box from the top-left of 1080p (1920x1080) displays. The live stream appears cut off on the right and bottom while static screenshots (`ImageGrab.grab()`) capture full 1920x1080.
  *Rule*: Omit `-video_size` on `gdigrab` input so FFmpeg grabs native display resolution (`1920x1080`). Use `-vf "scale=1280:-2"` on the output filter graph to downscale bandwidth efficiently (~70KB per frame) without cropping.
- **MJPEG Byte-Stream Delimiter Deadlock (`\xff\xd8` vs `\xff\xd9`)**:
  When parsing multipart MJPEG frames from an FFmpeg stdout pipe, searching for EOI (`\xff\xd9`) from index 0 instead of starting after SOI (`\xff\xd8`) creates an unrecoverable deadlock if stray bytes or truncated headers exist (`b < a`). Because `buf.find(b"\xff\xd9")` always returns the index before `a`, `b > a` remains `False` forever, `buf` balloons to hundreds of MBs, and the stream completely freezes.
  *Rule*: Always discard leading garbage before SOI (`if a > 0: buf = buf[a:]`), search EOI strictly after SOI (`b = buf.find(bytes([0xff, 0xd9]), a + 2)`), loop to extract all queued frames, and emit `Content-Length` headers in multipart boundaries.
- **FastAPI Non-Blocking Stream Proxy Lifecycle**:
  In HTTP proxies forwarding MJPEG/video streams via `requests.get(url, stream=True)`, passing a single integer timeout (`timeout=10`) causes the connection to drop on any 10s idle gap.
  *Rule*: Set `timeout=(5, None)` (5s connect timeout, infinite read timeout) and wrap `req.iter_content` in a generator with `finally: req.close()` to cleanly terminate upstream subprocesses on client disconnect.

### In-Memory Camera Snapshot Disk Sync for Outgoing Gateways
- **The Stale Attachment Trap**:
  Streaming live camera snapshot bytes directly to the HTTP client without persisting to disk (`camera_snapshot.jpg` in app static assets) leaves secondary features (e.g. WhatsApp outgoing media dispatch `/api/laptop/send_media_to_wa`) reading stale, days-old image files from disk.
  *Rule*: Always save the freshly captured JPEG frame buffer to disk immediately upon capture, and verify file freshness (<60s) before dispatching to external messaging gateways, auto-capturing a fresh frame if stale.

### Remote CCTV Surveillance: Audio Detection, Intercom & DirectShow Exclusive Lock
- **DirectShow Camera Exclusive Lock Trap**:
  In Windows, webcam drivers (DirectShow `dshow`) enforce an **exclusive device lock**. If a live MJPEG stream process (`ffmpeg -f dshow -i "video=..."`) is running, a secondary FFmpeg process attempting to open the same camera for recording fails instantly with `I/O error: Could not run graph (device already in use)`.
  *Rule*: Never spawn separate concurrent FFmpeg processes against the same DirectShow video device. To support recording while monitoring, either:
  1. Have the client request a recording transition where the single capture worker muxes/teed video and microphone audio into MP4 while streaming frames, or
  2. Maintain a single Python frame reader loop that broadcasts frames to HTTP streaming clients and pipes frames to an FFmpeg recording process stdin.
- **Two-Way Audio Intercom (Push-to-Talk to Host Speakers)**:
  To allow mobile users to speak through remote PC speakers:
  1. Mobile UI records voice chunks on button hold using HTML5 `MediaRecorder` (`audio/webm` or `audio/wav`).
  2. On button release, POST the blob to `/api/camera/talk`.
  3. Host agent plays a brief (150ms) chime tone followed by the user audio directly to default Windows speakers using `ffplay -nodisp -autoexit -loglevel quiet <file>`, providing an instant walkie-talkie experience with zero external dependencies.
- **Ultra-Low Latency Live Microphone Streaming (Raw PCM WebSocket vs HTTP Buffer Delay)**:
  - *The MJPEG Video Limitation*: Standard web CCTV streams use MJPEG (`multipart/x-mixed-replace`), which carries zero audio channels.
  - *The HTTP Audio Buffer Trap*: Streaming live mic audio via HTTP (`<audio src="/stream.mp3">`) forces a 1.5–3 second playback buffer in mobile browsers (Android Chrome/WebView) to prevent jitter, causing severe audio-video desync.
  - *The Real-Time Solution (<150ms Latency)*:
    0. Report the root cause in plain text BEFORE executing any fix when the user asked for text-first diagnosis.
    1. Host captures raw PCM from DirectShow microphone with low-delay input buffering:
       `ffmpeg -y -fflags nobuffer -flags low_delay -probesize 32 -analyzeduration 0 -f dshow -rtbufsize 100M -thread_queue_size 1024 -i "audio=Microphone Array..." -vn -sn -dn -ac 1 -ar 16000 -af "highpass=f=120, lowpass=f=7000, volume=0.9, acompressor=threshold=-15dB:ratio=4:attack=5:release=100" -f s16le -flush_packets 1 pipe:1`
       Never pass `-bufsize` on a raw `s16le` pipe output — it is a bitrate-buffer flag for encoded streams, not a PCM chunk control, and mis-buffers the pipe. Never pass `-sample_rate`/`-channels` as dshow INPUT options for audio-only capture — recent ffmpeg builds reject them (`Could not set audio only options`, open fails with I/O error); set rate/channels on the output side (`-ac 1 -ar 16000`) only. Always set `-rtbufsize` on the `dshow` input because the mic is opened twice concurrently (VU-meter monitor + live stream) and the default DirectShow buffer drops samples under contention.
       dshow capture runs ~20% slow for the first ~0.5s (warmup) then locks to realtime — discard the first 2 chunks when benchmarking throughput, or you will misdiagnose a permanent underrun.
    2. WebSocket endpoint (`/ws/camera/live_audio`) emits 4096-byte chunks (2048 samples = 128ms @16kHz mono 16-bit) directly to client as binary frames. Never use 1024-byte (32ms) chunks — per-frame WebSocket overhead quadruples and any single jittered frame becomes an audible gap. Fix EVERY identical handler (backend `main.py` win32 branch AND `laptop_agent/agent_server.py`); duplicated handlers drift apart silently.
    3. Mobile client queues incoming Int16 frames as Float32 into a FIFO sample queue; a 100ms pump merges everything queued into ONE `AudioBuffer` per tick and schedules it with `BufferSourceNode.start(nextPlayTime)`. One source per tick (not one per WS frame) means no gaps or overlaps between chunks — this is what makes audio smooth instead of choppy/robotic.
    4. **Prefill, Drop-Guard & Drift Clamping (Prevent Gaps, Doubling & Delay Pile-Up)**:
       - Prefill: hold first playback until ~300ms of samples are queued, so the stream survives network jitter from the first second.
       - Drop corrupt frames: skip all-zero packets (capture dropout) and odd-byte-length frames before queueing.
       - Overrun: if the queue exceeds ~800ms (long stall), drop oldest samples and re-anchor `nextPlayTime = now + 0.06` so delay snaps back to live instead of piling up.
       - Underrun: if `nextPlayTime` falls behind `currentTime`, re-anchor to `now + 0.06`; if it runs more than ~0.6s ahead, pull it back — never schedule retroactively, which stacks overlapping buffers into doubling/screeching.
    5. **Mandatory DSP Limiter & PTT Mute Guard**:
       - Route stream through `HighpassFilter (120Hz) -> DynamicsCompressorNode (Threshold -18dB, Ratio 12:1) -> GainNode -> Destination` to prevent speaker clipping and howling runaway.
       - During Push-to-Talk (PTT) intercom recording, set `liveGainNode.gain.setValueAtTime(0.0, audioCtx.currentTime)` and restore on release to eliminate walkie-talkie feedback loops.
    6. Call `audioCtx.resume()` inside the click handler to satisfy mobile autoplay policies. Total latency is ~80ms with 0s buffer lag.
- **Real-Time Sound Activity & Volume Detection (Zero External C-Extensions)**:
  To detect audio spikes or speech near the host camera without heavy dependencies:
  Stream raw PCM audio from the DirectShow microphone array:
  ```bash
  ffmpeg -f dshow -i "audio=Microphone Array..." -f s16le -ac 1 -ar 16000 pipe:1
  ```
  In a Python background daemon, read 0.1s chunks (3200 bytes), unpack via `struct.unpack('<1600h', chunk)`, and compute RMS energy:
  ```python
  rms = math.sqrt(sum(s * s for s in samples) / len(samples))
  db = 20 * math.log10(rms + 1e-9)
  ```
  Expose `sound_detected` (when `db > threshold`) and current dB levels to the UI for live VU meters and intrusion/noise alerts.

### Mobile Virtual Touchpad: Multi-Touch Gestures & Browser Locking
- **The Browser Gesture Interception Trap**:
  On mobile browsers (Android Chrome/WebView), swiping across a virtual trackpad triggers browser pull-to-refresh, page overscroll, or text highlighting, stalling pointer events.
  *Rule*: Lock the trackpad element and its parent container with strict touch cancellation:
  ```css
  touch-action: none !important;
  -webkit-user-select: none !important;
  user-select: none !important;
  overscroll-behavior: none !important;
  ```
- **Two-Finger Vertical Scroll Bridge**:
  To support authentic trackpad 2-finger scrolling without moving the cursor:
  1. Inspect `e.touches.length`: if `>= 2`, enter scroll mode.
  2. Compute vertical touch midpoint: `midY = (touches[0].clientY + touches[1].clientY) / 2`.
  3. Calculate `deltaY = midY - lastMidY`.
  4. Stream scroll event via WebSocket (`wheel,<deltaY>`) or HTTP POST to `/api/laptop/mouse/scroll`.
  5. Windows host calls `ctypes.windll.user32.mouse_event(0x0800, 0, 0, int(-deltaY * multiplier), 0)` (`MOUSEEVENTF_WHEEL = 0x0800`), providing smooth 60 FPS scrolling identical to physical laptop trackpads.

### Remote Studio Ergonomics & Deck Hierarchy (Mobile Remote Control)
- **Visual Feedback Loop Placement**:
  When remotely controlling a PC from a mobile phone, placing the virtual touchpad far away from the live screen feed forces the user into constant vertical scrolling between seeing what is on screen and controlling the pointer.
  *Rule*: Place the Touchpad & Remote Keyboard **directly beneath the Live Desktop Stream**. The user's gaze remains on the live display above while their thumb drives cursor movement and taps virtual keys below with zero scroll jitter.
  *Ergonomic Hierarchy*:
  1. **Physical CCTV Camera** (at the top: physical room surveillance).
  2. **Instant Desktop Screenshot** (quick single-frame status glance).
  3. **Live Desktop Video Stream** (real-time 1920x1080 display).
  4. **Touchpad & Remote Keyboard** (direct thumb control surface).
  5. **Workstation Grid** (app launchers, tabs, volume, power).

### Mobile Card Action Bar Anti-Overflow Patterns (<400px Viewports)
- **The Inline Button Border Overflow Trap**:
  Placing multiple action buttons with icons and text labels (e.g. `Mulai Live`, `Rekam`, `Bicara PTT`, `Snapshot`) inside a horizontal container (`flex items-center gap-2` or `flex justify-between`) next to card titles inevitably overflows card boundaries on narrow mobile screens (360px–400px), causing buttons to clip or stick out past card borders.
  *Responsive Layout Patterns*:
  - **Clean Header**: Reserve card headers strictly for Title + Status Badge + 1–2 icon-only utility buttons (`Snapshot`, `Fullscreen`).
  - **Dedicated Control Decks**: Place multi-action button groups in a dedicated responsive grid below the video monitor:
    - Mobile: 2-column grid (`grid grid-cols-2 gap-2 pt-2`).
    - Tablet/Desktop: 4-column row (`sm:grid-cols-4 gap-2`).
  - **Full-Width Messaging Dispatch vs Local Downloads**:
    Remove cluttered `<a download>` and "Unduh" buttons. Replace with single full-width WhatsApp dispatch buttons (`Kirim ke WhatsApp 📲`) styled with `w-full` inside a border-t container.

---

## 5. Cross-Device Clipboard & Notification Delivery

### Directional Capabilities & Android Framework Realities
When designing continuous clipboard synchronization across PC and mobile over Tailscale/LAN:
1. **PC to Mobile (Text - Automatic Background Sync vs WhatsApp Push)**:
   - On Windows host, use `user32.GetClipboardSequenceNumber()` (Win32 API) via `ctypes` for zero-overhead change detection. It returns an integer incremented on EVERY clipboard change across all Windows applications. Polling this every 0.3s has ~0% CPU load and avoids locking the clipboard.
   - **Win32 Clipboard Sequence Watcher Concurrency Race Condition**: Win32 increments `GetClipboardSequenceNumber()` the instant an application begins writing to the clipboard, but large applications (e.g. Chrome, MS Word, VS Code) hold a write lock and populate `CF_UNICODETEXT` over a 30–80ms window. If a background watcher thread updates its tracked sequence number (`last_seq = curr_seq`) on the first iteration while `get_text()` returns `""`, it locks the new sequence number into memory and never re-reads. The copy event is dropped entirely.
     *Rule*: When `curr_seq != last_seq`, execute a bounded retry loop (3 attempts with 50–80ms backoff) for `get_text()` before concluding the clipboard is empty or non-text. Only advance `last_seq = curr_seq` after text is verified or retries complete.
   - **Android 10–15 Framework Background Clipboard Lockout (`ClipboardService.java`)**:
     Android framework explicitly enforces `isCallerDefaultImeOrFocused()`, blocking background apps from writing or reading clipboard data (`setPrimaryClip` / `getPrimaryClip`) unless the app has active window focus or is an active IME (keyboard). No ADB AppOps (`SYSTEM_ALERT_WINDOW`, `WRITE_CLIPBOARD`) can bypass this on non-root devices without Accessibility Services.
   - **Dual-Message WhatsApp Direct Push Pattern (`Ctrl + Alt + C`)**:
     To provide instant, friction-free clipboard access on mobile without opening a terminal, dispatch clipboard content to the user's messaging thread in **two separate messages**:
     1. *Message 1 (Header Indicator)*: `📋 *[CLIPBOARD DARI LAPTOP]*\n(Teks disalin di bawah ini ya...)`
     2. *Message 2 (Raw Pure Text)*: The exact copied text string without headers, prefixes, or formatting, allowing the user to 1-tap copy/forward on mobile without manual text editing.

2. **Mobile Notification Header & Task Clarity**:
   - In mobile companion notifications (`termux-notification`), **never set the primary title (`--title`) to generic stage names** (e.g. `"🌸 Mahiru • Mahiru — Pengingat Santai 🌸"`). Mobile status bars and lockscreens collapse to one line by default, completely burying or clipping the actual task name.
   - **Rule**: Set `--title` explicitly to the task title and priority badge (`🌸 <Title> (<Priority>)`, e.g. `🌸 Tugas Sir Sasongko P3 (P3 - Penting ⚡)`), and place deadlines, necessities, and conversational recommendations in the content body.

3. **Mobile to PC (Unified Zero-Friction Android Share Target for Text & Media)**:
   - `termux-clipboard-get` is text-only and cannot extract raw bitmap data or resolve `content://` image URIs. Furthermore, background polling of `termux-clipboard-get` on Android 14 is blocked by framework security policy and jams the Termux:API IPC queue.
   - **Unified Android Share Sheet (`ACTION_SEND`) via `~/bin/termux-file-editor` & `~/bin/termux-url-opener`**:
     Android native sharing is 100% immune to OS background clipboard restrictions across all Android versions (10–14+) and requires no Accessibility Services. When the user highlights text in WhatsApp/Chrome, taps a link, or selects a photo in Gallery and picks **Share -> Termux**, Android invokes `~/bin/termux-file-editor "$1"` or `termux-url-opener "$1"`.
     - Inspect `$1`: if URL, POST text JSON to `/api/clipboard/text`.
     - If image MIME/extension (`jpg|png|webp|bmp`), stream binary multipart to `/api/clipboard/image`.
     - If text file, read content and POST JSON to `/api/clipboard/text`.
     - Deliver an instant feedback toast via `termux-toast` ("✨ Disalin ke Laptop! Siap Ctrl+V").
   - **Pure Ctypes Windows Clipboard Manager (No pywin32 Dependency)**:
     - **Image Injection**: Convert image bytes to in-memory BMP via PIL (`img.save(buf, format='BMP')`). Strip the 14-byte `BITMAPFILEHEADER` (`bmp_bytes[14:]`) and allocate global movable memory (`GMEM_MOVEABLE = 0x0002`). Pass memory handle to `ctypes.windll.user32.SetClipboardData(8, h_mem)` (`CF_DIB = 8`). The image is immediately pasteable across all Windows applications via **`Ctrl+V`**.
     - **Decoupled Text/Image Storage**: Taking a screenshot (Snipping Tool `Win + Shift + S`) puts `CF_DIB` into Windows clipboard and clears `CF_UNICODETEXT` (`None`). Never blank out the synchronized text endpoint when an image format is copied; cache the last known non-empty text string independently so mobile text pullers are not disrupted.

### 4. WhatsApp-Powered Universal Mobile-to-PC Clipboard Gateway
- **Why Native Share Sheet Fails in WhatsApp**: In WhatsApp on Android, long-pressing or highlighting text in chat bubbles presents only `[Reply, Star, Info, Copy, Forward]`; there is **no native Android Share menu option** for chat text in WhatsApp's action bar.
- **Android 14 Background IPC Jam**: Background polling of `termux-clipboard-get` on Android 14 is blocked by framework security policy and jams the `Termux:API` IPC queue, causing all subsequent Termux:API commands (even `termux-clipboard-set` and `termux-toast`) to freeze or time out.
- **The WhatsApp Gateway Alternative**: Leverage the host's WhatsApp bot/bridge (Baileys/Fonnte). Allow the user to forward any chat message, document, or photo directly to the bot with an intent/caption like `"kirim ke laptop"`, `"copy ke laptop"`, or `"salin ke laptop"`.
  - On the host backend:
    - If text: invoke `clipboard_manager.set_text(text)`.
    - If image: decode `image_base64`, convert to `CF_DIB` bitmap via ctypes, and invoke `clipboard_manager.set_image(image_bytes)`.
    - Return an instant WhatsApp confirmation: *"Sudah disalin ke clipboard laptop! Tinggal tekan Ctrl+V di laptop."*
  - This bypasses all mobile OS clipboard restrictions, requires zero mobile terminal configuration, and works seamlessly over any network (Wi-Fi, cellular, Tailscale).

---

## 6. Mobile Inbound Notification Interception (Android NotificationListenerService & E-Wallet QRIS)

When an Android application needs to automatically capture incoming financial transactions (QRIS payments, e-wallets, bank alerts):

### Framework Reality: Web vs Native Sandbox
- **Web / WebView Boundary**: Web applications, PWAs, and Android WebView JavaScript sandboxes **CANNOT** intercept Android system notifications from third-party applications under any circumstances. Android framework enforces process isolation; only native Android services declaring `NotificationListenerService` can receive notification events.
- **Native Android `NotificationListenerService` Requirements**:
  1. Declare service in `AndroidManifest.xml` with system permission guard:
     ```xml
     <service
         android:name=".service.QrisNotificationListenerService"
         android:label="FinSmart QRIS Listener"
         android:permission="android.permission.BIND_NOTIFICATION_LISTENER_SERVICE"
         android:exported="true">
         <intent-filter>
             <action android:name="android.service.notification.NotificationListenerService" />
         </intent-filter>
     </service>
     ```
  2. **Non-Bypassable Manual User Authorization**: Android framework strictly forbids enabling Notification Access programmatically. Applications must detect authorization status via `NotificationManagerCompat.getEnabledListenerPackages(context).contains(context.packageName)` and route users directly to system settings:
     ```kotlin
     val intent = Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS)
     context.startActivity(intent)
     ```
  3. **OEM Aggressive Battery Optimization Trap (XOS / MIUI / ColorOS)**: OEM battery cleaners terminate background notification listener services during screen-off sleep. Prompt users to whitelist the app from battery restrictions via `Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS`.

### E-Wallet & Bank Regex Parsing Heuristics
Package name filtering and resilient multi-regex extraction:
- **GoPay (`com.gojek.app`)**:
  - Sample: *"Pembayaran Berhasil! Kamu telah membayar Rp15.000 ke Teh Sri."*
  - Amount regex: `(?:Rp|IDR)\s*([\d\.]+)`
  - Merchant regex: `(?:ke|pada)\s+([^,\.\n]+?)(?:\.|\s+berhasil|\s*$)`
- **ShopeePay (`com.shopee.id`)**:
  - Sample: *"Pembayaran Berhasil: Pembayaran sebesar Rp 25.000 ke Warung Nasi Goreng telah berhasil."*
  - Amount regex: `(?:Rp|sebesar\s*Rp)\s*([\d\.]+)`
  - Merchant regex: `(?:ke|pada)\s+([^,\.\n]+?)(?:\s+telah|\.|\s*$)`
- **SeaBank (`com.seabank.id`)**:
  - Sample: *"Transaksi Berhasil: Pembayaran QRIS sebesar Rp12.000 ke Bakso Solo berhasil."*
  - Amount regex: `(?:sebesar\s*Rp|Rp)\s*([\d\.]+)`
  - Merchant regex: `(?:ke|pada)\s+([^,\.\n]+?)(?:\s+berhasil|\.|\s*$)`
- **BCA / myBCA (`com.bca`, `com.bca.mybca`)**:
  - Sample: *"m-Transfer / QRIS Berhasil: Pembayaran Rp 18.000 ke Teh Sri."*
  - Amount regex: `(?:Rp)\s*([\d\.]+)`
  - Merchant regex: `(?:ke|pada)\s+([^,\.\n]+?)(?:\.|\s*$)`

### Deduplication Hash Window Rule (Preventing Double-Deduction)
E-wallets routinely dispatch secondary notifications following successful payments (e.g. cashback rewards, coin updates, or receipt banners).
- Compute deduplication hash: `sha256("${packageName}_${amount}_${timestamp / 60000}")` (quantized to 60-second sliding buckets).
- If hash exists in the local 5-minute memory ring-buffer, drop the notification immediately to prevent deducting user balance twice.

---

## 7. Native Offline-First Android Architecture (Replacing Brittle CLI Daemons & WebViews)

When mobile users need reliable task management and deadline reminders that survive host PC shutdowns, network drops, and aggressive mobile battery killers (Infinix XOS, MIUI, ColorOS):

### The Terminal Daemon & WebView Failure Pattern
1. **Background CLI Daemon Death (Termux / Termux:API)**:
   Running Python/Node background loops in Termux relies on userland sandboxes. Despite `termux-wake-lock`, OEM battery managers (e.g. Transsion XOS `PowerMaster`) terminate background processes during screen sleep. Furthermore, companion APIs like `termux-notification` get silenced by features like XOS "Pengingat AI", and `termux-dialog` commands hijack active foreground activities (knocking users out of games/YouTube).
2. **WebView Online-Only Fragility**:
   Wrapping a remote web server (`100.x.y.z:port` or HTTPS) inside an Android WebView fails completely when the laptop is powered off or outside the network. The WebView renders `net::ERR_CONNECTION_REFUSED`, completely locking the user out of viewing tasks, checking them off, or scheduling alarms.

### Complete Native Offline-First Architecture
1. **Local Persistent Storage (SQLite Engine - 0ms Offline Access)**:
   - Build a lightweight native SQLite database (`SQLiteOpenHelper`) directly in the Android APK.
   - The app opens with zero latency even in Airplane Mode or when the PC is off.
   - Full offline CRUD: users can view, filter (Semua, Hari Ini, Belum Selesai, Selesai), search, add, edit, and complete tasks locally.
   - Track sync metadata per record: `sync_status` (`SYNCED`, `PENDING_INSERT`, `PENDING_UPDATE`, `PENDING_DELETE`) and `last_synced_at`.

2. **Smart Two-Way Watermark Synchronization**:
   - Probe server connectivity with bounded timeouts (3s connect, 4s read).
   - When the host PC is online (Tailscale MagicDNS, Funnel, or Wi-Fi LAN):
     - **Push**: Send pending local changes (`PENDING_INSERT` -> POST `/api/tasks`, `PENDING_UPDATE` -> PUT `/api/tasks/{id}`, `PENDING_DELETE` -> DELETE `/api/tasks/{id}`). Update local state to `SYNCED` on success.
     - **Pull**: Fetch all tasks from host (`GET /api/tasks`). Upsert into local SQLite without overwriting pending local mutations.
     - **Feedback**: Display clear indicators (`🟢 Laptop Online` / `⚪ Offline (HP)`).

3. **`AlarmManager.setAlarmClock()` for Unstoppable Reminders**:
   - Standard alarms (`setExactAndAllowWhileIdle`) can still be batched or throttled during deep Doze mode on customized Android skins (Infinix XOS).
   - **Rule**: Use `AlarmManager.setAlarmClock(AlarmClockInfo, pendingIntent)`. In Android framework (API 21+), `setAlarmClock` is treated as a physical alarm clock ringer. The OS guarantees exact millisecond wakeup from deep sleep, displays the system alarm clock icon, and is completely immune to OEM battery limiters.

4. **Multi-Stage Staged Proactive Alarms**:
   - Register progressive alarm stages per active pending task:
     - Stage 0: H-24 Jam (H-1) -> "Besok ada deadline penting! 📅"
     - Stage 1: H-3 Jam -> "Tinggal 3 jam lagi! ⏰"
     - Stage 2: H-1 Jam -> "PERHATIAN! 1 jam lagi deadline! ⚠️"
     - Stage 3: Saat Deadline (H-0) -> "WAKTU HABIS! Kumpulkan sekarang! 🚨"

5. **Direct In-Notification Actions (`BroadcastReceiver`)**:
   - Provide interactive action buttons directly on the notification banner:
     - `✅ Selesai`: BroadcastReceiver directly marks the task completed in SQLite, cancels remaining task alarms, dismisses the notification, and triggers an asynchronous background sync to the laptop without pulling any Activity to the front.
     - `⏳ Tunda 10m` / `⏳ Tunda 1 Jam`: Re-registers an exact snooze alarm via `AlarmScheduler.scheduleSnooze()`.

6. **Reboot Survival (`BootReceiver`)**:
   - Register `RECEIVE_BOOT_COMPLETED` and `MY_PACKAGE_REPLACED` in `AndroidManifest.xml`.
   - On device boot, `BootReceiver` queries local SQLite and re-schedules exact alarms for all pending future tasks automatically.

7. **Anti-Pitch-Black Aesthetic Guard for Companion & Sacred UIs**:
   - Avoid pure pitch-black themes (`#000000` / `#161115`) for companion/devotional apps. Apply warm cozy cream backgrounds (`#FFFBF5`), warm card whites (`#FFFFFF`), soft rose/burgundy accents, and amber/gold highlights.
   - For Catholic 73-book canon, KWI liturgical calendar syncing, Angelus/Regina Caeli seasonal alarms, and direct client Gemini AI REST integration, see `references/liturgical-and-offline-apps.md`.

---

## 8. Common Pitfalls & Traps

| Pitfall | Root Cause | Preventive Rule |
| :--- | :--- | :--- |
| **`AlarmManager` Doze Throttle on Aggressive Skins (Infinix XOS / MIUI)** | Standard `setExactAndAllowWhileIdle()` can still be delayed during deep Doze on certain Transsion/Xiaomi ROMs. | Use `AlarmManager.setAlarmClock(AlarmClockInfo, pendingIntent)`; Android treats it as a physical clock alarm and guarantees exact wakeup. |
| **WebView Zero-Offline Fragility** | Relying solely on a WebView wrapper around a host LAN/Tailscale server renders the app completely unusable (`ERR_CONNECTION_REFUSED`) when the laptop is off. | Implement a local-first SQLite database (`SQLiteOpenHelper`) on device with background push/pull sync. |
| **Notification Action Foreground Hijack** | Launching an Activity to handle "Selesai" or "Tunda" from a notification pulls the app to the front and knocks the user out of active games or videos. | Handle notification actions via `BroadcastReceiver` with background database updates and toast feedback. |
| **`android:gravity="baseline"` Linker Error** | Setting `android:gravity="baseline"` on `LinearLayout` fails AAPT2 resource linking (`'baseline' is incompatible with attribute gravity`). | Use `android:gravity="bottom"` or child layout gravity; baseline alignment is controlled via `android:baselineAligned="true"`. |
| **Material 3 Token Dimens Missing at Compile Time** | Calling `resources.getDimensionPixelSize(com.google.android.material.R.dimen.m3_btn_height)` fails when the project's Material dependency variant does not export that token. | Calculate dynamic dimensions programmatically: `(dp * resources.displayMetrics.density).toInt()`. |
| **Web Browser Notification Listener Fallacy** | Assuming Web / PWA or Android WebView can intercept system notifications from other installed apps. Web sandbox strictly isolates process permissions. | Implement notification interception strictly inside native Android APKs via `NotificationListenerService`. |
| **OEM Notification Listener Sleep (XOS/MIUI)** | Transsion XOS or MIUI task killers terminate background `NotificationListenerService` during screen sleep, causing missed QRIS notifications. | Request `ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS` during onboarding and check listener re-bind status on application resume. |
| **E-Wallet Notification Duplicate Deduction** | E-wallet apps dispatching two notifications for one QRIS payment (e.g. payment confirmation followed by cashback coins) causes two transactions. | Implement 60-second deduplication ring buffer keyed by `(package_name, amount, rounded_minute_timestamp)`. |
| **Demonstrative Pronoun Hijack in Contact Forwarding** | Contact regexes (`kirim\s+...\s+([a-zA-Z0-9_\s]+)`) greedily capture words like "ini" ("Kirim vn ini ke laptop"), triggering unwanted address book searches instead of desktop media handling. | Evaluate desktop/laptop routing (`ke laptop`, `ke desktop`) and quoted media handling BEFORE contact forwarding regexes; sanitize pronouns ("ini", "itu", "tersebut") from contact candidate names. |
| **Missing `videoMessage` Ingestion in Chat Bridges** | Baileys bridge listener checks only `imageMessage` and `audioMessage`, causing incoming video messages or video captions to be dropped as empty strings. | Register `videoMessage` in Baileys message extraction, download video stream buffers, save to `Documents/clipboard mahiru/video/`, and copy the resolved file path to Windows clipboard. |
| **Tailscale Ingress Domain Desync on Host Renaming** | Host is renamed in Tailscale (changing `<name>.<tailnet>.ts.net`) while Funnel configuration and client auto-upgrade redirect scripts hardcode the old hostname, resulting in NXDOMAIN (`ERR_NAME_NOT_RESOLVED`). | Check active domain via `tailscale status --json`, run `tailscale funnel reset && tailscale funnel --bg <port>`, and sanitize Android `SharedPreferences` on `onCreate` to invalidate deprecated hostnames. |
| **Missing Java Runtime for Android Gradle Build on Windows CLI** | Running `./gradlew assembleDebug` in Windows Git-Bash fails with `JAVA_HOME is not set` when system Java is absent. | Export `JAVA_HOME="/c/Program Files/Android/Android Studio/jbr"` and prepend `$JAVA_HOME/bin` to `PATH` before invoking Gradle. |
| **HTTP Audio Stream Buffer Lag on Mobile CCTV** | Mobile browsers enforce a mandatory 1.5–3s buffer on HTTP audio (`<audio src="...">`) to avoid jitter, creating severe audio-video desync. | Stream raw PCM 16kHz mono via WebSocket (`/ws/camera/live_audio`) and render directly through Web Audio API `AudioContext` buffer queue (~80ms total latency). |
| **Mobile Card Header Button Jamming on Multi-Feature CCTV Cards** | Cramming multiple action buttons with text labels inside card headers overflows narrow mobile viewports (<400px), clipping buttons outside card borders. | Keep headers minimal (title + status badge); place multi-action buttons in dedicated 2x2 mobile grids below the monitor feed. |
| **`threading.Lock` Deadlock on Reentrant Player State Calls** | Calling `self.play_track()` inside `with self.lock:` in `add_to_queue()` causes a silent thread deadlock when using non-reentrant `threading.Lock()`. | Always use `threading.RLock()` for player and queue managers where state transition methods cross-call. |
| **Browser Tab Proliferation on Queued Media** | Launching every queued track via `webbrowser.open()` spawns dozens of duplicate background tabs that clutter the desktop or play audio concurrently. | Queue songs in memory with duration tracking; close prior tabs (`Ctrl+W`) before launching next track, or construct dynamic playlist URLs (`watch_videos?video_ids=...`). |
| **Mobile Card Download Fragmentation vs Gateway Dispatch** | Local file download buttons on mobile cards cause Android WebView download drops, gesture timeouts, and horizontal card overflow on <400px screens. | Route file exports directly through the messaging bot (`/send_media_to_wa`) with full-width action buttons. |
| **Action Feedback Blindness on Keyword "Status"** | Checking `if "status" not in reply.lower():` to avoid duplicating reports discards the real-time detail payload if the template contains "status" (e.g. "Mengecek status lagu..."). | Set `reply_text = action_info["detail"]` directly for observational actions (`view_queue`, `view_playlist`), or guard with `action in (...)`. |
| **Git Checkout Regression During Layout Refactoring** | Reverting or checking out files from git (`git checkout <file>`) to clean up or rearrange markup silently destroys recent uncommitted JavaScript helpers, state bridges, or WebSocket connections. | Always inspect `git diff` and stash or backup uncommitted functions before restoring base templates. Never assume git reflects your active uncommitted workspace state. |
| **Android WebView Anchor Click Download Drop** | Creating an in-memory anchor `<a href="..." download>` and calling `a.click()` fails silently in Android WebView because `setDownloadListener` is only triggered when navigation occurs or the scheme is intercepted. | Pair anchor clicks with an immediate `window.location.href = url` fallback; server responses with `Content-Disposition: attachment` trigger Android `DownloadManager` without leaving the page. |
| **Remote Keyboard Buffer Submit vs Real-Time Typing** | Requiring users to type into an input buffer and tap 'Submit' or press Enter breaks the seamless remote desktop illusion. | Listen to `input` events on the input element, compute character delta length, and stream new characters immediately to `/api/keyboard/type` and backspaces to `/api/keyboard/key`. |
| **Companion Interactive Voice Latency Delay** | Running on-the-fly zero-shot TTS and RVC models on consumer GPUs adds 2–4s delay to companion interaction buttons (Sapa, Merajuk, Puji, Teh), making tactile taps feel laggy. | Pre-render an authentic pool of character voice clips directly on the GPU host, store in static assets (`/static/audio/interact/`), and return the URL for instant 0ms audio playback. |
| **Phoneme Mismatch in Character Voice Synthesis** | Feeding non-native language text to voice models fine-tuned on Japanese anime audio corrupts phoneme synthesis or triggers robotic fallback voices. | Decouple spoken audio (`japanese_voice`) from UI subtitles (`reply`), keeping spoken kana/kanji under 20 chars for sub-3s call latency. |
| **Conversational Trigger Tail Leakage in Message Forwarding** | Appending phrases like "sekalian vn nya" to voice forwarding commands leaks the instruction into the synthesized audio. | Strip conversational trigger tails (`re.sub(r"\s*(?:sekalian|sama)?\s*vn(?:\s*nya)?...", "", msg)`) before TTS synthesis. |
| **Non-Opus Audio Attachment vs Native WhatsApp PTT** | Sending raw `.mp3` files to WhatsApp contacts renders as static file attachments without waveforms or inline voice note playback. | Transcode to Opus OGG (`-c:a libopus -b:a 32k`) and dispatch with `{ audio: buffer, mimetype: 'audio/ogg; codecs=opus', ptt: true }`. |
| **High-Reasoning Model Latency Trap in Duplex Calls** | Routing real-time voice calls to high-thinking LLMs (e.g. `gemini-3.8-flash-high`) forces thousands of internal reasoning tokens, adding 7–10s TTFT latency and creating awkward 10–13s dead silences per sentence. | Use Dual-Brain routing: reserve high-reasoning models for code/terminal tasks; route duplex voice calls to zero-thinking models (Groq LPUs ~350ms or zero-thinking Gemini). |
| **Autonomous CLI Agent Stdout Truncation in Chat Gateways** | Capturing raw CLI stdout dumps ANSI escape codes and tool calls that exceed chat message length limits (>2500 chars). Truncating stdout from the front drops the final answer and generated file paths. | Execute agent workers with `--format stream-json --yolo`, parse event objects to extract clean text replies, and keep host terminal displays clean. |
| **Missing Post-Worker Database State Synchronization** | Failing to save the agent worker's completion summary into the message history database leaves the conversational model believing the task is still in progress. | Always call `save_chat_message()` upon worker completion and update an in-memory job state cache (`LAST_HERMES_JOB`). |
| **Rigid Follow-up Intent Blindness on Agent Artifacts** | User asking "mana filenya" after task completion triggers full LLM intent classification, which lacks current filesystem awareness and hallucinates that the task is still running. | Intercept follow-up file queries in `fast_intent_detection` to immediately dispatch the latest cached artifact or scan the desktop without waiting for LLM inference. |
| **Termux:API Background Polling IPC Jam on Android 14** | Running an infinite polling loop calling `termux-clipboard-get` in the background on Android 14 triggers repeated `ClipboardService` security denials, saturating and locking the `Termux:API` IPC queue and causing subsequent commands (`termux-clipboard-set`, `termux-toast`) to freeze or hang. | Never poll `termux-clipboard-get` in a background daemon on Android 14. Use WhatsApp forward commands, explicit notification tap actions, or native Android Share targets. |
| **WhatsApp Chat Bubble Share Menu Absence** | WhatsApp on Android does not expose an Android Share sheet target for highlighted chat text bubbles (only Copy and Forward). | Do not instruct users to 'Share -> Termux' for WhatsApp chat text. Provide a forward-to-bot intent (`kirim ke laptop`) or a 1-tap notification bar trigger. |
| **Snipping Tool Clipboard Format Overwrite** | Taking a screenshot in Windows (`Win+Shift+S`) places `CF_DIB` into the clipboard and leaves `CF_UNICODETEXT` as `None`. Host clipboard watchers that wipe text state when `CF_UNICODETEXT` is `None` cause mobile pollers to lose text. | Cache the last known valid text independently from image updates, and separate text vs image endpoints. |
| **Timestamp-Based Clipboard Polling Lockout** | Comparing float timestamps (`since_ts`) across heterogeneous host/mobile clocks or float rounding differences causes polling daemons to silently drop clipboard updates if the timestamp does not strictly increment. | Synchronize cross-device clipboards based on direct content comparison (`text != last_synced_text`) paired with Win32 sequence numbers (`GetClipboardSequenceNumber()`), rather than relying solely on float timestamps. |
| **Windows Clipboard Sequence Number Concurrency Drop** | `user32.GetClipboardSequenceNumber()` changes before the writing application releases the clipboard lock. An immediate `last_seq = curr_seq` assignment when `get_text()` returns `""` skips all subsequent read attempts for that sequence. | Retry `get_text()` up to 3 times with 50–80ms delays when `curr_seq != last_seq` before advancing `last_seq`. |
| **Termux Multi-Daemon Autostart Single-Process Blindness** | Guarding `start.sh` in `~/.bashrc` with `pgrep -f 'notifier.py'` fails to revive `clip_sync.py` if only the clipboard daemon crashes or is killed by Android battery optimization. | Check all companion daemons concurrently: `(pgrep -f 'notifier.py' && pgrep -f 'clip_sync.py') || bash start.sh`, and acquire `termux-wake-lock`. |
| **KDE Connect UDP Broadcast Drop on Tailscale/VPN** | KDE Connect device discovery relies on UDP broadcast (ports 1714-1764). Mesh VPNs (Tailscale) and Windows Defender Firewall block or drop UDP broadcasts, causing frequent disconnects, reconnect loops, or "No devices found". | Use direct TCP/HTTP Tailscale endpoints (`100.x.y.z:port`) with explicit persistent notification triggers for deterministic, zero-discovery-failure synchronization. |
| **Win32 External Clipboard Timestamp Amnesia** | Host API only updates its internal clipboard timestamp during its own `set_text` endpoint, not when the user presses `Ctrl+C` in third-party desktop apps (browser, editor). Mobile pull pollers checking `since_ts` assume nothing changed and never sync. | Monitor `user32.GetClipboardSequenceNumber()` in a 0.3s background thread on the host. When the sequence number changes, fetch text, update `last_synced_text`, and refresh `last_change_ts` so mobile pullers detect the change. |
| **Termux Daemon Subprocess PATH Omission** | In Termux background/nohup scripts, `/data/data/com.termux/files/usr/bin` is not inherited in `os.environ["PATH"]`. Calls to `termux-clipboard-set`, `termux-toast`, or `termux-notification` fail with `FileNotFoundError`. | Explicitly set `os.environ["PATH"] = "/data/data/com.termux/files/usr/bin:" + os.environ.get("PATH", "")` or use absolute binary paths. |
| **Android 14 Framework Clipboard Lockout vs ADB Appops** | Granting `READ_CLIPBOARD_IN_BACKGROUND` via ADB writes to system settings and persists across reboots, but Android 14 framework (`ClipboardService.java`) still checks foreground window focus or active Accessibility Service, silently returning empty strings to background terminal scripts. | Do not promise 100% background CLI clipboard reading on Android 14 without an Accessibility Service. For seamless zero-tap sync, recommend native KDE Connect (`winget install KDE.KDEConnect` + Android APK) or use a foreground user-gesture trigger (`clip` / notification action). |
| **Compiler Auto-Run Fallacy (g++ / clang++)** | Expecting compiler flags (`-o`) to execute the compiled binary. C++ compilers are strictly AOT compilers without execution flags; `-o` is an output naming flag only. | Always chain binary execution via `&& ./<binary>` or wrap in a build script/runner (`make`, bash alias). |
| **64-bit Pointer Truncation in Windows ctypes Clipboard** | Calling `GlobalAlloc` or `GlobalLock` in 64-bit Python without setting `argtypes` and `restype = ctypes.c_void_p` defaults to 32-bit `int`, truncating memory addresses. | Set `.restype = ctypes.c_void_p` and explicit `.argtypes` on all Win32 memory and clipboard functions (`GlobalAlloc`, `GlobalLock`, `SetClipboardData`, `GetClipboardData`). |
| **Bitmap Header Truncation for CF_DIB** | Passing full BMP file bytes into `SetClipboardData(CF_DIB, ...)` corrupts the image because Windows DIB expects `BITMAPINFOHEADER` directly, not the 14-byte `BITMAPFILEHEADER`. | Strip the first 14 bytes (`data[14:]`) from standard PIL BMP output before copying to global memory. |
| **Uvicorn Without Reload In-Memory Stale Code** | Editing Python backend routes while Uvicorn runs without `reload=True` leaves old endpoints active in memory. | Gracefully terminate the specific backend PID without disturbing sibling companion daemons (Node Baileys or Agent). |
| **Android 10+ Background Clipboard Lockout** | Google blocks background access to `ClipboardManager`. Background polling loops in Termux (`termux-clipboard-get`) return empty strings when another app is focused. | Never rely on passive background polling for mobile clipboard extraction. Use an explicit user action (notification action button, Quick Tile) or an Android AccessibilityService. |
| **Termux:API Image Clipboard Incompatibility** | `termux-clipboard-get` only handles UTF-8 text; Android copies images as scoped `content://` URIs inaccessible to CLI stdout. | Ingest mobile images via system Share Target / HTTP multipart upload, then have the PC host agent inject raw bitmap data into Windows Clipboard (`CF_DIB`). |
| **Netstat-Only Process Kill on Reconnecting Services (Status 440)** | Killing processes solely by checking listening ports (`netstat -aon \| findstr :8001`) misses processes currently in exponential backoff / reconnect loops (where the socket is closed). | Enforce single-instance process management via recorded PID files (`wa_bridge.pid`) or kill by exact process image name (`taskkill /F /IM node.exe`) rather than listening state alone. |
| **Android WebView Silent STT Hang** | `webkitSpeechRecognition` exists in WebView memory but fails silently without Google Speech service. Blocks fallback recorders if checking `if (!recognition)`. | Never use Web Speech API in Android WebViews. Use `MediaRecorder` + server-side Faster-Whisper. |
| **Mobile Autoplay Policy Blocking Async Audio** | Calling `new Audio(url).play()` in async `fetch` callback gets rejected with `NotAllowedError` because user activation gesture expired. | Play audio using `AudioContext.decodeAudioData()` buffer playback (already primed during call start gesture) or set `settings.mediaPlaybackRequiresUserGesture = false` in WebView. |
| **Assistant Audio Self-Mute Loop** | Phone loudspeaker audio is captured by the phone's microphone within 15–20ms, tripping VAD barge-in and muting the assistant. | Set `isSpeaking = true` during playback and bypass mic volume checks in VAD loop. Allow barge-in via manual tap. |
| **Jarring HTTP Warning Popups** | Rendering manual banners/buttons to switch to HTTPS frustrates users and looks broken. | Execute an instant silent auto-upgrade redirect in `<head>` before DOM render. |
| **Mute Traps UI in "Listening..."** | Muting microphone only disables audio tracks without flushing the recorded chunk. | Tapping mic while speaking must act as Push-to-Send (flush chunk immediately to backend). |
| **Android WebView Mic Insecure Context** | HTTP non-localhost triggers Insecure Context in Chromium. `chrome://flags` is ignored by WebViews. | Always serve WebRTC/microphone endpoints over Tailscale HTTPS with valid TLS certificates. |
| **WhatsApp Target Phone Missing** | LLM places phone numbers in `target_phone` instead of `action_param`. | Check both fields and run `resolve_contact_number()` if the value contains alphabetic characters. |
| **False-Positive Split on "Pesan"** | Regex matches the word "pesan" inside normal text ("tes pesan dari..."). | Only treat "pesan" as a delimiter if followed by explicit punctuation (`[:=]`) or line breaks. |
| **Ambiguous Contact Dispatch** | Multiple contacts share nicknames or duplicate names. | Group search results by phone number. If count > 1, prompt user for confirmation before sending. |
| **Global Syntax Error in Python Functions** | Assigning to a variable before declaring `global` in the same outer function. | Place `global var_name` at the very top of the enclosing function before any read or assignment. |
| **Android Build Java Version** | Missing `JAVA_HOME` in shell environment when running Gradle. | Point `JAVA_HOME` to Android Studio JBR (`C:\Program Files\Android\Android Studio\jbr`). |
| **Audio Sent as `image_url`** | Sending `data:audio/...` inside `image_url` to Chat Completion APIs causes payload loss. | LLM receives no user words and hallucinates based on system prompt examples (e.g., Discord). Transcribe via Whisper before LLM turn. |
| **Loudspeaker Self-Interruption** | Mic picks up assistant speech from phone speaker; naive volume VAD trips barge-in. | Request mic with `{ echoCancellation: true }` and lock VAD during assistant speech playback. |
| **Endless VAD Speech Detection** | Background room noise keeps static amplitude above threshold; silence timer never fires. | Enforce a hard maximum recording cap (5-6s) and adaptive noise floor estimation. |
| **Fast-Path Hijacking by Conversational Words** | Keywords like "dengerin" or "putar" inside long complaints trigger media player actions. | Restrict media intent regex to short utterances (<10 words) and evaluate agent delegation keywords first. |
| **Rigid Beginning-of-String Regex on Delegation** | Using `re.match(r"^hermes")` fails when user prepends context or greetings. | Use `re.search` with word boundaries across the full message text. |
| **WhatsApp Calling via Baileys** | WhatsApp calls use separate SRTP/WebRTC signaling with ephemeral keys not supported in WhatsApp Web protocol. | Baileys only supports call detection & rejection (`rejectCall`). Never attempt live voice calls over Baileys; use PTT Voice Notes (`ptt: true`) or in-app WebRTC. |
| **Termux Dynamic Linker Symbol Error (`libcurl.so`)** | Upgrading `libcurl` without updating `openssl` causes missing symbol errors (`SSL_set_quic_tls_early_data_enabled`). | Include `openssl` in package upgrades (`pkg install -y openssl libcurl curl`). Use standard library Python `urllib.request` as a fallback downloader in setup scripts. |
| **Dual-Instance WhatsApp Web Conflict (Status 440)** | A) Two Node instances on the host sharing the same auth folder (caused by `process.kill('SIGKILL')` failing on Windows or port-based kill missing reconnecting processes). B) Copying the same auth folder to phone. | On Windows host, enforce single instance via `execSync('taskkill /F /PID ' + oldPid)`. For dual PC + Termux support, use WhatsApp Multi-Device: separate auth directories (`auth_info_baileys` vs `auth_info_termux`) and distinct browser signatures (`Desktop` vs `Safari`). |
| **Baileys QR Pairing Handshake Reconnect Trap (Status 515)** | When user scans QR, WA server sends keys and closes initial socket (status 515 restart required) to complete crypto negotiation. If pairing script exits on close, WA phone app times out with "Gagal menautkan perangkat". | Always catch non-logout closes in pairing scripts and immediately reconnect via `setTimeout(startSocket, 1500)` until `connection === 'open'`. |
| **WhatsApp Multi-Device Cooldown ("Coba Lagi Nanti")** | Multiple failed pairing attempts or concurrent handshakes trigger WA anti-abuse rate limiting (5-15 min cooldown) on that phone number. | Halt rapid connection attempts, ensure existing bridge instances are fully terminated, and allow cooldown to expire before re-scanning. |
| **Termux Native API vs Background Baileys on Mobile** | Running Node.js Baileys inside Termux consumes ~200MB RAM and is aggressively killed by OEM battery savers (Infinix XOS). | Offload 24/7 background tasks to `termux-notification` (Termux:API) with `termux-wake-lock`, running a lightweight Python daemon that syncs from PC when online and alerts natively when PC is off. |
| **Global JS Audio Function Name Collisions** | Defining identical function names (`playMahiruVoice`) in chat and call modules causes the latter to overwrite the former globally. | Separate audio function namespaces cleanly (`playChatAudio` vs `playVoiceCallAudio`). |
| **Termux Dialog Foreground App Hijack** | `termux-dialog` commands are Android Activities (`DialogActivity`, `SheetDialogActivity`). When invoked via `am start`, Android WindowManager forcibly pulls Termux:API to the foreground, knocking the user out of whatever app they were using (games, YouTube, browser) even if "Display over other apps" is granted. | Never use `termux-dialog` for passive reminders. Use `termux-notification` with action buttons (`--button1-action`), which runs fully inside Android SystemUI without disrupting or switching the active foreground app. |
| **Termux Dialog Decoupled Execution Trap** | Calling `termux-dialog` directly in the shell only prints selected JSON to stdout and exits without calling backend APIs. | Always wrap dialog calls in an execution handler script that parses stdout and fires the corresponding HTTP PUT/POST or DB update. |
| **Android 8+ Notification Channel Banner Suppression (Infinix XOS / OEM)** | Passing `--priority max` on `termux-notification` does not pop down a heads-up banner if the app's Notification Channel defaults to "No Banner / Tanpa Spanduk". | Instruct users to open Android Settings > App Management > Termux:API > Notifications > tap the specific category name > toggle "Spanduk / Banner / Tampilkan di Layar" to ON. |
| **Termux Dialog Sheet Title Omission** | In `termux-dialog sheet`, the `-t` title parameter is ignored by the BottomSheet layout; only `-v` array rows are rendered. | If task details must be visible in a modal dialog, use `termux-dialog confirm -t "<title>" -i "<message>"` or `termux-dialog radio`, or deliver full context in a notification banner. |
| **Termux Bash History Expansion Error (`!`)** | Exclamation marks (`!`) placed inside double quotes (`"..."`) in bash trigger `bash: !': event not found`. | Never use `!` inside double-quoted strings in Termux CLI or action strings; use single quotes or omit `!`. |
| **Infinix XOS AI Reminder Heads-Up Suppression** | On Infinix XOS (Transsion), "Intensitas Pengingat" defaults to "Pengingat AI", which suppresses heads-up pop-down banners for non-whitelisted apps (like Termux:API) even when "Spanduk" is toggled ON. Also, Android blocks heads-up drop-downs when the virtual keyboard is active. | Switch "Intensitas Pengingat" from "Pengingat AI" to "Ikuti Notifikasi Aplikasi" / "Kuat", and test heads-up banners with the virtual keyboard dismissed. |
| **Termux Dialog Sheet Clickable Row Trap (Dummy Title Row)** | In `termux-dialog sheet -v "..."`, every row in the array is rendered as an actionable button. Passing title/metadata headers into `-v` creates an accidental dummy button that registers as a selection and aborts the dialog without action. | Embed task titles and deadlines directly into real action buttons (e.g. `✅ Selesaikan: <task> (<due>)`, `⏳ Tunda (<duration>)`, `🔕 Matikan Pop-up`), ensuring 100% of rows perform actual work. |
| **Post-Dialog IPC Broadcast Transition Stall** | When `termux-dialog` dismisses, calling `termux-toast` synchronously right after `subprocess.run(termux-dialog)` sends an immediate IPC broadcast to `com.termux.api`. This wakes the dying package and stalls Android's window transition, stranding the user on the Termux:API screen instead of returning to the underlying app (WhatsApp, YouTube). | Do not invoke synchronous `termux-toast` upon dialog dismissal; let the Python script exit immediately so Android WindowManager restores the previous foreground task. |
| **Termux:API Task Stack Retention in Recent Apps** | If the user opened the Termux:API app manually (viewing Preferences or About screen), `TermuxAPILauncherActivity` sits in the package task stack. When `DialogActivity` finishes, Android falls back to `TermuxAPILauncherActivity`. | Swipe away/close `Termux:API` from Recent Apps (`☰`) so transient `noHistory="true"` dialog activities cleanly terminate the task stack and restore the previous foreground app. |
| **Adaptive Snooze Timeline vs Static Snooze Lockout** | Hardcoding static snooze timers (e.g. flat 1 hour) violates urgency stages (e.g., delaying critical <1h tasks by 60 minutes) and blocks repeated testing if `snooze_until` is persisted in prefs. | Dynamically calculate snooze durations from task urgency stages (CRITICAL: 10m, URGENT: 40m, TODAY: 2.5h, APPROACHING: 8h) and support a `--test` / `--force` flag to clear stale snooze locks during manual verification. |
| **Mobile Daemon Sleeping on Host Online** | Daemon completely idles when host is detected online, failing to show screen pop-ups on the user's phone for newly added tasks. | When host is online, keep syncing tasks every 30s and evaluate mobile screen pop-ups; only suppress duplicate WhatsApp messaging that the host already performs. |
| **Hardcoded Due Dates in Daemon Pop-up Invocations** | Passing static placeholders (e.g. `"13:00"`) when calling modal pop-ups breaks deadline display and adaptive snooze calculations. | Propagate the real task `due_str` / ISO datetime to the pop-up helper script. |
| **Mobile Daemon Death on Termux Restart** | Background daemons killed when the user closes Termux or restarts the phone. | Add idempotent autostart check (`pgrep ... || bash start.sh`) to `~/.bashrc` and invoke `termux-wake-lock` in `start.sh`. |
| **winsound.Beep Silent Failure on Laptops** | Calling `winsound.Beep()` targets legacy PC-motherboard buzzers (`beep.sys`). Modern Windows 10/11 laptops lack buzzer hardware and audio drivers do not route kernel beeps to audio endpoints, executing silently. | Use Windows Multimedia waveOut API `winsound.PlaySound()` with native WAV ringers (`C:\Windows\Media\Ring01.wav` or `Alarm01.wav`) with `SND_ASYNC \| SND_LOOP` and cancel with `SND_PURGE`. |
| **Silent Fatal Script Compilation Freeze** | A single syntax error in a monolithic frontend HTML `<script>` block (e.g., duplicated keyword `async async function ...`) halts parsing of the entire script during the initial browser compilation phase. Because execution aborts before attaching event listeners or running data fetchers (`fetchTasks`), the UI appears completely frozen and lists appear empty (0 tasks) with zero visual error messages. | Validate all modified inline script blocks using `node --check` or `new Function(code)` before deployment. Keep initialization and event listeners modular so independent deck features do not bring down core task grids. |
| **Android WebView Blob Download Drop** | Generating `blob:` URLs via `URL.createObjectURL(blob)` and clicking `<a download>` fails silently in Android WebViews because `DownloadListener` and `DownloadManager` only support `http://` and `https://` schemes. Programmatic clicks after `await fetch` are also blocked in mobile Chrome due to expired user gestures. | Always serve files from direct HTTP endpoints with `Content-Disposition: attachment`. Trigger direct URL navigation (`<a href="..." download target="_blank">` + `window.location.href = url`) or offer 1-tap WhatsApp media dispatch. |
| **Virtual Touchpad HTTP Request Lock & Teleport ("Diam Lalu Lompat Instan")** | Guarding mouse movement with an in-flight flag (`isSendingMouse`) while dispatching HTTP POST requests holds movement frames for 80–150ms over Tailscale/LAN, causing the cursor to freeze. Releasing the lock dumps 40–50px of accumulated movement in a single instant warp. | Stream trackpad delta coordinates (`m,dx,dy`) over a persistent WebSocket connection at 60 FPS without request locking. Preserve sub-pixel fractional remainders (`smoothRemainderX`) across frames and bypass proxies with direct `ctypes.windll.user32.mouse_event` calls. |
| **Live Stream gdigrab 720p Resolution Crop** | Forcing `-video_size 1280x720` on FFmpeg `gdigrab` input crops 1080p monitors to top-left rather than scaling down. | Omit `-video_size` on `gdigrab` input to capture full native monitor resolution (1920x1080). |
| **In-Memory Camera Snapshot Disk Write Omission** | Proxying webcam snapshot bytes directly to HTTP responses without writing to disk leaves outgoing WhatsApp dispatch sending stale days-old images. | Persist captured JPEG buffer to disk immediately upon capture and verify timestamp freshness (<60s) before dispatching. |
| **Mobile Virtual Touchpad Browser Gesture Interference** | Mobile browser overscroll and pull-to-refresh intercept touch drag gestures on virtual touchpads. | Enforce `touch-action: none !important;` and `overscroll-behavior: none !important;` on the trackpad container, paired with linear subpixel accumulation. |
| **Mobile Card Action Button Border Overflow** | Placing 2–3 labeled action buttons side-by-side in horizontal flex rows on mobile cards overflows viewports <400px, clipping buttons or pushing them past card borders. | Use dedicated 2-column grids (`grid grid-cols-2 gap-2`) or a 2-tier layout (primary button on top, secondary grid below) with `truncate` on text labels. |
| **Live CCTV Audio Doubling & Melengking Feedback Runaway** | Unclamped Web Audio API chunk playback schedules delayed packets retroactively (`nextPlayTime = now`), causing multiple buffered chunks to play simultaneously (comb-filtering / flutter echo). Uncompressed mic signals clip into high-frequency screeching. | Queue frames into a FIFO sample queue drained by a 100ms pump (one merged buffer per tick, 300ms prefill, drop all-zero frames, 800ms overrun drop with re-anchor), insert a DSP chain (`Highpass 120Hz -> DynamicsCompressor brickwall limiter -> Gain 0.85`), and mute gain during PTT talk. |
| **Choppy / Putus-Putus Live Mic Audio** | 1024-byte WebSocket frames (32ms) multiply per-frame overhead so any jitter becomes an audible gap; `-bufsize` on an `s16le` pipe mis-buffers output; missing `-rtbufsize` drops samples when two FFmpeg processes share one DirectShow mic. | Emit 4096-byte (128ms) frames, use `-rtbufsize 100M -thread_queue_size 1024 -fflags nobuffer -flags low_delay -flush_packets 1` with no `-bufsize`, and patch all duplicate live_audio handlers, not just one. |
| **Choppy Playback Despite Healthy Server (Producer/Consumer Mis-split)** | Editing server capture code repeatedly when the producer is already realtime — every server-side fix looks plausible but changes nothing the user hears, because the gap/overlap happens in the client renderer. | Before touching code, timestamp arriving frames at the transport boundary and compare mean inter-arrival gap against the ideal frame duration (realtime ratio = ideal/mean). Ratio ≈ 1.0 with uniform frame sizes proves the producer healthy — stop editing the server and investigate the client (network path to phone, browser AudioContext throttling, competing features). Discard warmup frames before measuring; capture devices run slow for the first ~0.5s then lock to realtime. |
| **Theme CSS Substring Wildcard Text Inversion (`[class*="bg-..."] *`)** | Using loose attribute selectors like `body.theme-cream [class*="bg-rose-500"] *` to force white text on solid badges accidentally matches buttons with hover pseudo-classes (`hover:bg-rose-500/10`) or indicator dots, forcing button text to white-on-white. | Use exact class selectors (`.bg-rose-500:not(.keycap-btn):not([class*="/"]) *`) and define explicit contrast rules for keycap buttons across theme modes. |
| **Separated Screen Feed and Trackpad Ergonomics** | Placing the live desktop monitor and the virtual touchpad in distant card positions forces users to scroll constantly between viewing and interacting. | Anchor the virtual touchpad and remote keyboard directly beneath the live screen video feed for continuous thumb-to-eye feedback. |
| **MJPEG Stream Frame Delimiter Deadlock & Permanent Freeze** | Searching for EOI (`\xff\xd9`) from index 0 rather than after SOI (`\xff\xd8`) causes `b > a` to stay `False` forever when leading stray bytes exist, ballooning buffer memory and freezing the video stream permanently. | Discard garbage before SOI (`buf = buf[a:]`), search EOI strictly after SOI (`buf.find(bytes([0xff, 0xd9]), a + 2)`), loop to extract all buffered frames, and add `Content-Length` headers in multipart boundaries. |
| **FFmpeg Desktop 40 Mbps Bandwidth Choke & Proxy Read Timeout** | Capturing raw 1080p/4K MJPEG over-saturates network buffers (~40 Mbps), while FastAPI `requests.get(stream=True, timeout=10)` drops connections on momentary idle gaps. | Scale output via `-vf "scale=1280:-2" -q:v 5` (~70KB/frame), proxy with `timeout=(5, None)`, and close upstream connection in `finally`. |
| **Detached-Console Worker Pipe Break & Fake-Duration Report** | Spawning an agent worker with `CREATE_NEW_CONSOLE` detaches its stdout pipe, so result/log files stay empty (tens of bytes) while the worker falls back to a canned "task completed" template with a 2–3s duration. | Run workers attached/hidden with output redirected to files, require the structured result file to exist and be non-trivial before reporting success, and treat a missing result as failure with honest retry messaging, never a success template. |
| **Blanket FFmpeg Kill in Start Scripts** | `taskkill /F /IM ffmpeg.exe` in a startup script kills the live desktop/camera stream owned by the already-running agent, causing freeze/reconnect storms on every restart. | Never blanket-kill encoder binaries; kill only stale recorded PIDs (port-owner lookup or PID file) and leave healthy stream processes alive across restarts. |
| **Prompt Sanitizer Over-Trim** | Regex cleaners that strip leading/trailing conversational words also strip explicit preservation orders ("do not trim this command"), so long debugging tasks arrive at the agent truncated and finish as instant no-ops. | Constrain sanitizers to leading greetings/fillers only, never strip mid-prompt directives, and log pre/post-clean prompts to prove nothing load-bearing was removed. |
| **Single-Slot Clipboard Album Loss & Volatile Document Text** | Forwarding a multi-photo album sets the host clipboard once per image so only the last survives, and extracted PDF text kept only in memory is lost when the LLM call falls back. | Queue album images as files on disk (persist every attachment under Downloads with timestamped names), save extracted document text to disk alongside, and dispatch multi-image results as native multi-image/document sends, not clipboard sets. |
| **Unverified File-Op Success Claim** | Reporting "moved/copied N files" from worker stdout without a post-op directory listing lets empty moves pass as success. | After every file move/copy, re-list source and destination (directory listing + byte sizes) and attach the listing or screenshot as proof before claiming completion. |
| **Outer Window Title Matching Blindness on Multi-Tab / Localhost Browsers** | Matching window focus strictly by top-level OS window title fails when multiple tabs share domain (e.g. YouTube "Playlist" vs "Mazmur") or when web apps run on localhost ("9Router"), because background tab titles are invisible to Win32 title APIs. | Use Windows UI Automation (`uiautomation` / `TabItemControl`) to inspect all open tab names across all browser instances in memory, select the target tab element directly via `SelectionItemPattern`, and bring the window forward. |
| **Autonomous Worker Keyword Hijack on Window Switching Commands** | Intercepting keywords like "hermes" or "cmd" for autonomous code execution intercepts window switching requests ("pindah ke tab hermes"), spawning blank terminal jobs instead of focusing windows. | Exclude window navigation verbs (pindah, fokus, alih, switch, buka tab/window) from autonomous worker regex matchers. |
| **Emotional Mood Prompt Inconsistency in Voice Cloning** | Loading separate uncalibrated emotion prompt tensors (e.g. `prompt_cheerful.pt`) with divergent pitch/timbre causes sudden voice deepening, roughness, or autoregressive speed runaway. | Standardize and synchronize all emotional mood tensors to the gold-standard reference tensor (`prompt_gentle.pt`) and apply natural cadence smoothing (particle pauses `、`) on long clauses (>25 chars). |
