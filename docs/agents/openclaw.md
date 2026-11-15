# Alexa voice for OpenClaw

Use alexa-voice-announcer to talk to your [OpenClaw](https://docs.openclaw.ai) agent through any Echo or the Alexa app,
and let OpenClaw speak to you: briefings, reminders with live data, alerts and check-ins.

```
You: "Alexa, ask Jarvis to summarize my unread email"
  -> Alexa -> skill/bridge.py -> OpenClaw gateway (/v1/responses) -> spoken answer

OpenClaw cron job / chat: "tell Alexa the build failed"
  -> alexa-announce -> announcer -> Jarvis opens on the Echo -> spoken
```

> OpenClaw changes quickly. The config keys below follow the OpenClaw docs at the time of writing; check
> [OpenResponses API](https://docs.openclaw.ai/gateway/openresponses-http-api) for your version.

## 1. Turn on the gateway's OpenResponses endpoint

The `/v1/responses` endpoint is off by default. In `~/.openclaw/openclaw.json`:

```json5
{
  gateway: {
    auth: { mode: "token", token: "<a long random string>" },
    http: { endpoints: { responses: { enabled: true } } }
  }
}
```

Restart the gateway, then check it (the gateway listens on port 18789 by default):

```bash
curl -s http://127.0.0.1:18789/v1/responses \
  -H "Authorization: Bearer <gateway token>" -H 'Content-Type: application/json' \
  -d '{"model":"openclaw:main","input":"Say hi in five words"}'
```

Keep the gateway on localhost. The bridge runs on the same machine.

## 2. Point the skill at OpenClaw

`skill/bridge.env`:

```bash
AGENT_URL=http://127.0.0.1:18789/v1/responses
AGENT_MODEL=openclaw:main          # openclaw:<agentId>
AGENT_KEY=<gateway token>
AGENT_USER=alexa                   # one stable OpenClaw session for everything said through Alexa

# long answers and check-ins: a Telegram bot (or any command that reads stdin)
NOTIFY_CMD=/home/<you>/alexa-voice-announcer/bin/notify-telegram
NOTIFY_NAME=Telegram
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

`AGENT_USER` matters for OpenClaw: without it every request starts a fresh session; with it, voice questions share
one conversation and follow-ups work.

## 3. Let OpenClaw speak

OpenClaw skills are folders with a `SKILL.md`. Copy the two instructions into your workspace skills:

```bash
mkdir -p ~/.openclaw/workspace/skills/voice-updates ~/.openclaw/workspace/skills/accountability
cp ~/alexa-voice-announcer/agent-instructions/voice-updates.md  ~/.openclaw/workspace/skills/voice-updates/SKILL.md
cp ~/alexa-voice-announcer/agent-instructions/accountability.md ~/.openclaw/workspace/skills/accountability/SKILL.md
openclaw skills list      # both should appear
```

Make sure the agent can run shell commands and that `alexa-announce`, `alexa-say` and `jarvis-focus` are on its PATH
(`ln -sf ~/alexa-voice-announcer/bin/* ~/.local/bin/`).

Now, from WhatsApp, Telegram, Discord or wherever you talk to OpenClaw:

- *"Tell Alexa the guests are here"* -> the Echo says it.
- *"Put it on Alexa for later: call the accountant"* -> inbox ("Alexa, ask Jarvis what's new").

## 4. Scheduled jobs that speak

Ask OpenClaw to schedule them (it creates cron jobs; see `openclaw cron list`):

> Every weekday at 8:00, check my calendar and the weather, then speak a 3-sentence briefing on the Echo with
> `alexa-announce`, and send me the details here.

> Every 30 minutes, check if https://my-api.example/health returns 200. If not, announce "the API is down" on the
> Echo once, and again only when it's back.

> Every Sunday at 20:00, look at this week's calendar and tell me on the Echo what's coming.

## 5. Check-ins

Install `systemd/jarvis-checkin.timer` (see the main README). At each time Jarvis opens on your Echo, asks what you're
working on and listens. OpenClaw judges the answer against today's main task (set it by voice: *"Alexa, tell Jarvis
my main task today is the pitch deck"*, or in chat with the accountability skill).
