# Use cases: give your AI agent a voice on Alexa

alexa-voice-announcer turns any Echo or Alexa app into the speaker and microphone of your own AI agent
([Hermes Agent](agents/hermes-agent.md), [OpenClaw](agents/openclaw.md), or anything with an OpenAI-compatible API).
The agent can **fetch data, think, and then tell you out loud**, on a schedule, when something happens, or when you
ask.

Three building blocks make all of these:

| Block | How | Example |
|---|---|---|
| **You ask, it answers** | "Alexa, ask Jarvis to ..." -> your agent | "Alexa, ask Jarvis what's on my calendar" |
| **It tells you** | the agent runs `alexa-announce "..."` | a scheduled job, a webhook, a finished task |
| **It asks you** | the skill opens and listens (check-ins) | "What are you working on?" -> you answer by voice |

---

## Daily life

### Morning briefing that is actually about you
A scheduled agent job at 7:30 checks your calendar, the weather, unread email and today's main task, then speaks a
30-second summary on the bedroom Echo. The full version waits on Telegram.

> *Agent job, every day at 07:30:* "Check my calendar, the weather in my city and my unread email. Write a 3-sentence
> morning briefing and run `alexa-announce` with it. Send the detailed version to me on Telegram."

Echo, 07:30: *"Good morning. You have two calls today, the first at 11. It's 31 degrees with rain after 4, so take an
umbrella. Three emails need a reply, one from the bank."*

### Reminders with context, not just a time
Plain Alexa reminders say fixed text. An agent reminder fetches what you need at the moment it fires:

- *"At 5:45, remind me to leave for the airport, and include the traffic and my flight status."*
- *"Before my 3 pm meeting, tell me who it's with and the last email they sent."*
- *"Every Sunday at 8 pm, tell me what's on my calendar this week."*

### Meals, water, medicines, sleep
Health and habit nudges spoken on the Echo, with the agent adding the useful part:
*"Lunch time. Today's plan is the millet bowl; the ingredients are in the second shelf."* Quiet hours keep the nights
silent (`QUIET_HOURS`).

### Messages to the house from your phone
Send *"tell Alexa I'm 10 minutes away"* to your agent on Telegram or WhatsApp, and the Echo at home says it. Unlike
an Alexa "drop in", it works from any chat app the agent is on.

---

## Focus and accountability

### Check-ins that listen
Three times a day Jarvis opens on your Echo and asks **"What are you working on right now? Is it today's main task?"**
You answer by voice. The agent compares it with the main task you set in the morning and either encourages you or
nudges you back: *"Emails can wait until 4. Back to the launch video?"* Every answer is logged for a weekly review.

```
"Alexa, tell Jarvis my main task today is the launch video."
... 11:00, the Echo: "Check-in: what are you working on right now?"
"I'm answering emails."
... "That's not the launch video. Give it 90 minutes first, then emails."
```

### End-of-day and weekly review
At 9 pm the agent reads the day's check-ins and says what you actually spent the day on. On Sunday it summarizes the
week and asks for next week's main goal.

### Pomodoro with a voice
*"Alexa, ask Jarvis to start a 50-minute focus block on the proposal."* The agent schedules the end, then announces
*"Time's up. You've done two blocks on the proposal today. Take ten."*

---

## Work and long-running jobs

### "On it", then the answer, spoken when ready
Alexa only waits about 8 seconds for a skill, so long tasks don't fit in a normal Alexa conversation. Jarvis answers
*"On it, I'll send the result to Telegram"*, the agent keeps working, and when it finishes it can speak the
headline: *"The competitor research is done. Three of them raised prices this month; details on Telegram."*

Good for research, report writing, video renders, data exports and code agents finishing a task.

### Server, website and CI alerts out loud
- A health-check job finds the website down: *"Heads up, the shop website is not responding since 2:10."*
- CI fails on `main`: *"The build on main failed in the payment tests."*
- A backup did not run last night.

Wire any webhook or cron script to `alexa-announce`, or let the agent decide what is worth saying.

### Creator and business updates
- *"Alexa, ask Jarvis how yesterday's reel did."* The agent pulls the numbers and answers.
- A new order, a new lead or a review below 4 stars: spoken once, details in chat.
- Every evening: *"Today: 14 orders, two refunds, one message waiting from a wholesale customer."*

---

## Home and family

- **Family announcements:** "Homework time", "Dinner is ready", "Lights out in ten minutes", on a schedule or from a
  chat message.
- **Visitors and deliveries:** a doorbell or package-tracking webhook triggers *"Your Amazon package is out for
  delivery, arriving by 6."*
- **Weather and power alerts:** *"Heavy rain expected in an hour; bring the clothes in."*
- **For older parents:** medicine reminders in a familiar voice on their Echo, with a confirmation check-in
  (*"Did you take the evening tablets?"*) and an alert to you on Telegram if there's no answer.

---

## Ideas to build on top

- **Inbox triage by voice:** "Alexa, ask Jarvis what's new" reads only what the agent marked important today.
- **Learning:** a spoken vocabulary word or flashcard at fixed times, with a check-in that quizzes you.
- **Shared house agent:** one server, several Echo devices; pick the room with `device` in `/speak`.
- **Language practice:** the agent asks a question in the language you're learning and corrects your spoken answer.

Have a use case that works well? Open an issue or a pull request to add it here.
