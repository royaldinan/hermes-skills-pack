# PCM Gap Analysis: Decode-to-PCM Recipe

Decode any recording of suspect live audio to raw PCM and map sound vs
silence per 50 ms window:

```bash
ffmpeg -v error -i sample.mp3 -ac 1 -ar 16000 -f s16le pipe:1 > sample.raw
```

```python
import struct, math
raw = open('sample.raw', 'rb').read()
n = len(raw) // 2
s = struct.unpack('<' + str(n) + 'h', raw[:n * 2])
win = 800  # 50 ms @16 kHz
states = []
for i in range(0, n - win, win):
    seg = s[i:i + win]
    rms = math.sqrt(sum(x * x for x in seg) / win)
    states.append(1 if rms > 300 else 0)
bar = ''.join('#' if v else '.' for v in states)
for k in range(0, len(bar), 70):
    print(f'{k * 0.05:5.1f}s ' + bar[k:k + 70])
# segment sound/silence durations
segs, cur, ln = [], states[0], 1
for v in states[1:]:
    if v == cur:
        ln += 1
    else:
        segs.append((cur, round(ln * 0.05, 2)))
        cur, ln = v, 1
segs.append((cur, round(ln * 0.05, 2)))
print(segs)  # (1=sound, 0=silence) with durations in seconds
```

Interpretation rule: continuous speech arriving as 0.1-0.7 s sound bursts
interleaved with 0.1-1.5 s silences means the playback path is holing the
timeline (dropped or discarded frames, pump stalling on underrun) — the
capture side is exonerated regardless of how it sounds to the ear.
