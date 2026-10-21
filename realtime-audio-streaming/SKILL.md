---
name: realtime-audio-streaming
description: "Use when fixing live mic-to-browser audio."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [audio, streaming, websocket, ffmpeg, webaudio, debugging]
    related_skills: []
---

# Realtime Audio Streaming

## Overview

Live mic-to-browser voice over websocket breaks in the same few places:
capture starvation, timeline holes in the renderer, and chunks too small to
survive jitter. Fix in stage order: capture, then transport, then render.
Verify each stage with bytes, not ears.

## When to Use

- Live microphone audio streamed to a browser or phone app sounds choppy,
  robotic, or drops out, over websocket or any chunked PCM transport.
- Setting up a new mic-to-browser pipeline (capture flags, chunk sizing,
  jitter buffer design).
- A user supplies a recording of bad live audio and asks for root cause.

## Procedure

1. Isolate the stage first. Capture raw bytes at the server output boundary
   and check continuity: constant frame sizes, inter-arrival mean equal to
   the expected chunk duration, realtime ratio >= 1.0. If server output is
   continuous, stop touching capture code — the fault is downstream.
2. Analyze any user recording quantitatively. Decode to PCM mono 16 kHz,
   compute RMS per 50 ms window, print a sound/silence map and segment
   durations (see `references/pcm-gap-analysis.md`). Speech arriving as
   0.1-0.7 s bursts interleaved with 0.1-1.5 s silences means the render
   path is holing the timeline.
3. Set capture flags for Windows dshow: input `-rtbufsize 100M` plus
   `-thread_queue_size 1024` when the device is opened twice, output-side
   `-ac 1 -ar 16000`, `-flush_packets 1`, low-delay flags. Discard ~0.5 s
   warmup before measuring — dshow needs that long to reach realtime.
4. Size transport frames around 128 ms (4096 B mono 16-bit @16 kHz).
   Tens-of-ms frames multiply per-message overhead and jitter sensitivity.
5. Render with a continuous scheduler ahead of the playhead (tick ~50 ms,
   keep ~0.5 s scheduled, fixed ~150 ms buffers), prefill ~350 ms before
   the first sound, PLC-fill on underrun, re-anchor only on real overrun.
6. Re-run the byte-level loop plus the PCM map after the fix. Both must go
green: server ratio >= 1.0 AND the sound/silence map shows continuous
   speech. One without the other is not done.

## Pitfalls

- Never discard silence or all-zero frames in the render path — silence is
  signal, and dropping it holes the timeline into burst/silence chopping.
- Never drive playback off packet arrival — any jitter stalls the schedule;
  schedule continuously and fill gaps with PLC instead of going quiet.
- Keep audio-only constraints (`-sample_rate`, `-channels`) on the dshow
  OUTPUT side; as input options the device open fails with I/O error.
- Multiple DirectShow ffmpeg processes on the same microphone device cause
  driver buffer underruns, packet drops, and stuttering on Windows. Spawning
  an ffmpeg process per WebSocket connection quickly causes device handle
  contention, 40%+ silence dropouts, and acoustic comb filtering. Implement a
  Singleton Broadcaster: exactly ONE ffmpeg DirectShow capture process runs on
  the host, broadcasting PCM chunks to all connected WebSocket client queues.
  Terminate the capture process only when the subscriber set becomes empty.
- Uvicorn Websockets Package Dependency (HTTP 404 Silent Rejection): When
  running ASGI/FastAPI daemons under Uvicorn, verify `websockets` or `wsproto`
  is installed in that specific Python virtual environment. Without it, Uvicorn
  silently runs in HTTP-only mode, rejecting all `@app.websocket` routes with
  HTTP 404 Not Found. Any proxy falling back to local capture on 404 will spawn
  a competing local ffmpeg process, triggering the device contention trap.
- Client Singleton WebSocket & Jitter Scheduling: When toggling live audio
  in browser/mobile frontends, explicitly unbind handlers and close existing
  sockets (`ws.onclose = null; ws.close(); ws = null`) before creating a new
  one. Parallel open sockets stream duplicate audio with ~20ms offsets into the
  same AudioContext, causing intense comb filtering echo. Schedule playback
  with a 40ms lead-in jitter buffer instead of rigid 20ms resyncs to avoid
  choppy timeline dropouts.
- Web Audio Jitter Resync Overlap (The "Double Voice" Echo Trap): When
  scheduling incoming WebSocket PCM chunks on `liveAudioNextPlayTime`, NEVER
  jump `startAt` backwards (e.g. `if (startAt > now + 0.45) startAt = now + 0.04;`).
  When network packet bursts push queue time forward, forcing `startAt` back
  schedules new audio chunks directly on top of already-queued future buffers,
  playing both simultaneously through AudioContext. This produces an instant
  artificial "double voice" and hallway echo. Maintain an active source array
  (`liveAudioActiveSources`); when buffer drift or overrun forces a re-anchor,
  call `source.stop()` on all pending future-scheduled nodes and clear the array
  before resetting `liveAudioNextPlayTime = now + lead_in`. Simply changing the
  timestamp leaves previously scheduled nodes alive in Web Audio's hardware
  timeline, playing them concurrently with the newly re-anchored stream.
  Similarly, stop all active nodes immediately on socket close or mute.
- Laptop Microphone Array Stereo Downmix Phase Cancellation: Modern laptops
  (Intel Smart Sound Technology, HP, Dell, Acer) use a stereo dual-mic array
  with physical spatial separation. Capturing with ffmpeg `-ac 1` downmixes
  via `0.5*L + 0.5*R`. Due to time-of-arrival phase differences between left
  and right capsules, constructive/destructive phase interference cancels out
  voice frequencies, causing up to 75% (-12 dB) amplitude drop, hollow "inside
  a barrel" acoustics, and muffled treble. Use a single channel pan filter
  (`-af "pan=mono|c0=c0"`) or capture native stereo to preserve full voice energy.
- Proximity Acoustic Feedback Loop: When testing live CCTV audio from a mobile
  device in the same room as the laptop, the laptop microphone captures the
  phone speaker's output after a 200–400ms network round-trip. The re-captured
  sound is streamed back to the phone, creating an endless multi-echo loop. Test
  from another room or require headphones on the receiving device.
- Double Dynamic Compression & Pumping Trap: Stacking server-side DSP
  compression (`acompressor` in ffmpeg) with client-side Web Audio
  `DynamicsCompressorNode` simultaneously crushes voice dynamic range and pumps
  low-level ambient fan/electronic noise during pauses, making speech sound
  stifled and muffled. Apply gentle compression at only ONE stage (preferably
  server-side DSP or pure transparent gain passthrough on the frontend).
- DirectShow Device Release Race on Stream Transition: When transitioning from an
  idle audio level monitor process to a live streaming broadcaster process,
  terminating the first FFmpeg process requires ~300-400ms sleep on Windows
  before opening the second DirectShow handle; opening immediately causes the
  Windows audio driver to reject the new process or drop buffers.
- Mobile DAC Sample Rate Mismatch: Mobile Android hardware DACs run strictly at
  48,000 Hz. Streaming 16,000 Hz raw PCM forces browser real-time upsampling on
  every discrete buffer source, producing micro-clicks and digital crackle at
  chunk boundaries. Match the stream to native 48,000 Hz or use an AudioWorklet
  continuous circular ring buffer.
- Overly aggressive DSP lowpass filters (<8000Hz) cut vocal presence and
  harmonics, making live audio sound muffled and boomy. Use highpass 80Hz +
  lowpass 18kHz at full 48kHz studio bandwidth.
- Naive PLC that repeats the last 20ms audio slice on tiny arrival delays
  causes buzzing robotic distortion; use a continuous timestamped Web Audio API
  buffer schedule (target latency 150-300ms) without rigid slicing.
- When the user gates fixes behind explanation-first, present evidence and
  the ranked cause list in chat and wait — partial mid-investigation fixes
  contaminate the loop and destroy trust.

## References

- `references/pcm-gap-analysis.md` — decode-to-PCM recipe and burst/silence interpretation rule.
