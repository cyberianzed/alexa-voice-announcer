#!/usr/bin/env python3
"""Jarvis: an Alexa custom skill backend for your own server.

- Talk to your AI agent by voice ("Alexa, ask Jarvis to ..."): words go to any OpenAI-compatible /v1/responses API.
  Short answers are spoken; long jobs are acknowledged and the result is sent with NOTIFY_CMD (e.g. Telegram).
- Speaks queued announcements when the announcer opens the skill on your Echo / Alexa app (speak.json).
- Inbox ("Alexa, ask Jarvis what's new"), daily main task and accountability check-ins (see focus.py).

Security: every request is verified as Amazon's (certificate chain, signature, timestamp), must carry SKILL_ID, and
only the first Alexa user who opens the skill (saved in paired_user) is served. Listens on localhost only; put an
HTTPS reverse proxy (e.g. Caddy) in front. Settings: bridge.env (see bridge.env.example).
"""
import json
import re
import subprocess
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from ask_sdk_webservice_support.verifier import RequestVerifier, TimestampVerifier, VerificationException

HERE = Path(__file__).resolve().parent
ENV = {}
if (HERE / "bridge.env").exists():
    for line in (HERE / "bridge.env").read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            ENV[k.strip()] = v.strip()
SKILL_ID = ENV.get("SKILL_ID", "")
AGENT_URL = ENV.get("AGENT_URL", "http://127.0.0.1:8642/v1/responses")
AGENT_MODEL = ENV.get("AGENT_MODEL", "agent")
AGENT_KEY = ENV.get("AGENT_KEY", "")
AGENT_USER = ENV.get("AGENT_USER", "")
NOTIFY_CMD = ENV.get("NOTIFY_CMD", "")       # shell command that reads a message on stdin (e.g. bin/notify-telegram)
NOTIFY_NAME = ENV.get("NOTIFY_NAME", "Telegram")
NAME = ENV.get("ASSISTANT_NAME", "Jarvis")
PORT = int(ENV.get("PORT", "8090"))
SPEAK_WAIT_S = 6.0           # Alexa waits about 8 s; past this we answer "on it" and finish on NOTIFY_CMD
PAIRED = HERE / "paired_user"
VOICE_RULES = ("[Spoken through Alexa. Answer in 1-3 short spoken sentences, plain words, no markdown, no lists, "
               f"no links. For long work, start it and say the result will come on {NOTIFY_NAME}.]\n")
SESSIONS = {}                # Alexa session id -> the agent's previous response id (keeps the conversation)
INBOX = HERE / "inbox.jsonl"  # updates for Alexa: {"at", "text", "read"}; written by alexa-say and by long jobs
verifiers = [RequestVerifier(), TimestampVerifier()]


def log(msg):
    print(time.strftime("%Y-%m-%d %H:%M:%S"), msg, flush=True)


def agent(text, prev=None, timeout=900):
    body = {"model": AGENT_MODEL, "input": VOICE_RULES + text}
    if AGENT_USER:                 # stable session key for agents that use it (e.g. OpenClaw)
        body["user"] = AGENT_USER
    if prev:
        body["previous_response_id"] = prev
    headers = {"Content-Type": "application/json"}
    if AGENT_KEY:
        headers["Authorization"] = f"Bearer {AGENT_KEY}"
    req = urllib.request.Request(AGENT_URL, data=json.dumps(body).encode(), method="POST", headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read())
    out = []
    for item in data.get("output") or []:
        for c in item.get("content") or []:
            if c.get("type") in ("output_text", "text") and c.get("text"):
                out.append(c["text"])
    return " ".join(out).strip() or (data.get("output_text") or "").strip(), data.get("id")


def spoken(text, limit=700):
    t = re.sub(r"```.*?```", " ", text, flags=re.S)
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)
    t = re.sub(r"https?://\S+", f"the link on {NOTIFY_NAME}", t)
    t = re.sub(r"MEDIA:\S+", "", t)
    t = re.sub(r"[*_#>`|]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t if len(t) <= limit else t[:limit].rsplit(". ", 1)[0] + f". The rest is on {NOTIFY_NAME}."


def notify(text):
    """Send a message to the owner (Telegram etc.) with NOTIFY_CMD; silently skipped when not set."""
    if not NOTIFY_CMD:
        return
    try:
        subprocess.run(["bash", "-lc", NOTIFY_CMD], input=text.encode(), timeout=300)
    except Exception as e:  # noqa: BLE001
        log(f"notify failed: {e}")


def inbox_add(text):
    import fcntl
    with open(INBOX, "a", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.write(json.dumps({"at": time.time(), "text": text.strip(), "read": False}) + "\n")
    try:
        import notify_ring   # optional: the Echo's yellow notification ring (Proactive Events)
        notify_ring.ring()
    except Exception as e:  # noqa: BLE001
        log(f"no notification ring: {e}")


def inbox_unread():
    if not INBOX.exists():
        return []
    items = [json.loads(x) for x in INBOX.read_text(encoding="utf-8").splitlines() if x.strip()]
    return [x for x in items if not x.get("read")]


def inbox_mark_read():
    if not INBOX.exists():
        return
    items = [json.loads(x) for x in INBOX.read_text(encoding="utf-8").splitlines() if x.strip()]
    items = [dict(x, read=True) for x in items][-50:]          # keep the last 50
    INBOX.write_text("".join(json.dumps(x) + "\n" for x in items), encoding="utf-8")


def reply(text, end=False, reprompt="Anything else?", attrs=None):
    r = {"outputSpeech": {"type": "PlainText", "text": text}, "shouldEndSession": end}
    if not end:
        r["reprompt"] = {"outputSpeech": {"type": "PlainText", "text": reprompt}}
    out = {"version": "1.0", "response": r}
    if attrs:
        out["sessionAttributes"] = attrs
    return out


def read_updates():
    new = inbox_unread()
    if not new:
        return reply("No new updates. Anything else?")
    parts = [f"Update {i}. {spoken(x['text'], 300)}" for i, x in enumerate(new[:5], 1)]
    more = f" And {len(new) - 5} more on {NOTIFY_NAME}." if len(new) > 5 else ""
    inbox_mark_read()
    return reply(" ".join(parts) + more + " Anything else?")


def checkin_judge(answer):
    """The owner's spoken answer to a check-in, against today's main task. One short agent call."""
    import focus
    main = focus.priority()
    prompt = (f"[Accountability check-in] Today's main task: {main or 'not set'}. The owner says they are working on: "
              f"{answer}. Reply in 1-2 warm spoken sentences. If it serves the main task, encourage briefly. If not, "
              "kindly nudge them back to it, or ask whether priorities changed. If no main task is set, ask them to "
              "set one by saying: my main task today is ...")
    result, done = {}, threading.Event()

    def run():
        try:
            result["text"], _ = agent(prompt)
        except Exception as e:  # noqa: BLE001
            result["error"] = str(e)
        done.set()

    threading.Thread(target=run, daemon=True).start()
    ok = done.wait(SPEAK_WAIT_S)
    verdict = spoken(result.get("text", ""), 400) if ok and "error" not in result else ""
    focus.log_answer(answer, verdict)
    if verdict:
        return reply(verdict + " Anything else?")

    def later():
        done.wait()
        notify(f"Check-in: you said \"{answer}\"\n\n{result.get('text') or 'Noted.'}")

    threading.Thread(target=later, daemon=True).start()
    return reply(f"Noted. I will send my thoughts to your {NOTIFY_NAME}.", end=True)


def handle(req):
    rq = req.get("request") or {}
    sess = req.get("session") or {}
    system = (req.get("context") or {}).get("System") or {}
    app = (sess.get("application") or {}).get("applicationId") or (system.get("application") or {}).get("applicationId")
    if SKILL_ID and app != SKILL_ID:
        raise PermissionError("wrong skill")
    user = (sess.get("user") or {}).get("userId") or (system.get("user") or {}).get("userId", "")
    if not PAIRED.exists():
        PAIRED.write_text(user)
        log("paired with the first Alexa user")
    if user != PAIRED.read_text().strip():
        return reply("Sorry, this assistant is private.", end=True)
    kind, sid = rq.get("type"), sess.get("sessionId", "")
    attrs = sess.get("attributes") or {}
    import focus
    if kind == "LaunchRequest":
        queued = focus.take_queued()              # an announcement waiting to be spoken (alexa-announce)
        if queued:
            return reply(queued, end=True)
        if focus.pending():
            main = focus.priority()
            return reply(focus.QUESTION + (f" Your main task today is {main}." if main else ""),
                         reprompt="What are you working on?", attrs={"state": "checkin"})
        n = len(inbox_unread())
        if n:
            return reply(f"{NAME} here. You have {n} new update{'s' if n > 1 else ''}. Want to hear {'them' if n > 1 else 'it'}?",
                         reprompt="Shall I read your updates?")
        return reply(f"{NAME} here. What do you need?", reprompt="What do you need?")
    if kind == "SessionEndedRequest":
        SESSIONS.pop(sid, None)
        return {"version": "1.0", "response": {}}
    if kind != "IntentRequest":
        return reply("Sorry, I did not get that.")
    intent = rq.get("intent") or {}
    name = intent.get("name")
    slot = (((intent.get("slots") or {}).get("query") or {}).get("value") or "").strip()
    if name == "SetPriorityIntent" and slot:
        focus.set_priority(slot)
        return reply(f"Got it. Today's main task is {slot}. I will check in with you.")
    if name == "PriorityQueryIntent":
        main = focus.priority()
        return reply(f"Your main task today is {main}." if main else
                     "No main task is set for today. Say: my main task today is, and then the task.")
    if name == "CheckinIntent":
        main = focus.priority()
        return reply(focus.QUESTION + (f" Your main task today is {main}." if main else ""),
                     reprompt="What are you working on?", attrs={"state": "checkin"})
    if attrs.get("state") == "checkin" and slot and name in ("CheckinAnswerIntent", "AskAgentIntent"):
        return checkin_judge(slot)
    if name == "CheckinAnswerIntent" and slot and focus.pending():
        return checkin_judge(slot)
    if name in ("UpdatesIntent", "AMAZON.YesIntent"):
        return read_updates()
    if name in ("AMAZON.StopIntent", "AMAZON.CancelIntent", "AMAZON.NoIntent"):
        SESSIONS.pop(sid, None)
        return reply("Okay. Bye.", end=True)
    if name == "AMAZON.HelpIntent":
        return reply("Ask me anything, like: what's new, check in with me, or my main task today is. "
                     f"Long jobs report on {NOTIFY_NAME}.")
    if name == "AMAZON.FallbackIntent":
        return reply("Sorry, say that again starting with: ask, tell me, or can you.")
    if not slot:
        return reply("What should I do?", reprompt="What should I do?")
    log(f"asked: {slot[:80]}")
    result, done = {}, threading.Event()

    def run():
        try:
            result["text"], result["id"] = agent(slot, SESSIONS.get(sid))
        except Exception as e:  # noqa: BLE001
            result["error"] = str(e)
        done.set()

    threading.Thread(target=run, daemon=True).start()
    if done.wait(SPEAK_WAIT_S):
        if "error" in result:
            log(f"agent error: {result['error']}")
            return reply("Sorry, I could not reach the assistant right now.")
        if result.get("id"):
            SESSIONS[sid] = result["id"]
        return reply(spoken(result.get("text") or "Done."))

    def finish():
        done.wait()
        msg = result.get("text") or f"Sorry, that failed: {result.get('error', 'no answer')}"
        notify(f"From Alexa: \"{slot}\"\n\n{msg}")
        inbox_add(f"About {slot}: {spoken(msg, 280)}")

    threading.Thread(target=finish, daemon=True).start()
    return reply(f"On it. I will send the result to your {NOTIFY_NAME}.", end=True)


class H(BaseHTTPRequestHandler):
    def do_POST(self):
        raw = self.rfile.read(int(self.headers.get("Content-Length", 0) or 0))
        try:
            from ask_sdk_core.serialize import DefaultSerializer
            from ask_sdk_model import RequestEnvelope
            headers = dict(self.headers.items())
            envelope = DefaultSerializer().deserialize(raw.decode(), RequestEnvelope)
            for v in verifiers:
                v.verify(headers=headers, serialized_request_env=raw.decode(), deserialized_request_env=envelope)
            out, code = handle(json.loads(raw)), 200
        except (VerificationException, PermissionError) as e:
            log(f"rejected: {e}")
            out, code = {"error": "forbidden"}, 400
        except Exception as e:  # noqa: BLE001
            log(f"error: {e}")
            out, code = reply("Sorry, something went wrong."), 200
        body = json.dumps(out).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json;charset=UTF-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    log(f"{NAME} skill backend on 127.0.0.1:{PORT}")
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
