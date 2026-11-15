"""Speaking out loud, today's main task and accountability check-ins.

    python focus.py say "Lunch is ready"          speak it now on the Echo / Alexa app (announcer, else Voice Monkey)
    python focus.py priority "Finish the report"  set today's main task
    python focus.py show                          today's main task
    python focus.py checkin                       ask "what are you working on?" (notify + open the skill, which asks
                                                  and listens for the spoken answer); fixed text, no AI
    python focus.py log "<what I am working on>"  record an answer
"""
import json
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
TODAY = HERE / "today.json"        # {"date": "2026-01-31", "task": "..."}
PENDING = HERE / "checkin.json"    # {"at": epoch, "answered": false}
ANSWERS = HERE / "checkins.jsonl"  # one line per answer
SPEAK = HERE / "speak.json"        # {"at": epoch, "text": "..."}: spoken by the skill when the announcer opens it
QUESTION = "Check-in: what are you working on right now? Is it today's main task?"


def env():
    out = {}
    if (HERE / "bridge.env").exists():
        for line in (HERE / "bridge.env").read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip()
    return out


TZ = ZoneInfo(env().get("TIMEZONE", "UTC"))


def today():
    return datetime.now(TZ).strftime("%Y-%m-%d")


def priority():
    try:
        d = json.loads(TODAY.read_text(encoding="utf-8"))
        return d["task"] if d.get("date") == today() else ""
    except (OSError, ValueError, KeyError):
        return ""


def set_priority(task):
    TODAY.write_text(json.dumps({"date": today(), "task": task.strip()}), encoding="utf-8")


def pending():
    """The check-in waiting for an answer (asked in the last 4 hours), else None."""
    try:
        d = json.loads(PENDING.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return d if not d.get("answered") and time.time() - d.get("at", 0) < 4 * 3600 else None


def log_answer(answer, verdict=""):
    PENDING.write_text(json.dumps({"at": time.time(), "answered": True}), encoding="utf-8")
    with open(ANSWERS, "a", encoding="utf-8") as f:
        f.write(json.dumps({"at": datetime.now(TZ).isoformat(timespec="minutes"), "main_task": priority(),
                            "answer": answer, "verdict": verdict}) + "\n")


def take_queued(max_age=180):
    """The queued announcement for the skill to speak (once), if it is fresh."""
    try:
        q = json.loads(SPEAK.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    SPEAK.unlink(missing_ok=True)
    return q.get("text", "") if time.time() - q.get("at", 0) < max_age else ""


def own_announce(text=None):
    """Free, unlimited: queue the text, then ask the announcer to open the skill on the device; the skill speaks it.
    text=None only opens the skill (e.g. for a pending check-in, which it then asks and listens for)."""
    if text:
        SPEAK.write_text(json.dumps({"at": time.time(), "text": text}), encoding="utf-8")
    url = env().get("ANNOUNCER_URL", "http://127.0.0.1:8095") + "/speak"
    req = urllib.request.Request(url, data=json.dumps({"mode": "launch"}).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return json.loads(r.read() or b"{}").get("ok") is True
    except Exception:  # noqa: BLE001
        return False


def voicemonkey(text):
    """Optional backup: Voice Monkey (VOICEMONKEY_TOKEN, VOICEMONKEY_DEVICE in bridge.env)."""
    e = env()
    tok, dev = e.get("VOICEMONKEY_TOKEN", ""), e.get("VOICEMONKEY_DEVICE", "")
    if not tok or not dev:
        return False
    url = "https://api-v3.voicemonkey.io/announce?" + urllib.parse.urlencode({"token": tok, "device": dev, "speech": text})
    with urllib.request.urlopen(url, timeout=20) as r:
        return r.status == 200


def announce(text):
    """Speak on the Echo / Alexa app now: own announcer first, Voice Monkey only as the backup."""
    if own_announce(text):
        return True
    SPEAK.unlink(missing_ok=True)
    return voicemonkey(text)


def notify(text):
    cmd = env().get("NOTIFY_CMD", "")
    if cmd:
        subprocess.run(["bash", "-lc", cmd], input=text.encode(), timeout=120)


def checkin():
    PENDING.write_text(json.dumps({"at": time.time(), "answered": False}), encoding="utf-8")
    main = priority()
    notify(QUESTION + (f"\nToday's main task: {main}" if main else
                       "\nNo main task set for today yet. Reply with: today's main task is ..."))
    try:
        if not own_announce():   # opens the skill, which asks the question and waits for the spoken answer
            voicemonkey("Check-in. What are you working on right now? Say: Alexa, open Jarvis.")
    except Exception as e:  # noqa: BLE001
        print(f"no announcement: {e}")
    print("check-in sent")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["say"] and len(a) > 1:
        print("announced" if announce(" ".join(a[1:])) else "not announced: announcer not ready and no Voice Monkey backup")
    elif a[:1] == ["priority"] and len(a) > 1:
        set_priority(" ".join(a[1:]))
        print(f"today's main task: {priority()}")
    elif a[:1] == ["show"]:
        print(priority() or "(no main task set for today)")
    elif a[:1] == ["checkin"]:
        checkin()
    elif a[:1] == ["log"] and len(a) > 1:
        log_answer(" ".join(a[1:]))
        print("logged")
    else:
        print(__doc__)
