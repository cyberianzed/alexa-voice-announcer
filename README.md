# alexa-voice-announcer

**Make Alexa speak any text from your own server: free, unlimited, self-hosted.**
A Voice Monkey alternative with no monthly limit, plus **Jarvis**, a private Alexa skill that gives your AI agent a voice:
two-way voice chat, spoken announcements, an inbox, and accountability check-ins that listen for your answer.

Send a message from a script, cron job, Telegram bot or AI agent, and your **Amazon Echo or the Alexa phone app says it out
loud**.

```bash
alexa-announce "Lunch is ready."
alexa-announce "Your video render finished. Check Telegram."
curl -X POST localhost:8095/speak -H 'Content-Type: application/json' -d '{"text":"Hello from my server"}'
```

> Keywords: Alexa announcement API, make Alexa speak text, Echo text-to-speech from a script, free Voice Monkey alternative,
> unlimited Alexa notifications, Alexa TTS from cron / Python / Node / Telegram, self-hosted Alexa announcer, Alexa skill
> for an AI agent, talk to your AI agent through Alexa, Jarvis for Alexa.

---

## Why

- **Voice Monkey** and similar services work well, but the free tier is about 200 requests a month. Hourly reminders,
  check-ins and agent updates use that up in days.
- **Alexa Notifications / Proactive Events** only show a yellow ring; they do not speak.
- **Alexa Reminders** speak, but only fixed text and always as "Reminder: ...".

This project speaks **any text, any time, as often as you like**, from a server you own.

## Features

| | |
|---|---|
| **Free and unlimited** | Runs on your server (a free cloud VM works). No per-message cost, no quota. |
| **Works on the Alexa phone app** | Mode `launch` opens your own skill on the device, the same way Voice Monkey's routine does, so even the phone app talks. |
| **Echo announcements** | Mode `announcement` (with chime) or `speak` on Echo devices. |
| **Two-way voice** | "Alexa, ask Jarvis to ..." sends your words to your AI agent; short answers are spoken, long jobs report to Telegram. |
| **Check-ins that listen** | A timer asks "what are you working on?" out loud and waits for your spoken answer; the agent nudges you back on track. |
| **Inbox** | Agents queue updates; "Alexa, ask Jarvis what's new" reads them. |
| **Private by default** | Amazon signature check, skill-ID lock, pairs with one Alexa user; local APIs listen on localhost only. |
| **Backup** | Optional Voice Monkey fallback if the announcer is down. |

## How it works

```
 script / cron / agent / Telegram
            │  alexa-announce "text"
            ▼
   skill/focus.py ── queues the text (speak.json)
            │
            ▼  POST /speak {mode: "launch"}
   announcer/echo.js (Node, alexa-remote2) ── signed in to your Amazon account once
            │  runs a routine action: "open skill <your skill> on <device>"
            ▼
   Echo / Alexa app opens your skill ──► Amazon calls your HTTPS endpoint
                                               │
                                               ▼
                                   skill/bridge.py speaks the queued text
                                   (or asks the check-in and listens)
```

The announcer uses the same unofficial Alexa web API as Home Assistant's Alexa Media Player and ioBroker's Alexa
adapter, through [alexa-remote2](https://github.com/Apollon77/alexa-remote). You sign in once through a local login
proxy; the session is stored on your server and refreshed automatically. Your password never touches this code.

## Repository layout

```
announcer/            Node service: speaks on Echo / Alexa app (localhost:8095)
  echo.js             HTTP API: /speak, /devices, /routines, /status
  patch-alexa-cookie.js  postinstall fix for the sign-in proxy on Node 20+
  echo.env.example
skill/                Python backend for the Jarvis Alexa custom skill (localhost:8090)
  bridge.py           voice chat with your agent, queued announcements, inbox, check-ins
  focus.py            announce(), today's main task, check-ins (CLI too)
  notify_ring.py      optional Echo notification ring (Proactive Events)
  interaction-model.json  paste into the Alexa console JSON editor
  bridge.env.example
bin/                  alexa-announce, alexa-say, jarvis-focus, notify-telegram
systemd/              user services and the check-in timer
deploy/Caddyfile.example  HTTPS in front of the skill
agent-instructions/   drop-in instructions so an AI agent uses all of this
```

## Requirements

- A Linux server that is always on (a free Oracle Cloud / any VPS works), Python 3.9+, Node 18+.
- A public HTTPS endpoint for the skill (Caddy + a domain, or `<your-ip>.sslip.io`). Ports 80 and 443 open.
- A free [Alexa developer account](https://developer.amazon.com/alexa/console/ask), signed in with the **same Amazon
  account as your Echo / Alexa app**, so the development skill is enabled on your devices.
- Announcements-only (`announcement` / `speak` modes on Echo devices) need just the announcer, no skill and no HTTPS.

## Setup

### 1. Get the code

```bash
git clone https://github.com/cyberianzed/alexa-voice-announcer.git ~/alexa-voice-announcer
cd ~/alexa-voice-announcer
```

### 2. The announcer

```bash
cd announcer
npm install                      # also applies the Node 20 sign-in fix
cp echo.env.example echo.env     # set AMAZON_PAGE to your region (amazon.com, amazon.in, amazon.co.uk ...)
mkdir -p ~/.config/systemd/user && cp ../systemd/alexa-announcer.service ~/.config/systemd/user/
systemctl --user daemon-reload && systemctl --user enable --now alexa-announcer
loginctl enable-linger "$USER"   # keep user services running after you log out
```

**Sign in once.** The login page only listens on the server's localhost, so open an SSH tunnel from your computer:

```bash
ssh -N -L 3456:127.0.0.1:3456 user@your-server
```

Open <http://localhost:3456> in your browser, sign in with the Amazon account your Echo / Alexa app uses, and approve the
OTP if asked. You should see "Amazon Alexa Cookie successfully retrieved". Then check:

```bash
curl -s localhost:8095/status      # {"ready":true,...}
curl -s localhost:8095/devices     # your Echo devices and Alexa apps
curl -s -X POST localhost:8095/speak -H 'Content-Type: application/json' -d '{"text":"It works"}'
```

Echo devices speak now. For the **Alexa phone app**, and for check-ins that listen, set up the skill.

### 3. The Jarvis skill

1. In the [Alexa developer console](https://developer.amazon.com/alexa/console/ask), create a **Custom** skill
   ("Provision your own" backend), invocation name `jarvis` (or your own).
2. **Build > JSON Editor:** paste `skill/interaction-model.json`, save, and build the model.
3. **Build > Endpoint:** HTTPS, `https://your-host/`, certificate type "My development endpoint has a certificate from
   a trusted certificate authority".
4. **Test:** set "Skill testing is enabled in" to **Development**.
5. On the server:

```bash
cd ~/alexa-voice-announcer/skill
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp bridge.env.example bridge.env && chmod 600 bridge.env    # SKILL_ID, AGENT_URL, NOTIFY_CMD, TIMEZONE ...
cp ../systemd/alexa-skill.service ~/.config/systemd/user/
systemctl --user daemon-reload && systemctl --user enable --now alexa-skill
```

6. HTTPS: install [Caddy](https://caddyserver.com/docs/install) and use `deploy/Caddyfile.example`.
7. Say **"Alexa, open Jarvis"** once. Jarvis pairs with your Alexa user; everyone else is refused.
8. Put your skill ID in `announcer/echo.env` (`SKILL_ID=`), pick your speaker (`ECHO_DEVICE=` from `/devices`) and
   restart the announcer: `systemctl --user restart alexa-announcer`.

Now `bin/alexa-announce "text"` opens Jarvis on that device and Jarvis speaks the text, including on the phone app.

### 4. Command-line tools (optional)

```bash
mkdir -p ~/.local/bin && ln -sf ~/alexa-voice-announcer/bin/* ~/.local/bin/
alexa-announce "Dinner is ready"          # speak now (quiet hours respected)
alexa-say "Your render is done"           # inbox: "Alexa, ask Jarvis what's new"
jarvis-focus priority "Finish the report" # today's main task
jarvis-focus checkin                      # ask "what are you working on?" now
```

### 5. Check-ins (optional)

Edit the times and time zone in `systemd/jarvis-checkin.timer`, then:

```bash
cp ~/alexa-voice-announcer/systemd/jarvis-checkin.* ~/.config/systemd/user/
systemctl --user daemon-reload && systemctl --user enable --now jarvis-checkin.timer
```

At each time, Jarvis opens on your device, asks what you are working on, and listens. Your answer is compared with
today's main task by your agent, which encourages you or nudges you back.

### 6. Connect your AI agent

- **Voice to agent:** `AGENT_URL` takes any OpenAI-compatible **Responses API** (`/v1/responses`): a local agent
  server, or a small proxy to OpenAI, Claude or a local model.
- **Agent to voice:** give your agent shell access to `alexa-announce` / `alexa-say` and add the files in
  `agent-instructions/` to its skills or system prompt.
- **Telegram:** set `NOTIFY_CMD=~/alexa-voice-announcer/bin/notify-telegram` with your bot token and chat ID.

## Spoken phrases

| Say | What happens |
|---|---|
| "Alexa, ask Jarvis to check my server" | Your agent answers out loud (or on Telegram if it takes long) |
| "Alexa, ask Jarvis what's new" | Reads queued updates |
| "Alexa, tell Jarvis my main task today is the launch video" | Sets today's main task |
| "Alexa, ask Jarvis to check in with me" | Starts a check-in |
| "I'm working on emails" (during a check-in) | Agent compares it with your main task and responds |

## Announcer API

`POST /speak` with JSON:

| Field | Values |
|---|---|
| `text` | What to say (up to 1000 characters). Not needed for `launch`. |
| `mode` | `announcement` (default), `speak`, `launch` |
| `device` | Name or serial from `/devices`. Default: `ECHO_DEVICE` or the first online one. |
| `skill` | Skill ID for `launch` (default `SKILL_ID`) |

The API listens on 127.0.0.1 only. Never expose port 8095 or 3456 to the internet: anyone with access can speak on
your devices.

## Troubleshooting

| Problem | Fix |
|---|---|
| After signing in you see Amazon's "page not found" | Run `npm install` again (it applies `patch-alexa-cookie.js`), restart, sign in again. |
| Sign-in page is in German | Set `ACCEPT_LANGUAGE` in `echo.env` (e.g. `en-US`), restart. |
| `amazon.in` / regional sign-in returns no code | Keep `BASE_AMAZON_PAGE=amazon.com` (works for all regions except Japan). |
| `/devices` shows only "This Device" | Those are Alexa phone apps. Announcements do not play there; use mode `launch` with the skill. If your Echo is missing, you signed in with a different Amazon account. |
| Jarvis does not open from `launch` | The skill must be enabled on the same Amazon account (development skills are, for the developer's own account). |
| Nothing is spoken at night | `QUIET_HOURS` in `skill/bridge.env`. |
| Session expired | Delete `announcer/cookie.json`, restart, sign in again through the tunnel. |

## Security and privacy

- `cookie.json` is a full Amazon session for your account. It is stored with mode 600 and must never be committed or
  shared. `.gitignore` excludes it, every `*.env` file, and all personal state files.
- The skill backend verifies Amazon's signature and timestamp on every request, accepts only your `SKILL_ID`, and
  serves only the first Alexa user who paired.
- This project uses an **unofficial** Alexa web API. Amazon may change it at any time; use at your own risk. It is not
  affiliated with or endorsed by Amazon.

## Credits

- [alexa-remote2](https://github.com/Apollon77/alexa-remote) and [alexa-cookie2](https://github.com/Apollon77/alexa-cookie)
  by Apollon77, which do the hard work of talking to Alexa.
- [Alexa Skills Kit SDK for Python](https://github.com/alexa/alexa-skills-kit-sdk-for-python) for request verification.

## License

MIT. See [LICENSE](LICENSE).
