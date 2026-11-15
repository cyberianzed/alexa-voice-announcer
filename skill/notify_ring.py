"""The Echo's notification ring (Alexa Proactive Events, AMAZON.MessageAlert.Activated: "You have a new message
from Jarvis"). Optional. Needs CLIENT_ID / CLIENT_SECRET (Skill Messaging credentials) in bridge.env and the owner's OK for
notifications in the Alexa app. Until then ring() raises and the update just waits in the inbox."""
import json
import time
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENV = dict(l.split("=", 1) for l in (HERE / "bridge.env").read_text().splitlines() if "=" in l and not l.startswith("#")) if (HERE / "bridge.env").exists() else {}
ENV = {k.strip(): v.strip() for k, v in ENV.items()}
TOKEN = {"value": None, "until": 0}


def token():
    if TOKEN["value"] and time.time() < TOKEN["until"] - 60:
        return TOKEN["value"]
    cid, sec = ENV.get("CLIENT_ID", "").strip(), ENV.get("CLIENT_SECRET", "").strip()
    if not cid or not sec:
        raise RuntimeError("notifications not set up (no CLIENT_ID / CLIENT_SECRET)")
    body = urllib.parse.urlencode({"grant_type": "client_credentials", "client_id": cid, "client_secret": sec,
                                   "scope": "alexa::proactive_events"}).encode()
    with urllib.request.urlopen(urllib.request.Request("https://api.amazon.com/auth/o2/token", data=body), timeout=20) as r:
        d = json.loads(r.read())
    TOKEN.update(value=d["access_token"], until=time.time() + d.get("expires_in", 3600))
    return TOKEN["value"]


def ring(stage=None):
    user = (HERE / "paired_user").read_text().strip()
    now = datetime.now(timezone.utc)
    event = {
        "timestamp": now.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "referenceId": str(uuid.uuid4()),
        "expiryTime": (now + timedelta(hours=23)).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "event": {"name": "AMAZON.MessageAlert.Activated",
                  "payload": {"state": {"status": "UNREAD", "freshness": "NEW"},
                              "messageGroup": {"creator": {"name": ENV.get("ASSISTANT_NAME", "Jarvis")}, "count": 1, "urgency": "URGENT"}}},
        "relevantAudience": {"type": "Unicast", "payload": {"user": user}},
    }
    stage = stage or ENV.get("NOTIFY_STAGE", "development")
    url = f"https://api.amazonalexa.com/v1/proactiveEvents/{'stages/development' if stage == 'development' else ''}".rstrip("/")
    req = urllib.request.Request(url, data=json.dumps(event).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {token()}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.status
