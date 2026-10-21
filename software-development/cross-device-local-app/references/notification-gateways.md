# Notification Gateways (WhatsApp & Discord)

Payload recipes and scheduler architecture for sending automatic reminders without paid SaaS dependencies.

## 1. WhatsApp Gateway Comparison: Local Web Bridge (Baileys) vs Fonnte API

| Feature | Local Bridge (Baileys / Node.js) | Cloud Gateway (Fonnte API) |
|---|---|---|
| **Cost & Quota** | 100% Free, Unlimited messages | Free tier limited to 1,000 msgs/month |
| **Incoming Voice Notes (VN)** | Raw Opus OGG downloaded directly | Stripped on Free tier (`"message": "non-text message"`, no URL) |
| **Outgoing Voice Notes (PTT)** | Native WhatsApp waveform (`ptt: true`) | Audio attachment (or stream via public URL) |
| **Dependency** | Laptop/PC must be online | Runs on cloud server |
| **Best For** | Full two-way voice companion & unlimited reminders | Low-maintenance setup without local Node.js |

---

## 2. Local WhatsApp Web Bridge (Baileys) Implementation

Running `@whiskeysockets/baileys` directly on the host machine provides complete control over inbound/outbound audio streams and avoids third-party payload stripping.

### Essential Dependencies
```bash
npm install @whiskeysockets/baileys qrcode qrcode-terminal express pino
```

### Critical Baileys Configuration & Traps
1. **Infinite "Menyinkronkan..." (Syncing) Trap**:
   - Connecting a personal WhatsApp account with years of chat history causes the phone's "Linked Devices" screen to hang indefinitely on "Menyinkronkan...".
   - **Fix**: Always pass `syncFullHistory: false` and `markOnlineOnConnect: true` to `makeWASocket`. This tells WhatsApp to skip transferring historical messages and immediately activate real-time event listeners.
2. **Self-Chat / "Message Yourself" (You) Trap**:
   - If the user links their primary WhatsApp account (rather than a secondary bot SIM), chatting with the companion takes place inside WhatsApp's built-in "Message Yourself" / (You) chat.
   - In self-chats, `m.key.fromMe` is ALWAYS `true`. Naively filtering `if (m.key.fromMe) continue;` completely silences user messages in self-chat!
   - **Fix**: Track bot-generated message IDs in a `Set`. Identify self-chat via `isSelfChat = jid.includes(myNumber)`. Only drop `m.key.fromMe` when `!isSelfChat`. If `isSelfChat`, drop only messages present in `botSentMsgIds`:
     ```javascript
     const botSentMsgIds = new Set();

     // When sending
     const sent = await sock.sendMessage(jid, { text: replyText });
     if (sent?.key?.id) botSentMsgIds.add(sent.key.id);

     // In messages.upsert
     for (const m of messages) {
       if (!m.message) continue;
       if (m.key.id && botSentMsgIds.has(m.key.id)) {
         botSentMsgIds.delete(m.key.id);
         continue; // Ignore companion's own reply
       }

       const myNum = sock.user?.id?.split(':')[0]?.replace(/[^0-9]/g, '') || '';
       const isSelfChat = m.key.remoteJid.includes(myNum);\n       if (m.key.fromMe && !isSelfChat) continue;
       // Process user message...
     }
     ```
3. **Native WhatsApp Voice Notes (PTT - Push-To-Talk)**:
   - Sending raw MP3 files renders as an audio document/attachment, not a voice bubble with green microphone waveforms.
   - **Fix**: Convert MP3/WAV to OGG Opus via ffmpeg in ~0.08s before sending:
     ```javascript
     execSync(`ffmpeg -y -i "${audioPath}" -c:a libopus -b:a 32k -vn "${tempOgg}"`);
     await sock.sendMessage(jid, {
       audio: fs.readFileSync(tempOgg),
       mimetype: 'audio/ogg; codecs=opus',
       ptt: true // Renders real WhatsApp voice note with waveform
     });
     ```
4. **Downloading Inbound Voice Notes**:
   - Download the raw buffer directly via `downloadMediaMessage`:
     ```javascript
     const buffer = await downloadMediaMessage(m, 'buffer', {}, { logger: pino({ level: 'silent' }) });
     // Forward buffer as base64 to FastAPI backend for ffmpeg conversion and speech recognition
     ```
5. **WhatsApp LID (Linked ID) Routing & Authorization Trap**:
   - In modern WhatsApp, messages sent from mobile clients often use privacy Linked IDs (`<digits>@lid`) rather than the sender's phone number (`<digits>@s.whatsapp.net`).
   - If the backend compares `sender` directly against `auth_phone`, messages will be dropped with `Sender not authorized`.
   - **Fix**: Baileys caches reverse mappings in `auth_info_baileys/lid-mapping-<lid>_reverse.json`. In the bridge, resolve the LID before forwarding or pass `remote_jid`:
     ```javascript
     const senderRaw = jid.split('@')[0].replace(/[^0-9]/g, '');
     let sender = senderRaw;
     if (jid.endsWith('@lid')) {
       const mappingFile = path.join(AUTH_DIR, `lid-mapping-${senderRaw}_reverse.json`);
       if (fs.existsSync(mappingFile)) {
         try {
           const mappedNum = JSON.parse(fs.readFileSync(mappingFile, 'utf8'));
           if (mappedNum) sender = String(mappedNum).replace(/[^0-9]/g, '');
         } catch (e) {}
       }
     }
     ```
   - When sending replies via `/send`, support sending to either `@lid` or phone number JID (`const jid = target.includes('@') ? target : `${cleanTarget}@s.whatsapp.net``).
6. **Concurrent Host Session Conflict (Status 440 `connectionReplaced` Loop) & Dual-Instance Traps**:
   - **Root Cause A (Windows Host Zombie Processes)**: In Node.js on Windows, `process.kill(oldPid, 'SIGKILL')` fails silently because Windows does not support POSIX signals. If a new bridge process starts while an older process is in a 15-second reconnect delay, `netstat` filtering for `LISTENING` will miss the old process. Both processes read and write `auth_info_baileys`, ping-pong kicking each other every 15 seconds.
     * **Fix**: In Node.js on Windows, enforce single-instance termination via `execSync('taskkill /F /PID ' + oldPid)`. In batch launchers, terminate zombie node processes via PowerShell:
       ```bat
       powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"name = 'node.exe' and CommandLine like '%%server.js%%'\" | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
       ```
   - **Root Cause B (Running on PC and Termux Simultaneously)**: WhatsApp Web Multi-Device allows up to 4 companion devices per phone number. Running both PC and Termux is fully supported without status 440 kicks IF AND ONLY IF:
     1. Each client maintains an independent auth directory (`auth_info_baileys` on PC vs `auth_info_termux` on Termux).
     2. Each client uses a distinct browser signature (`Browsers.windows('Desktop')` vs `Browsers.macOS('Safari')`).
     3. Pairing is performed independently via `pair.js` on Termux so WhatsApp registers it as Device 2.
     * **Smart Failover Dispatch**: In `notifier.py` on Termux, probe host availability over Tailscale (`http://100.x.y.z:8000/api/ping`). When the host laptop is online, bypass Termux WhatsApp dispatch so only the laptop sends messages, avoiding duplicate alerts. When the laptop goes offline, Termux takes over automatically.
7. **The Reconnect Message Sync Drop Trap vs Startup Backlog Flood**:
   - When Baileys disconnects and reconnects (or starts up after host sleep), WhatsApp delivers pending backlog messages in `messages.upsert` with `type === 'append'`, NOT `'notify'`.
   - Naively checking `if (type !== 'notify') return;` silently ignores every message received while offline or reconnecting. However, accepting `append` with a naive 30-minute window (`nowSec - msgTime > 1800`) and an in-memory `Set()` creates a catastrophic flood on server restart: because the in-memory Set is wiped, Baileys treats up to 30 minutes of replayed chat history as brand-new messages and forwards every queued command to the backend at once!
   - **Fix**: Record a startup timestamp on bridge initialization (`const startupSec = Math.floor(Date.now() / 1000)`). Drop any message whose `messageTimestamp` is earlier than `startupSec - 10`:
     ```javascript
     const startupSec = Math.floor(Date.now() / 1000);
     const processedMsgIds = new Set();

     sock.ev.on('messages.upsert', async ({ messages, type }) => {
       for (const m of messages) {
         if (!m.message) continue;
         const msgId = m.key?.id;
         if (msgId) {
           if (botSentMsgIds.has(msgId)) { botSentMsgIds.delete(msgId); continue; }
           if (processedMsgIds.has(msgId)) continue;
           processedMsgIds.add(msgId);
         }
         const msgTime = m.messageTimestamp ? Number(m.messageTimestamp) : null;
         // Drop messages older than bridge startup (skips offline backlogs on reboot)
         if (msgTime && (msgTime < startupSec - 10)) continue;
         // Process realtime message...
       }
     });
     ```

8. **Fast-Path Host Intent Matching & Non-Blocking Async Webhook Architecture**:
   - **The Monolithic LLM Bottleneck**: Forcing simple host commands (`lock`, `shutdown`, `open youtube`, `volume up`) to await a 25-second conversational LLM query causes severe delays. If the AI gateway is busy, the request times out and the fallback block sends a canned message (*"Ada apa sayang?"*) with `action: "none"`, spamming default greetings while failing to execute the command until minutes later.
   - **Regex / Keyword Fast-Path**: Intercept deterministic commands with sub-millisecond keyword/regex matching before invoking the LLM. If matched, immediately return the identified action and a predefined character response, bypassing the LLM entirely.
   - **Decoupling Action from Voice Rendering**: Never wait for neural voice generation (3-8 seconds) before triggering the physical host action (`/action`). Execute the OS action and dispatch the text confirmation immediately, offloading neural audio rendering to a background task so host actions execute in real time without lag.
   - **Preventing Async Event-Loop Starvation**: Webhook handlers declared as `async def` must wrap synchronous HTTP calls (`requests.post`) or heavy CPU tasks in `await asyncio.to_thread(...)`. Direct synchronous calls inside `async def` block Uvicorn's event loop, causing sequential message delivery to back up into multi-minute queues.

9. **WhatsApp Proxy Relay / Message Forwarding to Third-Party Contacts**:
   - In companion architectures, users frequently instruct the bot to send messages to third parties: e.g. *"kirim pesan ke 08123456789: halo bro besok jadi gak?"*.
   - **Regex Parsing & International Format Sanitization**:
     ```python
     wa_match = re.search(r'\b(?:kirim\s+(?:pesan|wa|chat)|chat|wa|titip\s+(?:pesan|wa))\s+(?:ke\s+)?(\+?62\d+|08\d+)(?:\s*[:=,]|\s+(?:bilang|isinya|pesan)?\s*[:=]?)\s*(.+)$', t, re.I)
     if wa_match:
         raw_num = wa_match.group(1).replace('+', '').replace('-', '').replace(' ', '')
         target_num = ('62' + raw_num[1:]) if raw_num.startswith('0') else raw_num
         msg_body = wa_match.group(2).strip(' :\"\'')
     ```
   - Dispatch to Baileys `/send` with target JID `f"{target_num}@s.whatsapp.net"`.
   - Reply to the user with an immediate confirmation containing the recipient number and message snippet, accompanied by an affirmative voice note.

10. **The WhatsApp Call (VoIP / Real-Time Voice Call) Protocol Boundary**:
   - **Protocol Reality**: Baileys operates strictly over the WhatsApp Web WebSocket protocol (JSON & Protobuf framing for messages and metadata).
   - **VoIP Isolation**: WhatsApp Voice and Video calls rely on a separate end-to-end encrypted WebRTC/SRTP signaling stack with ephemeral media keys routed through WhatsApp's media relay servers. These media exchange channels are not reverse-engineered or supported in Baileys.
   - **Baileys Scope**: Baileys can only listen for incoming call events (`sock.ev.on('call', ...)`) and reject them (`sock.rejectCall(id, from)`). It **CANNOT** initiate outbound VoIP calls, accept calls, or stream real-time bidirectional audio over WhatsApp.
   - **Rule**: Never attempt to build real-time full-duplex phone calls inside WhatsApp via Baileys. For WhatsApp audio interactions, use Voice Notes (Push-To-Talk `.opus` audio with `ptt: true`). For live duplex voice calls, route users to an in-app WebRTC / Web Audio interface (served over HTTPS) or an external SIP/VoIP trunk.

---

## 3. WhatsApp Integration via Fonnte (Cloud Gateway)

Fonnte links to WhatsApp via standard QR code (Linked Devices / Perangkat Tertaut):
- Setup: Register free at `https://fonnte.com`, open **Device / Perangkat**, and scan QR.
- Endpoint: `https://api.fonnte.com/send` (NOT `/send_message` which returns 404 HTML).
- **Free Tier Inbound Attachment Limitation**:
  - On the Free tier, Fonnte **does not forward incoming audio/media files** to the webhook. Fonnte strips the audio URL and sends `"message": "non-text message"`. If inbound voice note transcription is required, switch to the Local Baileys Bridge or use in-app mic capture.
- **Outbound Audio via Public URL Workaround**:
  - Multipart form upload `files={"file": ...}` is restricted on free plans.
  - **Fix**: Host the generated TTS MP3 under FastAPI `/static/audio/<filename>.mp3` exposed via Tailscale Funnel (`https://<node>.<tailnet>.ts.net/static/audio/...`). Pass `url: public_audio_url` in the Fonnte POST body — Fonnte fetches and delivers the audio to WhatsApp successfully.
- **Status handling pitfall**: Fonnte returns HTTP 200 even when failed (e.g. device disconnected, invalid quota). Always check `res.json().get("status") is True` explicitly, never rely on `res.status_code == 200`.
- **WhatsApp Anti-Spam "State 0" Trap (Reach-Out Time-Lock)**:
  - Freshly linked numbers dropping outgoing automated messages (`State: 0` in Fonnte log) require the target phone to send at least one inbound message (e.g. `"Halo"`) to complete encryption key exchange.

---

## 4. Discord Webhook Embeds & Persona Skinning

Discord accepts rich embeds via standard webhooks without requiring a bot token:
```python
import requests

def send_discord_webhook(webhook_url: str, title: str, description: str, priority_level: int, due_date: str, avatar_url: str = "", bot_name: str = "Assistant"):
    colors = {
        4: 0xE11D48, # Vivid Rose / Red Alert
        3: 0xFB923C, # Warm Coral / High
        2: 0xFBBF24, # Amber / Medium
        1: 0xF472B6  # Soft Sakura / Low
    }
    payload = {
        "username": bot_name,
        "avatar_url": avatar_url,
        "content": f"**[{title}]**",
        "embeds": [{
            "title": f"📌 {title}",
            "description": description,
            "color": colors.get(priority_level, 0xFBBF24),
            "fields": [
                {"name": "Deadline", "value": due_date, "inline": True},
                {"name": "Prioritas", "value": f"P{priority_level}", "inline": True}
            ],
            "footer": {"text": f"{bot_name} • Menemani setiap saat 💕", "icon_url": avatar_url}
        }]
    }
    res = requests.post(webhook_url, json=payload, timeout=10)
    return res.status_code in (200, 204)
```

---

## 5. Smart Adaptive Urgency Engine & Immediate Stage Transitions

Rather than flat reminder intervals (e.g. "every 30 mins"), scale notification cadence and companion tone dynamically based on remaining time ($\Delta t = \text{due\_date} - \text{now}$) and priority:
- `FAR_AHEAD` ($\Delta t > 3$ days): 1x / 24 hours (gentle planning nudge).
- `APPROACHING` ($1 < \Delta t \le 3$ days): every 8-12 hours (progress check-in).
- `TODAY` ($6 < \Delta t \le 24$ hours): every 3-4 hours (day-of priority alert).
- `URGENT` ($1 < \Delta t \le 6$ hours): every 45-60 minutes (imminent deadline alert).
- `CRITICAL` ($0 \le \Delta t \le 1$ hour): every 10-15 minutes (countdown siren).
- `OVERDUE` ($\Delta t < 0$): every 30-45m for first 3 hours, then every 3h.
- **Immediate Stage Transition Trigger**: Record `last_reminder_stage` in SQLite. When a task crosses into a new stage, fire an immediate notification regardless of interval timer so the urgency shift is felt instantly.

---

## 6. Conversational Voice Companion & Audio Tuning (Edge-TTS)

### Companion Voice Personality & Frequency Tuning
- Default `id-ID-GadisNeural` has a fundamental frequency around 190-200Hz, sounding like a formal, mature news anchor.
- For anime companion / waifu characters (e.g. Mahiru Shiina), pitch tuning (`pitch="+25Hz"` to `"+28Hz"`, `rate="+2%"`) shifts the voice into a sweeter, youthful timbre, but the underlying vocal DNA remains an Indonesian newsreader.
- Use conversational punctuation (frequent commas and ellipsis) in LLM system prompt outputs to produce gentle pauses and soft breathing intervals during TTS rendering.

---

## 7. Authentic Character Voice Transformation (RVC - Retrieval-based Voice Conversion)

To achieve 100% authentic character voice (matching the original anime seiyuu) while retaining fluent Indonesian speech, pair Edge-TTS with an RVC v2 voice conversion model:

### Architecture: TTS + RVC Post-Processing
1. **TTS Stage**: Edge-TTS generates clean, phonetically accurate Indonesian speech (`.wav` or `.mp3`).
2. **RVC Conversion Stage**: The generated audio is passed through a character-trained RVC model (`.pth` weights + `.index` feature retrieval). RVC replaces the vocal timbre, breathiness, and acoustic formant characteristics with the anime character's exact voice in <0.3s on CUDA (NVIDIA RTX 3050+).
3. **Dispatch**: Converted audio is saved to `/frontend/audio/` and dispatched as a native WhatsApp PTT voice note (`ptt: true`) or played in the Web/APK UI.

### Model Sourcing & Setup
- Source RVC v2 weights (`<character>.pth` ~50MB and `<character>.index` ~1-2MB) from HuggingFace (search `<character> rvc`). Prefer higher-epoch models (200-300 epochs) with clean index files.
- **Base Voice Cadence & Formant Clash ("Sounds Nothing Like Character" Trap)**: Standard Indonesian neural voices (e.g. `id-ID-GadisNeural`) have a sharp, staccato broadcast cadence and stiff consonant articulation that survives RVC conversion, causing the output to sound like a filtered news anchor. For soft, whispery anime characters, use a soft conversational multilingual base (e.g. `en-US-AvaMultilingualNeural` with soft rate `-8%`) or phonetically aligned seiyuu base audio.
- **Consonant & Breath Protection (`consonant_breath_protection`)**: Default is `0.33` to `0.5`, which aggressively preserves the source speaker's harsh unvoiced consonants and breathing patterns. Lowering `consonant_breath_protection` to `0.05 - 0.1` and raising `index_influence` to `0.85 - 0.95` allows RVC to fully replace breathiness and formant transitions with the character's authentic vocal DNA.
- **Target Fundamental Frequency (F0) Alignment**: Analyze the target character's reference audio with `librosa.pyin` or pitch tracker. For example, soft female anime voices (Mahiru Shiina) center at 326–341 Hz (E4–F4). If the base TTS audio already has a high fundamental frequency (~330Hz), setting RVC `pitch_lvl > 0` pushes the voice above 450Hz (chipmunk distortion). Keep `pitch_lvl = 0` or negative shifts (`-1` to `-2`) so the post-converted F0 lands exactly within the seiyuu's natural frequency band.
- **Pre-downloading `rmvpe.pt` to Prevent Download Timeout**: When using `pitch_algo='rmvpe+'`, `infer_rvc_python` downloads `rmvpe.pt` (~173MB) into the working directory on first invocation via Hugging Face Hub. Standard HTTP timeouts or CLI execution budgets frequently truncate the download mid-way (e.g. at 50%), causing corrupt model loads or pipeline hangs. Pre-download `rmvpe.pt` explicitly with `curl -L -o models/rmvpe.pt <url>` and pass `rmvpe_path` directly into `BaseLoader(rmvpe_path=...)`.
- **Double-Pitch Distortion Trap**: Never run RVC inference on base audio that has already been pitch-shifted (e.g. Edge-TTS generated with `pitch="+26Hz"`). Pitch-shifting the base audio distorts vocal formant ratios before RVC feature retrieval, causing the converted voice to sound robotic, unnatural, or indistinguishable from default TTS. Always synthesize a natural, clean base audio (`pitch="0Hz"`, `rate="+0%"`), and control pitch elevation entirely within the RVC model inference parameters (`pitch_lvl` parameter in `infer_rvc_python`).
- **The Intonation & Robotic Cadence Trap in Two-Stage TTS + RVC vs Zero-Shot TTS (OmniVoice)**:
  - RVC only converts voice timbre, formants, and pitch envelope; it does NOT alter speech rhythm, intonation, pauses, or mechanical cadence of the base TTS. If Microsoft Edge-TTS (`id-ID-GadisNeural`) is used as source, the output retains 100% of the robotic, stiff newsreader cadence regardless of how high-quality the RVC model is.
  - **Zero-Shot Voice Cloning Alternative (e.g. `k2-fsa/OmniVoice`)**: Synthesizes natural speech directly from text using a short 5-10s clean audio prompt (`ref_audio`) of the character without background music (BGM). Bypasses intermediate robotic TTS entirely, producing expressive character prosody and natural pauses. Fits within ~2.7GB VRAM (running smoothly on 6GB GPUs like RTX 3050 Laptop), generating ~3s of speech in ~1.6s on FP16 CUDA.
  - **The Hugging Face ASR Auto-Download Trap on `ref_text=None`**: In `OmniVoice.create_voice_clone_prompt(ref_audio, ref_text=None)`, if `ref_text` is omitted, the method invokes `self.load_asr_model()` to download a multi-gigabyte Whisper ASR model on-the-fly. On machines without `HF_TOKEN`, this triggers unauthenticated download rate limits or hangs on network timeouts. Slicing a clean 5-10s audio segment and supplying the exact reference transcript string (`ref_text`, obtainable from official subtitles via `yt-dlp --write-auto-sub --sub-lang ja`) skips ASR download completely, creating the `VoiceClonePrompt` in milliseconds.
  - **Pre-Caching `VoiceClonePrompt` & 0.02s MP3 Transcoding**: Voice clone prompts are static for a character. Compute and cache `VoiceClonePrompt` once at agent server startup to reuse across all requests. Transcode raw 24kHz WAV output to MP3 via `subprocess.run(["ffmpeg", "-y", "-i", wav, "-c:a", "libmp3lame", "-q:a", "2", mp3])` in ~0.02s for lightweight, universal WhatsApp and Web playback.
  - **Non-Blocking GPU Worker Threading (`asyncio.to_thread`)**: Never execute PyTorch CUDA inference directly on the main event loop thread inside an `async def` FastAPI route. Synchronous GPU tensor ops freeze the event loop, causing `/status` health probes and `/action` remote control calls (e.g. `lock`, `shutdown`) to stall for multiple seconds. Always offload model generation to worker threads: `await asyncio.to_thread(model.generate, ...)`.
- **Audio Dataset Preparation from Anime Compilation Clips ("Raw Clips / Omnibus")**:
  - When extracting character voice lines from YouTube/Bilibili "raw clips" or "omnibus" compilations via `yt-dlp`: Extract the cleanest audio stream (`yt-dlp -f 140 -x --audio-format wav <url>`).
  - Filter out silence, scene transition sound effects, and multi-character dialogue before generating zero-shot reference prompts or RVC index slices. A single clean 5-10s slice with distinct character breathiness and pitch contour yields better zero-shot cloning than a long concatenated clip with varying microphone distance or emotional extremes.
- **Text-First Explanation Before Executing Large Audio/Model Migrations**:
  - When the user requests a voice quality overhaul ("belum mirip dan masih kerasa robotnya", "Jawab teks dulu bisa gak"), always provide a blunt root cause diagnosis (explaining the difference between voice conversion vs speech synthesis, and why the current voice sounds robotic) and present concrete trade-offs (e.g. latency vs voice expressiveness, VRAM usage) before installing new heavy packages or altering pipelines.
- Use dedicated inference wrappers such as `infer_rvc_python` with preloaded model cache (`converter.generate_from_cache(...)`) to avoid per-request model reload overhead.
- When installing large PyTorch CUDA wheels (~2.3GB) on user machines, run downloads via background tasks (`notify=true`) or use isolated virtual environments (`uv venv`) to avoid tripping foreground timeout limits.
- **PyTorch CUDA Overwrite Trap**: Installing downstream audio packages (e.g. `uv pip install infer_rvc_python soundfile scipy librosa`) may resolve `torch` from standard PyPI and attempt to overwrite the pre-installed GPU build (`+cu121`) with CPU-only wheels. Always pass `--extra-index-url https://download.pytorch.org/whl/cu121` or `--no-deps` to preserve the GPU-accelerated PyTorch installation.
- **NumPy 2.x Binary Incompatibility Trap (PyWorld)**: Modern pip defaults install NumPy 2.x, but PyWorld and compiled Cython RVC extensions were built against NumPy 1.x headers. Launching inference crashes with `ValueError: numpy.dtype size changed, may indicate binary incompatibility`. Pin `numpy<2` (e.g. `numpy==1.26.4`) in the inference environment.
- **Setuptools > 80 `pkg_resources` Deprecation Trap**: Downstream audio packages (`librosa.util.files`) invoke `from pkg_resources import resource_filename`. Setuptools 80+ strips or moves `pkg_resources`, triggering `ModuleNotFoundError: No module named 'pkg_resources'`. Pin `setuptools<=80.6.0` during venv bootstrapping.

### Multi-Service Lifecycle in Batch Launchers
When an app pairs a FastAPI backend (port 8000), a Node.js WhatsApp bridge (port 8001), and a voice inference worker:
- **Clean both ports on startup**:
  ```bat
  for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000" ^| findstr "LISTENING"') do taskkill /F /PID %%a >nul 2>&1
  for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8001" ^| findstr "LISTENING"') do taskkill /F /PID %%a >nul 2>&1
  ```
- **Self-Healing Bridge Process**: Have the Python backend check `http://127.0.0.1:8001/status` on startup in a daemon thread; if unresponsive, spawn `node server.js` automatically via `subprocess.Popen(..., shell=True)` so users only need to launch a single `.bat` file.

---

## 8. 24/7 Hosting for Local Bot Gateways: Cloud, Android Termux, & Payment Traps

When the user wants the WhatsApp bot, voice notes, and task scheduler to run 24/7 without keeping their physical laptop powered on, migrate the stack to an always-on host.

### Payment Verification Traps & Rejection Realities
- **Hard Rule for Cardless Users**: If the user cannot provide an international credit card, STOP exploring foreign cloud container hosts immediately. Every major platform (Render, Zeabur, Koyeb, Hugging Face, Fly.io, Oracle) enforces card verification or redirects in 3DS loops. Never suggest successive "free" cloud hosts once cardlessness is confirmed.
- **Oracle Cloud Always Free Rejection**: Oracle Cloud Free Tier relies on automated fraud filters that systematically reject international and Southeast Asian debit cards (even with sufficient funds for the $1 pre-auth hold). Furthermore, Free Tier compute shape availability (`VM.Standard.A1.Flex`) is frequently depleted ("Out of host capacity"). Do not get stuck troubleshooting card rejections with Oracle.
- **Render / Koyeb Card Loops**: Render and Koyeb periodically trigger payment card verification forms depending on account origin. Standard bank debit cards often fail 3D-Secure or international recurring billing checks silently, refreshing back to the "Add Card" screen without clear error logs.
- **Zeabur & Hugging Face Traps**: Zeabur permits free signup but locks deployment behind paid provider selection. Hugging Face now blocks non-static space creation (Docker, Gradio) behind card verification; "Static" spaces only support browser HTML/JS and cannot run Python/Node.js backends or WebSockets.
- **Serv00 Capacity & Approval Delay**: Serv00 free accounts enforce manual human review taking 24-72 hours and frequently hit capacity caps (>169,900 / 170,000 slots).

### Proven Zero-Credit-Card 24/7 Alternatives

#### 1. Android Phone Server via Termux (100% Free & Cardless)
If the user has an Android phone (whether a spare phone or their primary daily phone on Wi-Fi and charger):
- **Avoid Google Play Store**: Google Play's Termux build is deprecated and breaks on `pkg update` (404 errors). Direct users to F-Droid (`https://f-droid.org/repo/com.termux_1022.apk`) or GitHub releases.
- **Termux libcurl & OpenSSL Dynamic Linking Trap**:
  Running `pkg install curl` or upgrading `libcurl` (e.g. 8.22.0+) on a Termux system with pending upgrades installs `libcurl.so` compiled against newer OpenSSL with QUIC support (`SSL_set_quic_tls_early_data_enabled`). If `openssl` is not upgraded in the same pass, `curl` fails with `CANNOT LINK EXECUTABLE "curl": cannot locate symbol "SSL_set_quic_tls_early_data_enabled" referenced by ".../libcurl.so"`.
  - **Fix**: Run `pkg install -y openssl && pkg upgrade -y`.
  - **Defensive Bootstrap Rule**: Never rely solely on `curl -sL <url> | bash` in mobile setup scripts. Since Python is already installed on Termux, provide a fallback downloader via standard library:
    ```bash
    curl -s -O "$URL" || python3 -c "import urllib.request; urllib.request.urlretrieve('$URL', '$OUTPUT')"
    ```
- **Termux Pip Upgrade Trap**: Never run `pip install --upgrade pip` inside Termux bootstrap scripts. Termux uses an OS-patched pip package; upgrading pip triggers `ERROR: Installing pip is forbidden, this will break the python-pip package (termux)` and aborts execution.
- **Termux Rust & Binutils Compiler Trap (`maturin` / `pydantic-core`)**: Modern Python packages with compiled Rust extensions (such as `pydantic-core`) fail to build on Termux's `aarch64-linux-android` Python because `rustup` target `aarch64-unknown-linux-android` is unsupported. Always include `pkg install rust binutils clang make build-essential -y` in the initial package install so native `rustc` and `aarch64-linux-android-ar` are available for `maturin` wheel building. Alternatively, bypass compilation completely by passing `--extra-index-url https://eutalix.github.io/android-pydantic-core/` to pull precompiled wheels.
- **Termux Process Cleanup on Launch**: Background tasks spawned with `&` persist across script invocations and terminal exits. Always kill existing instances before binding ports:
  ```bash
  pkill -f "node server.js" 2>/dev/null || true
  pkill -f "uvicorn main:app" 2>/dev/null || true
  sleep 1
  ```
- **Primary Phone Clarification**: Clarify that a second/spare phone is NOT required; Termux runs silently in the Android notification tray using ~120MB RAM without disturbing normal phone usage.
- **1-Command Piped Bootstrap Script**: Provide a single-line command (`curl -sL <url>/setup_termux.sh | bash`) that:
  1. Installs core packages: `pkg update -y && pkg install python nodejs ffmpeg git wget unzip clang make rust binutils build-essential -y`
  2. Downloads a minimal application zip archive (<2MB, excluding large caches/models).
  3. Installs Python (`pip install fastapi uvicorn ... --extra-index-url https://eutalix.github.io/android-pydantic-core/`) and npm dependencies.
  4. Generates a startup script with `termux-wake-lock` to prevent Android deep sleep:
     ```bash
     termux-wake-lock
     pkill -f "node server.js" 2>/dev/null || true
     pkill -f "uvicorn main:app" 2>/dev/null || true
     cd wa_bridge && node server.js &
     cd backend && python -m uvicorn main:app --host 0.0.0.0 --port 8000
     ```
- Expose via Tailscale Android app to keep the phone accessible from laptops and web clients anywhere.
- **Single-Device WhatsApp Pairing Code (No Camera Scan Needed)**:
  If Termux runs on the user's primary phone, scanning a terminal QR code with the same phone's camera is physically impossible. Use Baileys pairing code instead:
  - **Browser Signature & Timeout Settings**: Meta's anti-abuse filters frequently reject default user-agents during pairing code verification. Always configure:
    ```javascript
    const { default: makeWASocket, Browsers, useMultiFileAuthState, DisconnectReason } = require('@whiskeysockets/baileys');
    const sock = makeWASocket({
        auth: state,
        browser: Browsers.macOS('Safari'), // High-reputation signature
        syncFullHistory: false,
        markOnlineOnConnect: true,
        connectTimeoutMs: 60000,
        defaultQueryTimeoutMs: 0
    });
    ```
  - **Foreground Pairing Utility & 515 Handshake Trap (`pair.js` / `pair.sh`)**:
    Because production startup scripts (`start.sh`) launch the bridge as a background daemon (`node server.js &`), interactive pairing must run via a standalone foreground CLI script.
    **Critical 515 Handshake Trap**: Entering the 8-digit code (or scanning a QR code) triggers a transient socket closure with `statusCode: 515 (restartRequired)` for cryptographic key exchange. The script MUST catch non-logout disconnects and immediately call `setTimeout(start, 1500)` to complete the handshake; exiting on close causes WhatsApp on the phone to display "Gagal menautkan perangkat / Couldn't link device".
    ```javascript
    // pair.js
    const cleanPhone = phone.replace(/[^0-9]/g, '').replace(/^0/, '62');
    let requested = false;

    async function start() {
        const sock = makeWASocket({
            auth: state,
            browser: Browsers.macOS('Safari'),
            syncFullHistory: false,
            markOnlineOnConnect: true,
            connectTimeoutMs: 60000,
            defaultQueryTimeoutMs: 0
        });
        sock.ev.on('creds.update', saveCreds);

        sock.ev.on('connection.update', async ({ connection, lastDisconnect }) => {
            if (!state.creds.registered && !requested) {
                requested = true;
                setTimeout(async () => {
                    const code = await sock.requestPairingCode(cleanPhone);
                    const formatted = code.match(/.{1,4}/g)?.join('-') || code;
                    console.log(`\n======================================================`);
                    console.log(`🌸 KODE PAIRING WHATSAPP: \x1b[1;32m${formatted}\x1b[0m`);
                    console.log(`1. Buka WhatsApp > Perangkat Tertaut > Tautkan Perangkat`);
                    console.log(`2. Pilih 'Tautkan dengan nomor telepon saja'`);
                    console.log(`3. Masukkan kode: ${formatted}`);
                    console.log(`======================================================\n`);
                }, 3000);
            }
            if (connection === 'close') {
                const code = lastDisconnect?.error?.output?.statusCode;
                if (code === DisconnectReason.loggedOut) {
                    console.log('❌ Logged out.');
                    process.exit(1);
                } else {
                    // Reconnect automatically on 515 (restartRequired) to finalize handshake
                    console.log('[Handshake] Memproses pertukaran kunci...');
                    setTimeout(start, 1500);
                }
            } else if (connection === 'open') {
                console.log('✅ Berhasil terhubung! Sesi tersimpan.');
                setTimeout(() => process.exit(0), 1000);
            }
        });
    }
    start();
    ```
  - **WhatsApp Multi-Device Anti-Spam Rate Limit Cooldown ("Tidak dapat menautkan perangkat. Coba lagi nanti")**:
    When an active Baileys socket is already running on port 8001 or rapid successive pairing attempts fail, WhatsApp's edge servers activate an anti-spam rate limit on that phone number. Subsequent pairing attempts (either via pairing code or QR scan) are rejected with: *"Tidak dapat menautkan perangkat. Coba lagi nanti"*.
    *Rule*: Do NOT repeatedly spam pairing attempts. If rejected with "Coba lagi nanti", stop all competing Baileys instances, wait out the 5–15 minute WhatsApp cooldown window, and resume with a single cleanly isolated process.
  - **Termux Native API (`termux-notification`) vs Mobile Baileys Resource Drain**:
    Running Node.js + `@whiskeysockets/baileys` inside Android Termux consumes ~180–220MB of RAM and maintains an active persistent TLS WebSocket connection to WhatsApp. On budget or daily driver Android phones (e.g. Infinix, Xiaomi, Samsung), OEM battery managers (such as Infinix XOS Power Marathon) aggressively terminate background processes with high memory or network usage, killing the bot silently.
    *Better Architecture*: Use `termux-api` (`pkg install termux-api` + companion Android app `com.termux.api`).
    A lightweight Python background daemon (`termux_notifier.py`) polls or syncs reminders from the host laptop via Tailscale (`http://100.x.y.z:8000`) and fires native Android status-bar alerts via `termux-notification --title "..." --content "..." --sound --vibrate "500,200,500" --priority max`.
    Benefits:
    1. Consumes <15MB RAM (versus >200MB for Node.js Baileys).
    2. Zero risk of WhatsApp socket rate-limiting, status 440 kicks, or multi-device quota limits.
    3. Works offline using local SQLite synced tasks.
    4. Delivers native Android status-bar banners, ringtones, and vibration patterns directly to the user's pocket 24/7 without maintaining a secondary WhatsApp session.
  - **Android Foreground App Disruption (`termux-dialog` vs `termux-notification`)**:
    * `termux-dialog` (sheet, confirm, radio) is implemented as a native Android `Activity` (`DialogActivity`). Triggering it from a background script invokes `am start`, forcing Android WindowManager to bring `com.termux.api`'s task to the foreground and pull the user out of their current application (YouTube, gaming, browser) even if "Display over other apps" is granted.
    * **The `termux-dialog` Standalone Execution Trap**: `termux-dialog` is strictly a decoupled UI presenter that emits JSON to stdout (`{"code": 0, "text": "...", "index": N}`) and exits. It possesses zero automated linkages to backend APIs or databases. Running raw `termux-dialog` commands in the terminal will display the options, but user selections will be completely ignored unless a wrapper script captures stdout and dispatches the required HTTP PUT/POST or DB query.
    * **Termux Dialog Sheet Clickable Row Trap (Dummy Title Row)**: In `termux-dialog sheet -v "..."`, every row in the array is rendered as an actionable button. Passing title/metadata headers into `-v` creates an accidental dummy button that registers as a selection and aborts the dialog without action. Embed task titles and deadlines directly into real action buttons (e.g. `✅ Selesaikan: <task> (<due>)`, `⏳ Tunda (<duration>)`, `🔕 Matikan Pop-up`), ensuring 100% of rows perform actual work.
    * **Post-Dialog IPC Broadcast Transition Stall**: When `termux-dialog` dismisses, calling `termux-toast` synchronously right after `subprocess.run(termux-dialog)` sends an immediate IPC broadcast to `com.termux.api`. This wakes the dying package and stalls Android's window transition, stranding the user on the Termux:API screen instead of returning to the underlying app (WhatsApp, YouTube). Do not invoke synchronous `termux-toast` upon dialog dismissal; let the Python script exit immediately so Android WindowManager restores the previous foreground task.
    * **Termux:API Task Stack Retention in Recent Apps**: If the user opened the Termux:API app manually (viewing Preferences / About), `TermuxAPILauncherActivity` sits in the package task stack. When `DialogActivity` finishes, Android falls back to `TermuxAPILauncherActivity`. Swipe away/close `Termux:API` from Recent Apps (`☰`) so transient `noHistory="true"` dialog activities cleanly terminate the task stack and restore the previous foreground app.
    * `termux-notification` runs via `NotificationManager` / `SystemUI`. It drops down as a floating banner over the current app without switching tasks.
    * Interactive Action Buttons: Attach background handler commands using `--button1 "⏳ Tunda" --button1-action "python3 ... ctl.py snooze <id>"` and `--button2 "✅ Selesaikan" --button2-action "python3 ... ctl.py complete <id>"`. Tapping buttons executes the CLI action immediately and dismisses the alert without opening Termux.
    * **Adaptive Snooze Timeline vs Static Snooze Lockout**: Hardcoding static snooze timers (e.g. flat 1 hour) violates urgency constraints (e.g., delaying critical <1h tasks by 60 minutes) and blocks repeated testing if `snooze_until` is persisted in prefs. Dynamically calculate snooze durations from task urgency stages (CRITICAL: 10m, URGENT: 40m, TODAY: 2.5h, APPROACHING: 8h) and support a `--test` / `--force` flag to clear stale snooze locks during manual verification.
    * **Permanent 24/7 Dual-Mode Daemon Pattern (Auto-Scan & Offline Fallback)**:
      In hybrid laptop + mobile architectures, run an auto-scan loop (e.g. every 30 seconds) in the mobile background daemon (`notifier.py`):
      1. **When Host Laptop is Online**: Probe `http://100.x.y.z:8000/api/tasks`. On success, cache latest tasks to `~/mahiru_tasks_cache.json`. Host handles heavy tasks and WhatsApp bot, while the mobile daemon fires native on-screen pop-ups for newly added tasks or urgency transitions so reminders appear right on the user's phone.
      2. **When Host Laptop is Offline**: Switch seamlessly to local cache mode. The daemon continues evaluating deadline deltas against local time and firing adaptive pop-ups and backup alerts 24/7.
      3. **When Host Laptop Powers Back On**: Auto-reconnect on the next 30s tick, push completed task states to the host API (`PUT /api/tasks/<id> {"status":"completed"}`), and pull fresh tasks.
    * **Persistent Auto-Start via `~/.bashrc` + `termux-wake-lock`**:
      To ensure background daemons survive Termux restarts or phone reboots without complex root daemons:
      1. Append an idempotent check to `~/.bashrc`:
         `pgrep -f 'python.*notifier.py' >/dev/null || bash $HOME/mahiru/start.sh`
      2. In `start.sh`, acquire `termux-wake-lock`, prune stale PID instances with `pkill -f "python.*notifier.py"`, and start in background:
         `nohup python3 -u "$HOME/mahiru/notifier.py" > "$HOME/mahiru/notifier.log" 2>&1 &`
    * **Dynamic Due-Date Propagation to Modal Pop-up Handlers**:
      Never hardcode placeholder due dates (e.g. `"13:00"`) when calling `notifier_popup.py` from the daemon. Always pass the actual task due date/time string (`due_str` or ISO format) so the pop-up handler accurately displays deadline context and computes the exact adaptive snooze duration.
  - **Notification Channel Banner Suppression Trap (Infinix XOS / MIUI / ColorOS)**:
    On Android 8.0+ through 14, OEM battery managers frequently default sideloaded Termux:API channels to "Tanpa Spanduk / No Banner" (sound and tray only). Passing `--priority max` or `--importance high` is ignored unless the user opens:
    `Pengaturan > Manajemen Aplikasi > Daftar Aplikasi > Termux:API > Notifikasi > [Kategori Notifikasi] > Aktifkan "Spanduk / Tampilkan di Layar"`.
  - **Termux Dialog Sheet Title Omission**:
    In `termux-dialog sheet`, the `-t` title parameter is omitted in the native BottomSheet layout; only `-v` rows render. If a modal prompt must show the task title and description, use `termux-dialog confirm -t "<title>" -i "<message>"`.
  - **Bridge HTTP Endpoint for Web UI Pairing**:
    Expose `POST /pair` in `server.js` accepting `{"phone": "08xxx"}` so users accessing the web dashboard at `http://localhost:8000` can generate and copy their pairing code with one click.
  - **Account Role Distinction & Active Client Requirement**:
    When guiding users, clearly differentiate:
    - **Bot Number**: Dedicated secondary number. Messages arrive *from* the bot *to* the user's personal WhatsApp. **Trap**: The bot number MUST already be registered and active inside an official WhatsApp app (e.g. WhatsApp Business, Dual App, or App Cloner). Entering a bot pairing code into the personal WhatsApp client causes an infinite loading loop and "Gagal menautkan perangkat" because the client cannot match the incoming session with the current account.
    - **Personal Number**: Primary SIM. Assistant operates in WhatsApp's built-in self-chat ("Message Yourself").
  - **Protocol Throttling & Screen QR Fallback**:
    Meta's anti-abuse filters periodically withhold `pair-success` stanzas on unofficial pairing code handshakes, causing the client to hang until timeout. When a laptop or second screen is present, fall back to scanning a terminal or web UI QR code (`qr`), which avoids pairing code server throttling and links instantly.
- **Session Host Dependency Warning**:
  WhatsApp Web auth tokens (`auth_info_baileys`) are host-local. If tested via `POST http://127.0.0.1:8001/send` on the developer's laptop, the message arrives from the laptop bridge, not Termux. When the laptop lid closes or powers down, the laptop bot dies immediately. Always test by pinging the Termux port or stopping the laptop bridge process first to confirm Termux autonomy.

#### 2. Serv00.com (Cardless European Shell Hosting)
- Register at `serv00.com` with standard email (no payment card required).
- Enable background processes via devil panel: `devil binexec on`.
- Run Node.js WhatsApp bridge and lightweight Python backend via user crontab or nohup.

#### 3. Regional Domestic VPS via QRIS / E-Wallets
- If a standard public Linux VPS is required without international credit cards, recommend domestic Indonesian cloud providers (e.g. Biznet Gio NEO Lite, IDCloudHost) priced at ~Rp 20,000 - Rp 30,000/month that accept instant payment via QRIS, GoPay, DANA, or local virtual accounts.

### 1. Multi-Process Cloud Docker Container
Bundle both Python (FastAPI) and Node.js (Baileys) into a single container image:
```dockerfile
FROM python:3.10-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl gnupg ffmpeg procps git \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r ./backend/requirements.txt groq

COPY wa_bridge/package*.json ./wa_bridge/
RUN cd wa_bridge && npm install --omit=dev

COPY backend ./backend
COPY frontend ./frontend
COPY wa_bridge ./wa_bridge
COPY start.sh ./start.sh
RUN chmod +x ./start.sh

EXPOSE 7860
ENV PORT=7860 PYTHONUNBUFFERED=1
CMD ["./start.sh"]
```

### 2. Multi-Service Startup Script (`start.sh`)
```bash
#!/bin/bash
set -e
echo "[Cloud] Starting WhatsApp Web Bridge..."
cd /app/wa_bridge && node server.js &
sleep 2
echo "[Cloud] Starting FastAPI on port ${PORT:-7860}..."
cd /app/backend && exec python -m uvicorn main:app --host 0.0.0.0 --port ${PORT:-7860}
```

### 3. Cloud Brain (LLM) Integration with Groq API Fallback & Rate Limit Handling
Cloud containers and Termux instances do not have access to local desktop GPU LLMs (`http://127.0.0.1:20128`). Support seamless fallback to Groq API (using OpenAI-compatible endpoint with models like `qwen/qwen3.8-27b`, `openai/gpt-oss-120b`, or `llama-3.3-70b-versatile`) responding in <0.5s for free without credit cards:
```python
def get_antigravity_config():
    # Check SQLite settings table first so packaged DB carries configured key
    groq_api_key = get_db_setting("groq_api_key") or os.environ.get("GROQ_API_KEY", "")
    if groq_api_key:
        return {
            "api_key": groq_api_key,
            "base_url": "https://api.groq.com/openai/v1",
            "model": os.environ.get("GROQ_MODEL", "qwen/qwen3.8-27b")
        }
    # Fallback to local Hermes or Antigravity endpoint
    return {"api_key": os.environ.get("ANTIGRAVITY_API_KEY", ""), "base_url": "http://127.0.0.1:20128/v1", "model": "ferdi"}
```
- **Groq JSON Mode Requirement**: When using `response_format: {"type": "json_object"}`, Groq strictly demands that the word `"json"` appears in the system or user prompt. Omitting `"json"` triggers HTTP 400: `'messages' must contain the word 'json' in some form, to use 'response_format' of type 'json_object'`.
- **Rate Limit & Tier Fallback Trap (HTTP 429)**: Groq enforces 1,000 requests/day on `llama-3.3-70b-versatile` and 14,400 requests/day on `llama-3.1-8b-instant`. Catch HTTP 429 errors in the client request and automatically retry with `llama-3.1-8b-instant` or Google Gemini Flash, ensuring 24/7 companion availability even during heavy chat sessions.

### 4. Preventing Free Cloud Sleep (Keep-Alive Ping via UptimeRobot)
Free container hosts (Hugging Face Spaces, Render, Koyeb) automatically spin down or sleep after inactivity.
- Expose a lightweight ping endpoint:
  ```python
  @app.get("/api/ping")
  def ping():
      return {"status": "ok", "message": "Awake! 🌸", "timestamp": time.time()}
  ```
- Register the public URL (`https://<space-name>.hf.space/api/ping`) on a free ping service (e.g. UptimeRobot) with a 5-minute interval. This forces the container, WhatsApp WebSocket, and reminder background threads to stay active 24/7/365.

### 5. Remote Host PC Control via Local Polling / Tailscale Agent
Because cloud containers and standalone mobile servers (Termux) cannot directly invoke host Windows OS commands, deploy a lightweight client agent on the user's laptop (exposed via port 8002 or polling):
- **Windows LockWorkStation Native API**: Never invoke `rundll32.exe user32.dll,LockWorkStation` via `subprocess.Popen(..., shell=True)` from background agents (it can fail silently or be blocked by security policies). Call the native Win32 API:
  ```python
  import ctypes
  ctypes.windll.user32.LockWorkStation()
  ```
- **Shutdown & Cancel Commands**:
  - Shutdown: `subprocess.Popen(["shutdown", "/s", "/t", "10"], shell=True)`
  - Cancel shutdown: `subprocess.Popen(["shutdown", "/a"], shell=True)`
- **Windows 11 Modern Standby (S0) Sleep vs Hibernate/Shutdown**:
  - Never call `rundll32.exe powrprof.dll,SetSuspendState 0,1,0` on Windows 11 with Modern Standby (where ACPI S3 is disabled in firmware). It triggers full S4 Hibernate or cold Shutdown.
  - To trigger low-power standby with instant resume:
    ```python
    import ctypes
    # Lock desktop first
    ctypes.windll.user32.LockWorkStation()
    # Send WM_SYSCOMMAND (0x0112) SC_MONITORPOWER (0xF170) with lParam 2 (power off display)
    ctypes.windll.user32.SendMessageW(0xFFFF, 0x0112, 0xF170, 2)
    ```
- **Windows 11 Lock Screen Credential Provider Navigation Trap (VBScript SendKeys Recipe)**:
  - Windows 11 lock screen defaults to Windows Hello PIN or Biometrics. Direct simulated keystrokes into the initial text input box fail if typing an alphanumeric password.
  - To navigate the credential provider and switch from PIN to Password via VBScript SendKeys:
    ```vbscript
    Set WshShell = CreateObject("WScript.Shell")
    ' 1. Wake screen & dismiss lock wallpaper
    WshShell.SendKeys " "
    WScript.Sleep 1200
    WshShell.SendKeys " "
    WScript.Sleep 1000

    ' 2. Navigate to Sign-in options (Use Space, NEVER Enter)
    WshShell.SendKeys "{TAB}"
    WScript.Sleep 300
    WshShell.SendKeys "{TAB}"
    WScript.Sleep 300
    WshShell.SendKeys " "
    WScript.Sleep 800

    ' 3. Select Password icon and enforce 1500ms LogonUI transition delay
    WshShell.SendKeys "{TAB}"
    WScript.Sleep 300
    WshShell.SendKeys " "
    WScript.Sleep 1500

    ' 4. Type password character-by-character with 50-60ms pause per keystroke
    pwd = "YourPasswordHere"
    For i = 1 To Len(pwd)
        WshShell.SendKeys Mid(pwd, i, 1)
        WScript.Sleep 60
    Next
    WScript.Sleep 500
    WshShell.SendKeys "~"
    ```
  - **Key Mechanics**:
    - **Space vs Enter on Sign-in Options**: Sending Enter (`~`) on the options tile button triggers the default form submission in Windows 11 UWP LogonUI, submitting an empty form and throwing an "Incorrect PIN" error before the password box mounts. `Space` activates the button cleanly without submitting.
    - **1500ms Transition Sleep**: Windows 11 LogonUI instantiates the password credential tile and focuses the password input box via asynchronous XAML animations. Keystrokes sent before 1500ms are dropped during transition.
    - **Per-Character Loop**: Typing with a 60ms delay per character avoids buffer overrun in masked credential fields.
- **Bilingual Subtitle Split Architecture (Japanese Voice Note + Localized Text Subtitle)**:
  - When training few-shot TTS models (GPT-SoVITS v2) on anime seiyuu dialogue (Japanese audio), feeding non-Japanese text forces the phonemizer into katakana approximation, resulting in stiff pronunciation and loss of character emotion.
  - **Two-Layer Schema**:
    In the LLM system prompt, require returning:
    ```json
    {
      "action": "none",
      "reply": "Balasan lengkap dan manis dalam Bahasa Indonesia (berfungsi sebagai teks chat dan subtitle)",
      "japanese_voice": "100% natural conversational anime Japanese (Kanji/Kana) reflecting the emotion"
    }
    ```
  - **Execution**: The user receives `reply` immediately in WhatsApp as a readable subtitle. The background worker synthesizes `japanese_voice` on the GPU (taking <3s on RTX 3050 Laptop) and delivers it as a native voice note (`ptt: true`). For deterministic fast-path commands (lock, unlock, sleep, youtube, task creation), pre-map `japanese_voice` to bypass LLM latency completely.
- **Decoupling 24/7 Reminders from Host Execution**:
  - In a hybrid host-and-mobile setup, reminder notifications must not be coupled solely to the laptop backend if the user turns off the laptop.
  - Use a cloud gateway with scheduled queues (e.g. Fonnte API scheduled messages) or native Android OS `AlarmManager` within the APK to ensure reminders ring at the exact time even when the laptop is completely powered off and Termux is not running.
- **Few-Shot GPT-SoVITS v2 vs Zero-Shot Diffusion & Windows HF Quirks**:
  - Fine-tuning GPT-SoVITS v2 (acoustic model `s2` for 8 epochs, semantic model `s1` for 15 epochs) on 1-3 minutes of clean seiyuu audio yields authentic emotional cadence, natural breath pauses, and expressive pitch contours.
  - **Bilingual Nuance**: Synthesizing non-native languages (Indonesian) using weights fine-tuned on Japanese seiyuu clips will produce a distinct Japanese/katakana accent ("nihonjin speaking Indonesian"). Set realistic user expectations: it sounds like an authentic anime character speaking Indonesian, not a native local speaker.
  - **Windows HF Cache Path Limit**: Hugging Face Hub downloads often fail on Windows due to 260-character path limits with `.cache/huggingface/download/...incomplete`. Stream downloads directly to target directories or convert model weights to `.safetensors`.
  - **Fallback for C-Extensions (`jieba_fast`)**: In Chinese/Japanese text processing pipelines where compiled C extensions like `jieba_fast` fail to import on Windows, wrap imports with a transparent fallback to pure-Python `jieba`.
- **`shell:startup` Activation & `pythonw.exe` Silent Crash Traps**:
  - Placing shortcuts or `.vbs` scripts into `shell:startup` only launches the agent upon the next Windows logon. During initial setup, always launch the agent immediately in the active session and verify port readiness (`curl http://localhost:8002/status`).
  - **`sys.stdout is None` Crash**: Under `pythonw.exe` (windowless GUI executable), `sys.stdout` and `sys.stderr` are `None`. Any `print()` or server logger crashes with `AttributeError: 'NoneType' object has no attribute 'write'`. Always redirect `sys.stdout` and `sys.stderr` to a local log file if they are `None` at the top of the entry file.
  - **VBS CurrentDirectory**: In `.vbs` startup wrappers, set `WshShell.CurrentDirectory` before calling `WshShell.Run` to prevent the agent from executing in `C:\Windows\System32`.
- **LLM Pre-Generated Affirmation vs Execution Status**: Never return pre-generated conversational affirmations (*"Iya sayang, langsung Mahiru kunci ya! 💕"*) without verifying that the remote command was successfully received by the laptop agent. If `executed is False` (host offline or connection timeout), append or override the reply with the honest error message (*"Laptop lagi offline / gagal dikirim"*).
