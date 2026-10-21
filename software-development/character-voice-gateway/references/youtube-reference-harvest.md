# YouTube Reference Harvest for Voice-Clone Prompt Banks

End-to-end pipeline for rebuilding zero-shot voice-clone prompts from
authentic character media (anime raw-clip compilations). Use when the
standing prompt bank sounds stale, robotic, or nothing like the reference.

## Procedure

1. Pull audio-only WAV, mono 16 kHz (Whisper/RVC-friendly, small files):
   `yt-dlp -x --audio-format wav -o "ref.%(ext)s" <url>` then
   `ffmpeg -y -i ref.wav -ar 16000 -ac 1 ref16.wav`.
2. VAD segment scan with stdlib `wave` + `struct` (no heavy deps): score
   100 ms frames by RMS, keep segments above ~0.03 RMS and longer than
   0.5 s, print start-end plus peak per segment for picking.
3. Transcribe candidate segments with local faster-whisper (tiny is enough
   for triage, `language="ja"`, `beam_size=1`) and keep only clips whose
   transcript is clean character speech — drop BGM-heavy, multi-speaker,
   or garbled segments.
4. Isolate dry vocals with HDemucs (`HDEMUCS_HIGH_MUSDB_PLUS` on CUDA,
   vocals stem) before ANY prompt encoding — BGM baked into a prompt
   returns as metallic buzz in every later synthesis.
5. Keep reference clips 3-10 s per the zero-shot model README; longer
   slows inference and can degrade cloning.
6. Rebuild one prompt tensor per emotion (`gentle`, `baka`, `crying`,
   `cheerful`) via `create_voice_clone_prompt`, save as `.pt`, reload on
   daemon start (<15 ms) instead of re-encoding per request.
7. Gate every rebuilt prompt by rendering a probe line and measuring
   speech-segment RMS/peak/ZCR/silence-ratio plus 100 ms VAD speech
   groups against the user's known-good reference clips — ship only when
   the metrics sit inside the reference band.

## Pitfalls

- Transcribe BEFORE isolating to pick clips, but encode prompts only AFTER
  isolation — picking on raw audio is triage, cloning on raw audio is
  contamination.
- Judge robot-voice regressions against the direct bot output file, never
  against screen-record audio (~99 % silence dilutes every whole-file
  average into a false reading).
