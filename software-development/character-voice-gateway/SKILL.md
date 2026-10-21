---
name: character-voice-gateway
description: Use when integrating anime voice models or WhatsApp PTT.
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [voice, tts, rvc, gpt-sovits, anime, companion, whatsapp, ptt, audio]
    related_skills: [cross-device-local-app, companion-ui-design]
---

# Character Voice Gateway (Anime & Companion TTS)

Workflow for integrating fine-tuned character voice synthesis models (GPT-SoVITS, RVC, OmniVoice) into personal assistant backends, duplex real-time voice calls, and multi-modal messaging gateways (WhatsApp PTT).

**Execution posture:** when the user gives a full-access go-ahead, chain every step without per-step confirmation and report once with verified evidence; stopping to ask 'mau lanjut?' after each step stalls GPU pipelines and wastes loaded VRAM.

### 1. Character Phoneme Alignment & Language Separation

### Root Mechanism
Voice cloning and speech synthesis models fine-tuned on native speech datasets (e.g. Japanese anime voice actors) fail when given foreign languages (Indonesian, English). The engine either synthesizes distorted, robotic phonemes or silently falls back to generic TTS voices.

### Dual-Channel Output Architecture
Decouple the visual reading experience from the acoustic listening experience:
1. **Visual Subtitles (`reply`)**:
   - Output in the user's primary conversational language (e.g. Indonesian).
   - Displayed as screen subtitles in voice call modals and sent as the text chat bubble in messaging apps.
   - **Prevent Dry-Text Syndrome**: Do NOT over-constrain visual subtitles to 1 sentence or <12 words. Generating 2–4 warm, expressive, flowing sentences in cloud LLMs takes <1s and has zero impact on GPU TTS latency.
2. **Acoustic Audio (`japanese_voice`)**:
   - Generated as native anime Japanese phrasing reflecting the character's authentic personality, using canonical honorifics (e.g. `[Name]-kun` / `〜君`) as the default rather than generic pet names (`ダーリン`). Intimate pet names (`sayang`) should be reserved as occasional emotional accents.
   - Fed directly into the fine-tuned voice synthesis engine.
3. **Single-Breath Joint Generation (Voice Call & Messaging Parity)**:
   - Generate BOTH visual text (`reply`, 2–3 flowing sentences) and spoken Japanese (`japanese_voice`, 2–3 matching sentences) simultaneously in ONE single LLM prompt turn.
   - Decoupled two-step waterfall (generating visual text first, then translating in a separate LLM call) introduces 15–25s latency, causes prompt mutilation, or triggers the short-stub bypass trap. Joint single-breath generation cuts end-to-end turnaround to ~5–6s (LLM ~1.5s + GPU TTS ~4s) with 100% semantic and duration parity.
4. **Golden Length Sweet Spot for Voice Notes (~45–70 Kana/Kanji, 6–9.5s)**:
   - **The Diffusion Marathon Cadence Trap**: Forcing zero-shot acoustic flow matching / diffusion models (OmniVoice) to generate marathon audio (>15s / >100 characters in a single shot) causes severe acoustic cadence degradation: prosody flattens, breath pauses turn into rushed robotic pacing, latency explodes (>8s), and the character sounds like an exhausted news anchor.
   - **Avoid Both Extremes**: Avoid hollow micro-clips (<20 characters / <3s) AND marathon monologues (>75 characters / >12s). The golden sweet spot for authentic companion anime voice notes is **45–70 characters (6–9.5 seconds)**.
   - **Technical Segregation Mandate**: Spoken audio must express the **emotional core, conversational reaction, and affectionate confirmation** (e.g. confirming files/messages are ready, playfully teasing, warm greeting). NEVER dictate step-by-step technical procedures (such as "tekan tombol Ctrl+V", full file paths, or CLI commands) aloud in Japanese; technical specifics belong strictly in visual chat subtitles (`reply`), while spoken character audio delivers the human/waifu warmth.
   - **Terminal Sentence Boundary Trimming**: In text length capping, never slice at a clause comma (`、`) mid-thought. Only trim at terminal sentence boundaries (`。`, `！`, `!`, `\n`) or append polite declarative closers (`〜ですよ。`) to keep clauses grammatically complete and natural.
   - **Trailing Syllable & Vowel Fadeout Tuning**: Keep the final cosine fade-out to 10–12ms strictly for anti-click smoothing. A heavy 50ms fade-out cuts off trailing unvoiced syllables, vowels, and rising question particles (`ねえ`, `の？`, `よ`), creating a swallowed grunt or abrupt cutoff.

### Duplex Voice Call State Machine & Action Intent Parity
1. **Strict Microphone & VAD Lock During Turn Processing**:
   - While the companion is thinking (`isProcessing`) or speaking (`isSpeaking`), the microphone audio track MUST be disabled (`track.enabled = false`) and VAD evaluation halted.
   - Failure to lock causes ambient room breathing or acoustic speaker echo to immediately re-trigger speech chunks, looping the state machine before the current reply finishes.
2. **Noise & Micro-Utterance Filtering**:
   - Require minimum audio size (>1200 bytes or >0.6s speech) before sending to STT. Micro-clicks and breathing puffs result in empty transcripts.
3. **Graceful Subtitle Recovery on Empty / Low-Confidence Speech**:
   - If STT returns empty or `status: false`, the frontend must immediately update subtitle text with a polite conversational prompt ("Suara Ferdinand-kun belum terdengar jelas... Boleh diulang? 💕") and reset visual state, NEVER leaving the subtitle card frozen on "sedang memikirkan jawaban".
4. **Dynamic Action Dialogue over Static Stubs**:
   - When special handlers (YouTube playback, music control, task completion) generate Japanese dialogue, dynamically format the target song title, artist, or task parameter into Katakana Wasei-Eigo. Never use static 30-character stubs (`今すぐYouTubeで再生するよ...`) that ignore user parameters, and never leave Latin titles unmapped as neural TTS skips or garbles raw Latin words.
5. **Whisper STT Model Floor (Base over Tiny)**:
   - Never use `faster-whisper-tiny` with greedy decoding (`beam_size=1`) for non-English speech or mobile mic input. Tiny models with 39M parameters routinely hallucinate random phonetic gibberish on short utterances (`tes tes` $\to$ `astus`, character names $\to$ random nouns). Use `faster-whisper-base` (runs <1.0s on CPU int8) with `beam_size >= 3` as the absolute minimum quality floor.
6. **Clause Comma Slicing Trap (Terminal Punctuation Only)**:
   - In message length capping, never slice at a clause comma (`、`) when trimming text to character budgets. Slicing at commas discards the remainder of the sentence mid-thought, truncating audio into 5-second fragments. Only slice at terminal sentence boundaries (`。`, `！`, `!`, `\n`) or split into sequential TTS utterances.
7. **End-to-End Latency Waterfall in Voice Calls**:
   - Synchronous chains of STT $\to$ Cloud LLM $\to$ Diffusion TTS $\to$ RVC $\to$ FFmpeg cumulative latency can exceed 35–40s, leaving duplex calls frozen in "thinking" state. Decouple subtitle delivery from voice generation: push the text subtitle immediately when LLM completes, and optimize TTS diffusion steps (`num_step=8`) or stream audio chunks to keep audio turnaround under 3–5s.
8. **Singleton DirectShow Capture for Live Audio Streaming**:
   - Multiple processes or WebSocket reconnections opening `ffmpeg -f dshow` on the same laptop mic hardware drop audio packets, induce silence dropouts, and create 20ms comb-filtering echo loops. Use a centralized singleton audio broadcaster to capture mic input once and distribute PCM chunks to all WebSocket clients.

### Seiyuu Prompt Engineering & Upstream Tone Conditioning
To ensure speech sounds like an authentic anime voice actress rather than a machine translation:
1. **Upstream Wasei-Eigo Directive in LLM Prompts**:
   Instruct the LLM in the system prompt to output ALL English loanwords, song titles, app names, and status tokens directly in Katakana Wasei-Eigo (*Good morning* $\to$ *グッドモーニング*, *YouTube* $\to$ *ユーチューブ*, *Playlist* $\to$ *プレイリスト*, *Task* $\to$ *タスク*, *Download* $\to$ *ダウンロード*, *Fighting* $\to$ *ファイト*). This prevents downstream tokenization hiccups at the root.
2. **Particle Cadence & Breath Insertion**:
   Enforce natural particle closers (`〜ですよ`, `〜ですね`, `〜てくださいね`, `〜ですから`, `もう…〜なんですから`) and insert Japanese commas (`、`) between clauses to generate natural breathing pauses and prevent speed runaway.
3. **Punctuation Pitch-Smoothing (Anti-Screech Rule)**:
   Explicitly instruct the LLM to avoid exclamation marks (`!`/`！`) and steep question marks (`?`/`？`), replacing them with soft declarative periods (`。`) and commas (`、`). Steep rising pitch inflections trigger octave doubling in pitch tracking algorithms (RMVPE).

### Wasei-Eigo & English-to-Katakana Phonetic Engine (Anti-Stutter & Accent Unification)
When technical terms, software names, and English expressions appear in spoken dialogue (e.g. `Good morning`, `YouTube`, `Playlist`, `Tab`, `Status`, `Download`, `Task`, `Fighting`), raw English alphabet tokens corrupt Japanese neural TTS phoneme tokenizers, causing token stuttering, pitch clamping, or bizarre phonetic butchering.
- **Rule**: Map all Latin/English loanwords to authentic Japanese seiyuu Katakana pronunciations (*Wasei-eigo*) before neural TTS tokenization:
  ```python
  (r"\bgood\s*morning\b", "グッドモーニング"),
  (r"\bthank\s*you\b", "サンキュー"),
  (r"\bplaylist\b", "プレイリスト"),
  (r"\byoutube\b", "ユーチューブ"),
  (r"\btabs?\b", "タブ"),
  (r"\bstatus\b", "ステータス"),
  (r"\bdownload\b", "ダウンロード"),
  (r"\bfight(?:ing)?\b", "ファイト")
  ```
- This guarantees seamless, natural phonetic flow without western accent dissonance or robotic pronunciation glitches.

---

## 2. Model Hierarchy, VRAM Budgeting & Pitch Tuning (RTX 3050 6GB Laptop GPU)

### Base Prosody vs Timbre Conversion (OmniVoice vs Edge-TTS + RVC)
- **The Edge-TTS Articulation Trap**: Running RVC on top of generic neural TTS (e.g. `ja-JP-NanamiNeural`) alters pitch and timbre, but preserves the stiff, robotic syllabic pacing and unnatural mechanical pauses of Microsoft Edge-TTS, making the voice sound overtly synthetic and artificial.
- **Fast Diffusion Step Optimization (OmniVoice num_step=8)**: A zero-shot model (e.g. `k2-fsa/OmniVoice`) conditioned on an authentic character audio prompt reproduces natural breathing, emotional prosody, and authentic anime voice actress timbre. While default diffusion steps (`num_step=16`) take ~8.3s on consumer GPUs (RTX 3050), tuning to `num_step=8` cuts synthesis time to **~1.6–1.8s** at the cost of audibly flatter prosody — acceptable for snappy replies, but use `num_step=12–16` whenever quality matters more than latency.
- **VRAM Contention on 6GB Laptop GPUs**: Loading large zero-shot weights (800+ layers) alongside RVC pitch estimators (RMVPE) concurrently can still pressure laptop VRAM alongside Epic/other GPU apps. Query `nvidia-smi --query-gpu=name,memory.total --format=csv` for the exact card and never hardcode VRAM from memory. Run OmniVoice as Priority #1 and fall back to Edge-TTS + RVC only if the zero-shot model fails or runs on CPU.

### Multi-Emotion Dynamic Prosody Pipeline (OmniVoice + High-Step RVC)
- **The Static Single-Prompt Flatness Trap**: Conditioning zero-shot synthesis on a single audio clip locks the character into one flat emotional tone across every turn. When the character is scolded, pouts, or cries, the voice still sounds placid and emotionless.
- **Pre-computed Emotion Prompt Bank**:
  Extract 3–6s clean audio clips from authentic character anime media covering key emotional archetypes:
  - `gentle`: warm, soft, calming angel tone.
  - `baka`: tsundere, indignant pout, sharp pitch attack.
  - `crying`: vulnerable, trembling breath, sobbing inflection.
  - `cheerful`: bright, smiling, energetic upward cadence.
- **Unified Single-Profile Mode (user-requested)**: When the user explicitly asks for one smart profile instead of per-emotion prompts, lock ONE conditioning prompt (gentle) plus ONE RVC config (pitch_lvl=0, fixed index influence) and NEVER switch prompts, pitch, or tempo per emotion. Express variant moods only through wording, particles, and punctuation pauses (、, ……); prompt-switching in this mode causes timbre jumps that read as robotic or a different speaker.
- **Pristine Vocal Stem Isolation via HDemucs (Zero-BGM Mandate)**:
  Extracting reference clips directly from raw anime episodes/YouTube leaks background music (BGM), strings, piano, and room reverberation. When conditioned on audio with BGM, the diffusion model / acoustic encoder treats the musical frequencies as part of the vocal tract, causing extreme phase cancellation, metallic harmonic buzz, and garbled voice glitches.
  *Rule*: ALWAYS isolate pure dry vocals using neural source separation (e.g. `torchaudio.pipelines.HDEMUCS_HIGH_MUSDB_PLUS` on GPU) before generating voice clone prompts. See `references/youtube-reference-harvest.md` for the end-to-end harvest pipeline (yt-dlp audio pull, VAD segment scan, ASR transcript pick, vocal isolation, prompt-bank rebuild, metric gates).
  ```python
  from torchaudio.pipelines import HDEMUCS_HIGH_MUSDB_PLUS
  model = HDEMUCS_HIGH_MUSDB_PLUS.get_model().to("cuda")
  sources = model(waveform) # index 3 is vocals (0% BGM, 0% sound effects)
  ```
- **Zero-Latency Tensor Serialization (`.pt`) & Exact Verbatim Transcription Mandate**:
  Extracting conditioning features from raw `.wav` on every request adds 1.2–1.8s of redundant GPU work. Pre-compute `voice_clone_prompt` offline once and save as `.pt` tensors:
  ```python
  prompt = omnivoice.create_voice_clone_prompt(ref_wav, ref_text=exact_whisper_transcript, preprocess_prompt=False)
  torch.save(prompt, f"prompt_{emotion}.pt")
  ```
  *CRITICAL PITFALL*: `ref_text` MUST be the character-perfect verbatim transcript of `ref_audio` (transcribed via Whisper and verified by ear). NEVER provide an invented script or generic greeting (e.g. `"ふふっ、フェルディナンド君、今日も一日お疲れ様でした！"`) when the audio clip speaks something else (`"子供みたいじゃないですか..."`). Cross-attention token misalignment causes three fatal anomalies:
  1. *Phantom Syllable Injection*: Words from `ref_text` (like `お疲れ様でした` or character names) are hallucinated and prepended/doubled at the start of EVERY generation.
  2. *Mid-Sentence Speed Runaway ("Ngerap")*: The duration predictor desynchronizes against mismatched token offsets, causing clauses in the middle to accelerate to 3x speed.
  3. *Early Sentence Truncation*: Frame budget calculation runs out before the sentence finishes, cutting off the audio abruptly mid-word.
  Loading serialized prompt tensors into VRAM on daemon startup takes `<15ms` and eliminates runtime prompt encoding entirely.
- **Dual-Stage Synthesis (Emotion Prosody + Exact Timbre Enhancement)**:
  1. *Stage 1 (Expressive Prosody)*: OmniVoice generates the dynamic emotional inflection using the cached emotion prompt in ~1.0s.
  2. *Stage 2 (Exact Character Timbre via RVC)*: Pass the generated wave through a high-step RVC checkpoint (e.g. 5200 to 21000+ steps with Master FAISS index).
  3. *Eliminate Double Pitch Shifting*: In dual-stage synthesis, set RVC `pitch_lvl = 0`. Because OmniVoice's conditioning prompt already maps the emotional F0 contour, adding downstream RVC pitch shifts causes pitch-aliasing, screeching, and harmonic distortion.

### RVC Index Retrieval Calibration & High-Pitch Stability
- **The High-Index Octave Jumping Trap (`index_influence = 0.70–0.75`)**:
  On high-pitch expressions and excited lines ($F_0 > 350\text{ Hz}$), high index influence forces nearest-neighbor replacement with training features that can suffer from harmonic mismatch, causing sudden octave doubling/jumping ($600–700\text{ Hz}$) and metallic screeching.
- **Golden Calibrated Inference Parameters**:
  ```python
  rvc.apply_conf(
      tag="character_master",
      file_model=MODEL_PATH,
      pitch_algo="rmvpe+",
      pitch_lvl=0,                      # 0 = Natural F0 tracking without chipmunk artifacts
      file_index=MASTER_INDEX_PATH,
      index_influence=0.40,             # 0.40 = Sweet spot: 100% character timbre + zero pitch jumping
      respiration_median_filtering=0,
      envelope_ratio=0.25,
      consonant_breath_protection=0.33  # Protects unvoiced consonants & natural breath from RMVPE distortion
  )
  ```

### Master FAISS Index Training (Multi-Episode & 1440p Dataset)
When building a custom retrieval index:
1. Extract 768-dim Layer 12 ContentVec/HuBERT features from all clean vocal clips across the entire anime dataset and 1440p studio raw clips.
2. Pool all frames into a float32 matrix (~150,000+ vector frames).
3. Train an `IndexIVFFlat` index with `faiss.IndexFlatL2(768)` quantizer (`nlist=256`, metric $L2$).
4. Save the resulting master `.index` (~450–500MB) for ultra-fast, distortion-free feature retrieval.

### Broadcast Studio Mastering & Frequency Shaping
- **The Lowpass Muffle Trap (`lowpass = 9500Hz`)**:
  Cutting frequencies at 9.5 kHz destroys the breath sparkle, air presence, and upper harmonic sheen of anime voice acting.
- **Broadcast Filter Chain**:
  ```bash
  ffmpeg -y -i input.wav -af "highpass=f=45, lowpass=f=18000, volume=1.05" -c:a libmp3lame -b:a 192k -q:a 1 output.mp3
  ```
  This removes low-end sub-bass rumble (<45 Hz) while retaining high-frequency clarity up to 18 kHz.

### Autoregressive Onset Trimming & Japanese Phonetic Sanitization
- **OmniVoice Onset Murmur / "Yoo..." Blip Removal**:
  Autoregressive diffusion models (like OmniVoice) consistently synthesize an onset energy blip (100–300ms) followed by an energy valley (<0.006 RMS) before true speech begins. If fed directly to RVC, RVC amplifies this blip into an audible "yoo..." murmur or sharp gasp.
  *Rule*: Scan the first 3.0s of raw OmniVoice audio in 50ms windows, locate the energy valley (`RMS < 0.006`) following the blip, trim the audio directly at the speech onset (`RMS > 0.015`), and apply a smooth 20ms cosine fade-in and 50ms fade-out.
- **Latin-to-Katakana Phonetic Sanitization (Anti-Glitch Mandate)**:
  Japanese neural TTS tokenizers lack pronunciation maps for Latin titles, tech terms, and English loanwords (e.g. `YouTube`, `Memories`, `One Piece`, `Playlist`, `Laptop`), causing severe token stuttering, pitch clamping, or robotic glitching.
  *Rule*: Pass spoken text through a comprehensive Latin-to-Katakana replacement dictionary before synthesis (e.g., `Memories` $\to$ `メモリーズ`, `One Piece` $\to$ `ワンピース`, `YouTube` $\to$ `ユーチューブ`, `Laptop` $\to$ `ノートパソコン`), unescape HTML entities (`&amp;` $\to$ `&`), strip 4-byte unicode emojis/Markdown, and remove trailing glottal stops (`……っ` $\to$ `……`) that cause pitch jumps.

### Neural Vocoder Phase Mismatch Hazard (Never Artificially Divide or Clamp F0 in DSP)
- **The Phase & Harmonic Mismatch Trap**:
  Attempting to fix pitch spikes by artificially halving or clamping the F0 array (`f0[mask] /= 2` or `np.clip`) inside RVC's `root_pipe.py` breaks the phase relationship between the latent phonetic representations (HuBERT / ContentVec) and the fundamental frequency in the neural vocoder (HiFi-GAN). This causes catastrophic phase cancellation, raspy robotic buzzing, gravelly voice distortion, and ruined audio on both speech and alarms.
- **Acoustic Pitch Smoothing at the Linguistic/Text Root**:
  To eliminate interrogative screeching, resolve it at the input text and conditioning prompt stage:
  1. Replace steep rising pitch punctuation (`？`) with polite declarative periods (`。`) or commas (`、`).
  2. Expand clipped rising interrogatives (`どうしたの？`, `何があったの？`) into calm polite phrasing (`どうしたのですか、何があったのですか。`).
  3. Strip sudden glottal stops or gasps at the start of sentences (`^[えアあ][っッ][、,]\s*`).
  4. Select a gentle, calm conditioning prompt (`prompt_gentle.pt`). The diffusion acoustic model will generate a natural, calm F0 trajectory that stays in the 250–330 Hz range without any vocoder phase corruption.

### Dynamic Japanese Dialogue Synchronization vs Conditioning Prompts
- **The Conditioning Prompt Boundary**:
  Voice clone prompts (`prompt_*.pt`) govern ONLY acoustic timbre, pitch envelope, and emotional delivery style (gentle, cheerful, baka, crying) — NEVER the spoken words!
- **The Static Template Voice Trap**:
  Emotion routing functions (`detect_advanced_mahiru_emotion`) must ONLY classify and return the emotion enum to pick the prompt. Never allow emotion classifiers to return hardcoded Japanese template phrases or overwrite the dynamic conversational dialogue generated by the LLM.
- **Dynamic Dialogue Translation & Fallback (`ensure_character_japanese_voice`)**:
  Spoken character audio must ALWAYS be a direct translation/adaptation of what the character is actually communicating in the visual reply. If the LLM generates a visual reply without spoken Japanese, dynamically translate the reply into 1–2 clauses of authentic character anime speech with proper honorifics (`[Name]-kun`), rather than playing a repetitive static fallback sentence.

### Japanese Text Sanitization & Pacing Rules
- **The Pseudo-Word Robot Drone Trap**:
  Japanese anime scripts often use written onomatopoeia for crying or gasping (e.g. `うぅ……`, `ううう`). Neural TTS models lack valid phonemic representations for sobbing from text; they pronounce `うぅ` literally as a flat, monotone, robotic drone vowel.
  *Rule*: Sanitize script text before synthesis (`text.replace("うぅ", "……っ")`). Evoke vulnerability, sobbing, or breathless catches through ellipsis pauses (`……`), glottal stops (`っ`), and authentic conversational particles (`もう……`, `ひどいです……`), letting the clean reference prompt govern emotional inflection.
- **The Runaway Japanese Rap-Speed Trap**:
  Japanese neural TTS engines synthesize compound kanji/kana clauses without punctuation at 8–10 mora/second, sounding like breathless rapping.
  *Rule*: Enforce punctuation pauses by inserting commas (`、`) after grammatical particles (`は`, `が`, `を`, `に`, `で`, `から`, `ので`) whenever a clause exceeds 15 mora, maintaining the natural conversational golden ratio (**~5.5 to 6.5 mora/second**).

---

## 3. Multimodal & Psychological Emotion Intelligence Engine

A truly human-like anime companion dynamically perceives the user's emotional state through acoustic analysis, circadian rhythm, and semantic psychology:

### 1. Acoustic Prosody Perception (User Voice Notes / Audio Input)
When processing user WhatsApp voice notes or duplex voice streams:
- Extract acoustic prosody using lightweight stdlib `wave` + `struct` (<5ms):
  * **RMS Energy**: Low RMS (<0.04) indicates whispering, exhaustion, or late-night fatigue.
  * **Zero-Crossing Rate (ZCR)**: Low ZCR (<0.05) indicates deep/low pitch; high ZCR indicates excitement or agitation.
  * **Silence Ratio**: High pause ratio (>0.40) indicates hesitation, lethargy, or vulnerability.
- *Acoustic Routing*: If energy is low and pitch is low, immediately route to `gentle` whisper care ("Suara kamu terdengar lelah sekali... jangan dipaksakan ya, istirahatlah..."), overriding generic upbeat defaults.

### 2. Circadian Rhythm & Time Awareness
- **Late-Night Guardian (23:00 – 05:00)**: If the user messages late at night, automatically activate `baka` (tsundere health guardian):
  * Japanese Voice: `「もう……フェルディナンド君のバカ！ 夜更かしばかりしてないで、早く寝てください！」`
  * Intonation: Exasperated, caring pout demanding the user go to sleep.

### 3. Deep Semantic Psychological Layers & Role Alignment
- **User Sadness & Burnout vs Character Crying (The Role Dissonance Trap)**:
  * When the user expresses sadness, distress, or exhaustion (`aku sedih`, `down`, `terpuruk`, `kecewa`, `sendirian`, `capek`), the companion's persona is the **Protective Angel / Caretaker**.
  * Route to **`gentle`** mode (`「フェルディナンド君、どうしたのですか、何があったのですか。話せるようになるまでずっと側にいるから、一人で抱え込まないでね。」`).
  * Never route user sadness to the character's `crying` mode. Forcing comforting words through a weeping reference prompt (`prompt_crying.pt`) produces acoustic trembling, tremolo instability, and erratic cadence.
- **Character Fragility & Tearful Emotion**:
  * Reserve **`crying`** mode strictly for when the character *herself* is vulnerable, touched, or weeping (e.g. apologies `maaf`, fear of abandonment `jangan tinggalin`, or emotional vulnerability `泣いちゃいます……ひどいです`).
- **Teasing & Playful Banter** (`baka`, `bawel`, `jelek`, `ngambek`, `iseng`, `godain`) -> Mode `baka` (Blushing tsundere indignation).
- **Task Success & Celebration** (`selesai`, `beres`, `kelar`, `sukses`, `hore`) -> Mode `cheerful` (Joyful giggles and praise).

### Language-Specific Pitch Shifting & Emotion-Aware Fallback
- **Native Japanese Base TTS (`ja-JP-NanamiNeural`)**: Set base pitch `+8Hz`, RVC `pitch_lvl = 0` (preserves authentic character voice actress timbre).
- **Localized / Indonesian Base TTS (`id-ID-GadisNeural`)**: Set base pitch `+16Hz`, RVC `pitch_lvl = +1` (shifts adult female vocal tract upwards into youthful/cute anime cadence).
- **Emotion-Aware Fallback Tuning**: When falling back to Edge-TTS + RVC, modulate base pitch and rate dynamically by emotional context rather than using static constants:
  - `baka`: pitch `+26Hz` (JP) / `+28Hz` (ID), rate `+6%` to `+8%`, RVC `pitch_lvl = 1`.
  - `crying`: pitch `-4Hz` (JP) / `-8Hz` (ID), rate `-10%` to `-12%`, RVC `pitch_lvl = 0`.
  - `cheerful`: pitch `+18Hz` (JP) / `+22Hz` (ID), rate `+4%` to `+6%`, RVC `pitch_lvl = 1`.
  - `gentle`: pitch `+10Hz` (JP) / `+14Hz` (ID), rate `+0%` to `+2%`, RVC `pitch_lvl = 0`.

---

## 4. Third-Party Message Forwarding via Native Voice Note (PTT)

When users command the assistant to forward messages to friends or contacts ("Kirim pesan dan VN ke Budi: Besok jangan lupa ya"):

### Step-by-Step Procedure
1. **Compound Intent Parsing**:
   Match compound verbs (`kirim pesan dan vn`, `kirim vn ke`, `vn si [nama]`, `kirim wa ... sekalian vn nya`).
2. **Conversational Tail Stripping**:
   Strip trailing triggers like `"sekalian vn nya"` or `"sama vn nya juga"` from the message payload before passing to LLM translation and TTS:
   ```python
   clean_msg = re.sub(r"\s*(?:sekalian|sama|beserta)?\s*(?:kirim|sertakan)?\s*(?:vn|voice\s*note|pesan\s*suara)(?:\s*nya)?(?:\s*juga)?\s*$", "", msg_body, flags=re.I).strip()
   ```
3. **Character-Attributed Translation**:
   Translate the payload into a concise native character phrase that explicitly attributes the message to the user:
   - Input: `"Besok jangan lupa bawa laptop ya"`
   - Spoken Japanese: `"フェルディナンド君からだよ。明日はノートパソコンを忘れないでね！"`
4. **Dual Dispatch to Recipient**:
   - Send the localized text message so the recipient can read it unambiguously.
   - Transcode the character audio to Opus OGG and send as a native WhatsApp PTT voice note.

---

## 5. WhatsApp Audio Transcoding (Native PTT)

WhatsApp client UI renders standard `.mp3` or `.m4a` attachments as generic audio boxes without scrubbable waveforms. To generate true voice notes:
```bash
ffmpeg -y -i input.mp3 -c:a libopus -b:a 32k -vn output.ogg
```
In Baileys (Node.js):
```javascript
await sock.sendMessage(targetJid, {
    audio: fs.readFileSync(outputOgg),
    mimetype: 'audio/ogg; codecs=opus',
    ptt: true
});
```

---

## 6. Pitfalls & Anti-Patterns

| Pitfall | Root Cause | Preventive Rule |
| :--- | :--- | :--- |
| **High-Index Octave Screeching** | `index_influence` set to 0.70–0.75 forces nearest-neighbor replacement on high frequencies (>350 Hz), causing sudden octave jumps (600–700 Hz) and metallic distortion. | Calibrate `index_influence = 0.40–0.45` and set `consonant_breath_protection = 0.33` for silky smooth high-pitch stability. |
| **Lowpass Filter Presence Loss** | Setting lowpass filters to 9500 Hz destroys the breath sparkle and upper harmonic presence (10–18 kHz) of anime voice acting. | Use studio broadcast filter: `highpass=f=45, lowpass=f=18000, volume=1.05` at 192kbps MP3. |
| **OmniVoice Onset Breath/Murmur ("Yoo..." Artifact)** | Autoregressive TTS models synthesize a 100–300ms onset burst followed by an energy valley before speech starts; downstream RVC turns this into a noisy breath/yoo artifact. | Scan first 3s in 50ms windows, detect the post-burst RMS valley (<0.006), trim to speech onset (>0.015 RMS), and apply 20ms cosine fade-in before RVC conversion. |
| **Latin/Foreign Word Token Stuttering** | Feeding raw Latin words (`YouTube`, `Memories`), emojis, or HTML entities into Japanese neural TTS causes tokenizer breakdown, pitch clamping, and audio glitches. | Sanitize input text through a comprehensive Wasei-Eigo Latin-to-Katakana dictionary and strip 4-byte unicode/markdown before neural TTS synthesis. |
| **Priority Clamping via max()** | Using `priority = max(priority, default_priority)` in task action handlers permanently overwrites low-priority requests (P1) to the default (P2). | Parse priority tokens (`p1`-`p4`, `prioritas 1`-`4`) explicitly and assign directly without clamping against defaults. |
| **From-Scratch RVC Training on Short Noisy Clips** | Training RVC weights from scratch on <15 minutes of uncleaned/YouTube audio produces severely underfitted, raspy, and robotic models. | Use verified pre-trained high-step checkpoints (5000+ steps) and treat short clips only as conditioning prompts for zero-shot synthesizers (OmniVoice), never as from-scratch RVC training corpora. |
| **Ad-Hoc System Python RVC Compilation** | Attempting to install RVC dependencies on bleeding-edge system Python (e.g. Python 3.14 on Windows) fails on Meson/C++ build tools and wheel mismatches. | Always reuse the dedicated pre-configured Python 3.10 CUDA environment (`rvc_env`) with pre-built binary wheels (`infer_rvc_python`, `torch 2.x+cu121`); never install RVC into system Python. |
| **RMVPE Octave Doubling Screech & Vocoder Phase Mismatch** | Steep rising pitch inflections on question marks (`の？`) trick pitch tracking into jumping 280 Hz to 560 Hz; attempting to halve F0 in DSP (`f0 /= 2`) causes severe vocoder phase mismatch, buzzing, and audio destruction. | Never alter F0 arrays in vocoder DSP; sanitize `？` to `。`, expand into calm polite declarative phrasing, and use a calm conditioning prompt. |
| **Static Template Voice Note Overwrite** | Emotion detection classifier returns hardcoded Japanese strings that overwrite the LLM's dynamic dialogue, causing the assistant to repeat the exact same 5-second sentence across every turn. | Emotion classifiers must strictly return emotion enums (`gentle`, `cheerful`, `baka`, `crying`) to select the acoustic prompt; spoken audio must always dynamically match the visual text reply via `ensure_character_japanese_voice()`. |
| **Character Role Dissonance on User Sadness** | Mapping user sadness to character `crying` mode forces comforting words through a weeping reference prompt, causing tremolo flutter and vocal instability. | Route user sadness to `gentle` (Angel Caretaker); reserve `crying` strictly for character vulnerability. |
| **Micro-Clip Truncation Trap** | Hyper-restricting Japanese dialogue (<15 characters) to avoid latency produces hollow, abrupt 2-word clips. | Keep lines substantial (~35–55 characters, ~6–9s) using 2–3 comma-punctuated clauses with breath pauses. |
| **Unisolated BGM in Reference Prompts** | Conditioning diffusion models on raw anime clips containing BGM treats music frequencies as vocal cords, causing harmonic buzzing, phase cancellation, and vocal glitching. | Always isolate pure vocal stems using HDemucs (`HDEMUCS_HIGH_MUSDB_PLUS`) before encoding reference prompts. |
| **Japanese Onomatopoeic Pseudo-Words** | Writing sobbing sounds literally (`うぅ……`, `ううう`) causes neural TTS to pronounce a monotone, robotic drone vowel. | Sanitize script text (`うぅ` -> `……っ`); let punctuation pauses, glottal breath catches, and clean emotional reference prompts express crying naturally. |
| **Runaway Conversational Cadence** | Japanese TTS engines rush through unpunctuated clauses at 8–10 mora/second, sounding like breathless rapping. | Insert commas (`、`) after particles (`は`, `が`, `を`, `に`, `で`, `から`, `ので`) on clauses over 15 mora to maintain conversational pace (~5.5–6.5 mora/s). |
| **Double Pitch Shifting in Hybrid Pipelines** | Applying RVC pitch shifts (`pitch_lvl = +1`) on top of already pitch-conditioned OmniVoice audio causes pitch-aliasing, screeching, and harmonic breakdown. | Set RVC `pitch_lvl = 0` and `index_influence = 0.70` in dual-stage pipelines; restrict `pitch_lvl = +1` to flat Edge-TTS fallback. |
| **Acoustic Blindness in Voice Note Responses** | Routing emotion solely via text keywords ignores user vocal exhaustion, replying with cheerful/tsundere banter when the user is tired or sick. | Extract acoustic prosody (RMS energy, ZCR, pause ratio) from incoming audio; route low-energy low-pitch voice notes to gentle whisper care. |
| **Robotic Fallback on Foreign Text** | Feeding non-native text to models trained on Japanese anime corpora corrupts phoneme mapping. | Always separate visual text (`reply`) from spoken native text (`japanese_voice`). |
| **Stiff TTS Prosody in RVC Pipeline** | Running RVC over generic neural TTS (Edge-TTS Nanami) only modifies formant timbre; the stiff, mechanical pacing of the base TTS remains. | Prioritize zero-shot diffusion (OmniVoice `num_step=8` for ~1.6s latency) to capture natural breathing and prosody; keep Edge-TTS + RVC as fallback. |
| **CUDA Unspecified Launch Failure in Pitch Estimation** | Running multiple large audio neural nets concurrently exhausts VRAM during RMVPE pitch extraction. | Dedicate 100% of GPU memory to the active inference pipeline; do not load inactive models into PyTorch CUDA memory. |
| **Flat Indonesian Adult Pitch in Companion TTS** | Passing default pitch on Indonesian neural voices sounds like a mature adult woman rather than a sweet anime heroine. | Shift base TTS pitch `+16Hz` and apply RVC `pitch_lvl = +1`; raise offline fallback to `+26Hz`. |
| **Conversational Trigger Leakage** | Trailing instructions ("sekalian vn nya") leak into the synthesized voice. | Strip trailing triggers via regex before TTS generation. |
| **Generic File Attachment vs PTT** | Sending `.mp3` directly results in a generic audio file rather than a green waveform voice note. | Transcode to Opus OGG with `libopus` and specify `ptt: true`. |
| **Marathon Technical Speech & Diffusion Degradation** | Translating complete multi-step technical instructions into spoken Japanese (>100 characters / >15s) overwhelms zero-shot diffusion models (OmniVoice), producing flat, rushed, breathless 25-second monologues that exhaust the listener. | Segregate channels: put detailed technical steps (Ctrl+V, paths) into visual chat text, and target the golden 45–70 character sweet spot (6–9.5s) for spoken audio expressing the warm emotional reaction. |
| **Emotion Prompt Pitch Distortion** | Using distinct pre-computed emotional prompt tensors (e.g. `prompt_cheerful.pt`) can dramatically distort the fundamental pitch (jumping F0 from 340 Hz to 412 Hz), sounding shrill, strained, and unnatural. | Anchor base voice synthesis to the clean golden master studio prompt (`mahiru_prompt_6s.wav`, F0 ~325–340 Hz); let the Japanese wording, particles, and punctuation natural prosody convey the emotion rather than forcing extreme pitch-shifted prompts. |
| **Trailing Syllable & Vowel Fadeout Muffling** | A heavy 50ms cosine fade-out at the end of speech synthesis cuts off unvoiced trailing syllables, rising interrogative particles, and soft sentence endings. | Keep terminal fade-out to 10–12ms strictly for anti-click smoothing so final vowels and question particles ring out cleanly. |
| **Whisper Tiny Hallucination on Low-Energy Utterances** | Using `faster-whisper-tiny` with greedy decoding (`beam_size=1`) causes absurd hallucinations on casual or short speech (e.g. `tes tes` -> `Astus`). | Deploy `faster-whisper-base` (int8 on CPU in <1s) with `beam_size >= 2` as the quality floor for speech recognition. |
| **Static Single-Prompt Vocal Flatness** | Conditioning zero-shot voice cloning on a single audio clip locks synthesis into one monotone emotional state. | Build a bank of pre-computed emotion prompt tensors (`gentle`, `baka`, `crying`, `cheerful`) and route dynamically by intent/mood. |
| **Repetitive Prompt Re-Encoding Overhead** | Computing voice clone prompts from raw audio files on every turn wastes 1.2–1.8s of GPU time. | Serialize extracted prompt tensors to disk (`torch.save(prompt, "prompt_<emo>.pt")`) and load in `<15ms` during service startup. |
| **Low-Epoch RVC Artifacts & Mechanical Nasality** | Running RVC with low-step models (<1000 steps) or small indexes (<10MB) produces muffled audio and nasal distortion. | Use high-step checkpoints (5000+ steps) paired with a complete feature index (`.index` >100MB) with `index_influence=0.70` for clean vocal cord acoustics. |
| **Voice Call Dry-Text Truncation** | Imposing hyper-strict word limits (e.g. "max 12 words") on visual subtitles ruins dialogue depth. | Decouple channels: allow `reply` to be rich and expressive (2–4 sentences), while restricting only `japanese_voice` length. |
| **Monotonous Pet-Name Saturation** | Prompting assistants to repeat terms of endearment ("sayang", "darling") on every turn creates a hollow, robotic caricature. | Establish canonical honorifics (`[Name]-kun` / `〜君`) as the 70–80% default address, reserving intimate terms for authentic moments of care or vulnerability. |
| **Wrong RVC Inference API** | The full RVC source repo (configs.config + infer.modules.vc.modules.VC) only exists when RVC is cloned as a directory; the pip package `infer_rvc_python` ships a different API. | Use BaseLoader(only_cpu=False) + apply_conf(tag, file_model, pitch_algo, pitch_lvl, file_index, index_influence, ...) + generate_from_cache(audio_data, tag, output_path) for inference-only pipelines; do not import configs.config unless the full RVC repo is present. |
| **Community Model Quality Assumptions** | Download counts and model card descriptions on CivitAI/community sites are unreliable quality signals; multi-character models (e.g. two roles voiced by one VA) bake both timbres together. | Download the .pth and .index, note any per-speaker IDs from the description, render test clips via BaseLoader, and let the ear decide; never replace a working baseline based on metadata alone. | Two node.exe holding one session evict each other; on Windows process.kill SIGKILL is a silent no-op so the zombie keeps the session. | Enforce single instance via PID file plus commandline kill with taskkill /F /PID; back off exponentially on 440, never fixed rapid retry. |
| **Assumed VRAM / GPU Spec** | Sizing models or diffusion steps from a remembered spec silently OOMs or underuses the card when the hardware differs. | Query nvidia-smi for exact model plus total/used VRAM before choosing checkpoints, num_step, or concurrent pipelines. |
| **Webhook Non-JSON 500 Kills Replies** | Bridge calls resp.json(); backend 500 text makes the bridge throw Unexpected-token and send nothing. | Never let the webhook return non-JSON; wrap imports and media helpers in try/except and make the bridge fall back to resp.text. |
| **Phantom Media-Helper Import** | Webhook imports helpers absent from the module, so every message 500s. | Grep the module for defs before wiring imports; media helpers return a safe dict and never throw. |
| **Screen-Record Silence Misdiagnosis** | Screen-record tracks run ~99% silence, so judging robot voice from them misleads. | Verify against the direct bot VN file: decode to 16kHz wav, measure rms/peak/zcr/silence plus 100ms VAD speech groups before claiming regression. |
| **Multi-Profile Timbre Jump** | Switching voice prompts per emotion changes timbre and reads as a different/robotic speaker. | When unified identity is requested, lock one voice prompt plus one RVC config and modulate emotion only through wording and punctuation; cap VN to short clauses. |
| **Manual Double-Start Collision** | Starting the voice agent or message bridge by hand while the main backend autostarts the same dependents causes port conflicts, double VRAM load, and session-eviction loops. | Keep one entry point: the main backend autostarts each dependent only when its port is not listening; never run the dependent launchers manually alongside it; stop scripts must cover every PID-file location. |
| **GPT-SoVITS Epoch Extension** | The S1 trainer auto-resumes the newest ckpt in `logs_s1_v2/ckpt` and S2 resumes its G/D `.pth`, so raising epochs continues training instead of restarting. | Extend epochs in `train_s1.yaml` / `train_s2.json` in place and relaunch the same config; deploy by pointing `tts_infer.yaml` at the newest dated ckpt/pth, then render a probe to verify. |
| **Volume-Metric False Pass** | RMS/peak/ZCR/silence only measure loudness and pauses; they are blind to speaker similarity, metallic buzz, and flat prosody, so a render can pass every gate and still sound nothing like the character. | Never claim a voice is good from metrics alone; verify by human ear, speaker-embedding cosine similarity, or the spectrogram/MFCC/F0 check in `references/voice-similarity-check.md` before declaring a prompt valid. |
| **Prompt Rebuild Masquerading as Training** | Rebuilding a `.pt` prompt re-encodes one short conditioning clip; it teaches the model nothing and cannot fix flat base prosody or an undertrained RVC checkpoint. | Call it conditioning, not training; real training needs minutes of clean dry vocals plus a full RVC training repo (inference-only loaders cannot train). |
| **Reference Transcript Mismatch** | Encoding a prompt with `ref_text` that differs from what is actually spoken in `ref_audio` corrupts phoneme alignment and degrades cloning. | Transcribe the isolated vocal clip first and encode only with its exact transcript. |
| **Short-Stub Translation Bypass** | Checking `if current_jp and len(current_jp) >= 15: return current_jp` skips full translation when upstream prompt produces an unexpanded short stub, generating 3s micro-clips for multi-sentence messages. | Check proportional length between visual reply and Japanese text; prefer joint single-breath generation where both are generated concurrently in one LLM turn. |
