"""Single-purpose pollers. Each one watches ONE thing, notifies ONCE, then finishes.

pollers.json:
  [{"name": "docs-v2", "url": "http://...", "kind": "contains", "pattern": "Version 2",
    "subject": "Docs v2 is live"}]

kind: contains (text appears) | absent (text disappears) | regex (pattern matches) | changed (page hash differs from first seen)
"""
import hashlib
import json
import os
import re
import smtplib
import ssl
import urllib.request
from email.message import EmailMessage

STATE = os.environ.get("POLLERS_STATE", "pollers-state.json")


def load_state():
    try:
        with open(STATE, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def save_state(s):
    with open(STATE, "w", encoding="utf-8") as fh:
        json.dump(s, fh, indent=1)


def fetch(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": "release-pollers/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def evaluate(poller, text, state):
    """-> (fired: bool, detail: str). 'changed' records its baseline in state."""
    kind, pat = poller.get("kind", "contains"), poller.get("pattern", "")
    if kind == "contains":
        return pat in text, "found %r" % pat
    if kind == "absent":
        return pat not in text, "%r is gone" % pat
    if kind == "regex":
        m = re.search(pat, text)
        return bool(m), "matched %r" % (m.group(0) if m else pat)
    if kind == "changed":
        h = hashlib.sha256(text.encode()).hexdigest()
        base = state.setdefault("baseline", h)
        return h != base, "page content changed"
    raise ValueError("unknown kind: %s" % kind)


def build_email(poller, detail, sender, to):
    m = EmailMessage()
    m["Subject"], m["From"], m["To"] = poller.get("subject") or "%s fired" % poller["name"], sender, to
    m.set_content("%s\n\n%s\n%s\n\nThis poller is now finished and will not send again." % (poller["name"], detail, poller["url"]))
    return m


def send(msg, dry_run=True):
    if dry_run:
        print("[dry run] would send to %s: %s" % (msg["To"], msg["Subject"]))
        return
    host, port = os.environ["SMTP_HOST"], int(os.environ.get("SMTP_PORT", "465"))
    with smtplib.SMTP_SSL(host, port, context=ssl.create_default_context()) as s:
        s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
        s.send_message(msg)


def run_once(pollers, dry_run=True, fetcher=fetch, sender=None, to=None):
    """One pass over every unfinished poller. Returns the names that fired."""
    state = load_state()
    fired = []
    for p in pollers:
        st = state.setdefault(p["name"], {})
        if st.get("finished"):
            continue
        try:
            text = fetcher(p["url"])
        except Exception as e:  # network trouble is not a result; try again next pass
            st["last_error"] = str(e)[:200]
            continue
        st.pop("last_error", None)
        ok, detail = evaluate(p, text, st)
        st["checks"] = st.get("checks", 0) + 1
        if ok:
            send(build_email(p, detail, sender or os.environ.get("MAIL_FROM", "pollers@example.com"),
                             to or os.environ.get("MAIL_TO", "you@example.com")), dry_run)
            st["finished"] = True
            fired.append(p["name"])
    save_state(state)
    return fired
