# How it works (and how it compares to Voice Monkey)

## The problem

There is no official Alexa API that says "speak this text on my Echo now":

| Official option | Why it doesn't fit |
|---|---|
| Proactive Events (notifications) | Only a yellow ring and a chime; the text is read only when you ask. |
| Reminders API | Speaks, but only fixed text set in advance, prefixed with "Reminder". |
| Custom skill responses | Only speak while you are talking to the skill. |

Services like Voice Monkey fill the gap, with a monthly limit on the free plan.

## How Voice Monkey does it

Looking at the routine Voice Monkey creates in your Alexa account shows the trick. Its trigger is a virtual smart-home
device; its action is **"open the Voice Monkey skill on device X"** (`Alexa.Operation.SkillConnections.Launch`). When
you call its API, Voice Monkey stores your text, triggers the routine, the skill opens on your device, fetches the
text and speaks it. Because it's a normal skill response, it works on Echo devices **and** the Alexa phone app.

## How this project does it

The same idea, all on your own server, with no third party in the middle:

1. **`alexa-announce "text"`** saves the text in `skill/speak.json`.
2. It calls the **announcer** (`announcer/echo.js`), which is signed in to your Amazon account through
   [alexa-remote2](https://github.com/Apollon77/alexa-remote), the library behind Home Assistant's and ioBroker's
   Alexa integrations.
3. The announcer sends Alexa a one-off routine (a "behavior preview") with a single action: **open your own skill
   (Jarvis) on your device**.
4. The device opens Jarvis. Amazon sends a `LaunchRequest` to your HTTPS endpoint (`skill/bridge.py`).
5. Jarvis sees the fresh text in `speak.json` and replies with it, so the device speaks it, then the session ends.

For a **check-in**, step 1 is skipped and a pending check-in is set instead: Jarvis opens, asks *"What are you
working on?"* and keeps the session open, so you can **answer by voice**. Voice Monkey can't do that, because its
skill doesn't know your agent.

The announcer also supports Alexa's built-in **announcement** and **speak** actions (`mode: "announcement" | "speak"`),
which work on Echo devices without any skill. The Alexa phone app accepts those silently but doesn't play them; the
skill-launch route is what makes the phone app talk.

## Comparison

| | Voice Monkey (free) | alexa-voice-announcer |
|---|---|---|
| Messages per month | about 200 | unlimited |
| Cost | free tier, then paid | free (your server) |
| Echo devices | yes | yes |
| Alexa phone app | yes | yes (mode `launch`) |
| Listens for a spoken reply | no | yes (check-ins, follow-up questions) |
| Talks to your AI agent | no | yes (any OpenAI-compatible Responses API) |
| Your text goes through | a third-party service | only Amazon |
| Setup | a few minutes | about an hour (server, skill, HTTPS) |
| Official API | partly (skill + routine) | partly (skill) + unofficial web API for the trigger |

## The sign-in

The announcer needs your Amazon session once. It runs alexa-cookie2's login proxy on the server's localhost; you reach
it through an SSH tunnel and sign in on Amazon's own pages, so the code never sees your password. Amazon returns a
device token, which is saved in `announcer/cookie.json` (mode 600) and refreshed automatically every few days.

Two fixes found while building this, both handled for you:

- **Node 20+:** alexa-cookie2 never noticed the successful sign-in (you ended on an Amazon "page not found").
  `patch-alexa-cookie.js` runs after `npm install` and fixes it.
- **Regional sign-in:** signing in on amazon.in (and likely other regional sites) returns no device code. Signing in
  through amazon.com works for every region except Japan, and is the default (`BASE_AMAZON_PAGE`).

## Limits and risks

- The trigger uses Alexa's **unofficial** web API. Amazon can change it; if it breaks, the optional Voice Monkey
  fallback keeps announcements working.
- `cookie.json` is a full session for your Amazon account. Keep it private and the local APIs on localhost.
- A development skill only runs on the developer's own Amazon account (plus beta testers you invite).
