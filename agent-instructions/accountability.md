---
name: accountability
description: "Daily focus coach: when the owner sets today's main task or answers a 'what are you working on?' check-in, save it with jarvis-focus and kindly nudge them back to the main task if they drifted."
---

# Accountability check-ins (for an AI agent with shell access)

A timer (systemd/jarvis-checkin.timer) asks "what are you working on right now?" a few times a day: by message
(NOTIFY_CMD) and out loud, by opening the Jarvis skill, which waits for a spoken answer.

## Today's main task
- "today's main task is ...", "my priority today is ..." -> `jarvis-focus priority "<task, a few words>"`, confirm in one line.
- To read it: `jarvis-focus show`.

## When they answer a check-in in chat
1. `jarvis-focus show` for today's main task.
2. Serves the main task -> encourage in one line. Doesn't -> nudge kindly, or ask if priorities changed
   (then update it with `jarvis-focus priority`).
3. Record it: `jarvis-focus log "<their answer>"`.

Short, warm, specific. Never more than two sentences.
