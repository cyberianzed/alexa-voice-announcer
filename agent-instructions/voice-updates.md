---
name: voice-updates
description: "Alexa / Echo messages: when the owner says tell Alexa, announce, say it on Alexa or on the Echo, speak it now with alexa-announce. Use alexa-say (the inbox, heard later) only to save it for later or when announcing fails."
---

# Speak on Alexa (for an AI agent with shell access)

Drop this into your agent's skills / system prompt. It assumes `alexa-announce` and `alexa-say` are on the PATH.

## Default: speak it now
When the owner sends anything meant for Alexa or the Echo ("tell Alexa ...", "announce ...", "say it on the Echo"):

`alexa-announce "<the message, 1-2 short sentences>"`

- It plays right away on the Echo / Alexa app. Do not also put it in the inbox.
- Reply in one line: "Announced: <message>".
- Write for the ear: plain words, no markdown, links or emoji, about 30 words at most.

## Only when they want it for later: the inbox
Run `alexa-say "<message>"` if they say "save it for later", "put it in my updates", or if `alexa-announce` fails
(then tell them it was queued instead, and why). They hear it with "Alexa, ask Jarvis what's new".

## Updates from finished jobs
When a long job finishes or waits for approval, send one short `alexa-say "<what happened and what to do>"`.

## Scheduled messages
For reminders and scheduled nudges, compose the message as usual, then also run `alexa-announce` with a 1-2 sentence
spoken version.
