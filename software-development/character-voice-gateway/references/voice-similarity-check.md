# Voice Similarity Check (Ear Substitute)

Use when a render passes volume metrics but speaker similarity is disputed.
RMS/peak/ZCR/silence cannot hear timbre — this recipe can, approximately.

## Procedure

1. Load reference (known-good character audio) and candidate at 16 kHz mono
   via `librosa.load(path, sr=16000)`.
2. Per file, compute and print:
   - Log spectrogram: `librosa.amplitude_to_db(abs(librosa.stft(y)), ref=np.max)`
     (all-lowercase `amplitude_to_db` — the camelCase spelling does not exist).
   - Mean MFCC vector: `librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13).mean(axis=1)`.
   - Mean F0: `librosa.yin(y, fmin=50, fmax=600).mean()`.
3. Render side-by-side spectrograms plus MFCC-mean bar charts into one PNG
   (matplotlib `Agg` backend) and inspect it with `vision_analyze`.

## Decision rule

Call the candidate similar only when ALL hold:

- Both spectrograms show a sustained voiced harmonic ladder (bright F0 track
  plus 2–3 parallel harmonics with intonation movement), not a diffuse
  smeared block or one short burst surrounded by silence.
- Mean F0 within ~25 Hz for same-gender character voices.
- Same MFCC-mean morphology: `c0 << 0`, dominant positive `c1`, negative `c2`,
  positive `c3`, then small alternating values — not a flat/sparse vector with
  near-zero upper coefficients (that shape means silence-heavy or failed audio).

## Pitfalls

- Compare against the direct bot output file, never a screen recording.
- A truncated render (high silence ratio, single energy burst) fails the
  harmonic-ladder check even when its peak looks healthy — that indicts the
  serving endpoint, not the trained checkpoint.
