# Alexa voice for Hermes Agent

Use alexa-voice-announcer to talk to [Hermes Agent](https://github.com/NousResearch/hermes-agent) through any Echo or
the Alexa app, and let Hermes speak to you: scheduled briefings, reminders with live data, job updates and check-ins.

This setup runs in production on a small cloud VM next to a Hermes Agent that also handles Telegram.

```
You: "Alexa, ask Jarvis what's on my calendar today"
  -> Alexa -> skill/bridge.py -> Hermes API server (/v1/responses) -> spoken answer

Hermes cron job / chat: "tell Alexa dinner is ready"
  -> alexa-announce -> announcer -> Jarvis opens on the Echo -> spoken
```

## 1. Turn on the Hermes API server

In `~/.hermes/.env`:

```bash
API_SERVER_ENABLED=true
API_SERVER_KEY=<a long random string>      # e.g. openssl rand -hex 32
```

Restart the gateway (`hermes gateway restart`). The OpenAI-compatible API listens on `127.0.0.1:8642`. Check it:

```bash
curl -s http://127.0.0.1:8642/v1/responses \
  -H "Authorization: Bearer $API_SERVER_KEY" -H 'Content-Type: application/json' \
  -d '{"model":"hermes-agent","input":"Say hi in five words"}'
```

## 2. Point the skill at Hermes

`skill/bridge.env`:

```bash
AGENT_URL=http://127.0.0.1:8642/v1/responses
AGENT_MODEL=hermes-agent
AGENT_KEY=<the same API_SERVER_KEY>

# long answers and check-ins go to your Telegram through Hermes itself
NOTIFY_CMD=hermes send -t telegram:<your-chat-id> -f -
NOTIFY_NAME=Telegram
```

The bridge keeps the conversation going within one Alexa session (`previous_response_id`), so follow-up questions
work: *"Alexa, ask Jarvis what's on my calendar"* ... *"and move the 3 pm to tomorrow"*.

## 3. Let Hermes speak

Put the tools on the PATH Hermes uses (`ln -sf ~/alexa-voice-announcer/bin/* ~/.local/bin/`) and add two skills:

```bash
mkdir -p ~/.hermes/skills/productivity/voice-updates ~/.hermes/skills/productivity/accountability
cp ~/alexa-voice-announcer/agent-instructions/voice-updates.md   ~/.hermes/skills/productivity/voice-updates/SKILL.md
cp ~/alexa-voice-announcer/agent-instructions/accountability.md  ~/.hermes/skills/productivity/accountability/SKILL.md
hermes gateway restart
```

Start a new chat (`/new`) so Hermes picks up the skills. Now on Telegram:

- *"Tell Alexa I'm on my way"* -> the Echo says it.
- *"Save for later on Alexa: the invoice is sent"* -> waits in the inbox ("Alexa, ask Jarvis what's new").
- *"My main task today is the launch video"* -> saved; check-ins compare against it.

## 4. Scheduled jobs that speak

Ask Hermes in chat, for example:

> Every day at 7:30, check my calendar, the weather and my unread email. Send me the full briefing here, and also
> speak a 3-sentence version on the Echo with `alexa-announce` (skill voice-updates).

> Every weekday at 13:30, remind me to eat lunch. Speak it on the Echo too.

> Every hour from 10 to 6, check that https://my-shop.example is up. If it's down, announce it on the Echo.

To add speech to cron jobs you already have, append this to each job's prompt (or use
`hermes cron edit <job-id> --prompt "..." --add-skill voice-updates`):

```
Also speak it on the Echo: after composing your message, run `alexa-announce "<a 1-2 sentence spoken version in
plain English, no emoji>"` (skill voice-updates). Keep the full message for this chat as usual.
```

## 5. Check-ins

Install the timer from `systemd/jarvis-checkin.timer` (see the main README). At each time the Echo asks *"What are you
working on?"* and listens. Your spoken answer goes to Hermes, which encourages you or nudges you back, and the same
question arrives on Telegram, where Hermes handles a typed answer with the accountability skill.

## Tips

- **Voice replies on Telegram too:** Hermes can reply with voice notes (`/voice tts`), so the same assistant talks on
  both Telegram and Alexa.
- **One memory:** Alexa questions go to the same Hermes, so anything you tell it by voice is known on Telegram and the
  other way round.
- **Cost:** check-ins and announcements are fixed text and cost nothing; only the agent's answers use the model.
