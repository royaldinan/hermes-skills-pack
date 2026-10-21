---
name: background-worker-reliability
description: 'Use when parent spawns workers and reports results.'
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [subprocess, workers, agents, reliability, reporting]
    related_skills: [systematic-debugging]
---

# Background Worker Reliability

## Overview

A parent that launches a worker and reports its result must read the worker's REAL output and propagate a REAL status. Every shortcut here produces false-success reports: the user is told work finished when nothing ran.

**Core principle:** empty or unread output means FAILURE, never success. Only an explicit success signal earns a success report.

## Procedure

1. Keep the child's stdio piped to the parent (PIPE/DEVNULL to a log file the parent tails). Never detach the console on the spawn path whose output the parent must consume.
2. Have the worker write a structured result (JSON) with an explicit `status` field plus exit code, answer text, and artifact paths. The parent reads status first, text second.
3. Pass the task prompt through byte-for-byte, preferably via a prompt file. A sanitizer may strip one greeting prefix at most; it must never use broad regexes that can delete instruction content.
4. Gate the user-facing report on status: success header only on explicit success, failure header otherwise. Failure text states what failed and what to check, and never claims completion.
5. Detect produced artifacts by snapshot-diff (mtime scan of target dirs before vs after), not by trusting the worker's prose. Cross-check paths the worker mentions against the filesystem.
6. Verify end to end with a real spawn: stale result files from earlier runs must be deleted before launch so a fresh result proves the current run executed.

## Pitfalls

- Detaching the worker console (new window, background daemon) on Windows breaks the parent's pipe, so the parent reads empty output and reports hallucinated success. The mechanism is pipe detachment, not a slow worker. Keep reporting-path workers piped.
- Defaulting missing/empty output to a cheerful success string converts every crash, timeout, and empty run into a false completion. Default missing output to error.
- Aggressive prompt-cleaning regexes silently eat instruction sentences, so the worker executes a mutilated task in seconds and reports success. Anchor cleaners to greeting wrappers only.
- Killing helper processes by image name (blanket kill of all encoders, bridges, or runtimes) also kills the live session the user is watching. Kill by exact PID, and reuse long-lived streams instead of respawning per view.
- A clipboard holds one item: fanning N incoming attachments through it keeps only the last. Persist every inbound attachment to disk (inbox dir) and keep a pending-context record so follow-up messages can reference them.
- Forwarding an attachment as extracted text only means the file is lost when the downstream call fails. Save the bytes first, then extract text.
