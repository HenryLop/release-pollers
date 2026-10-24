"""python -m pollers run [--config pollers.json] [--send]   one pass (schedule it with cron or Task Scheduler)
python -m pollers status                                   show every poller's state
"""
import argparse
import json
import sys

from pollers import core


def main(argv=None):
    ap = argparse.ArgumentParser(prog="pollers")
    ap.add_argument("cmd", choices=["run", "status"])
    ap.add_argument("--config", default="pollers.json")
    ap.add_argument("--send", action="store_true", help="really send mail (default is a dry run)")
    a = ap.parse_args(argv)
    with open(a.config, encoding="utf-8") as fh:
        pollers = json.load(fh)
    if a.cmd == "run":
        fired = core.run_once(pollers, dry_run=not a.send)
        print("fired: %s" % (", ".join(fired) or "none"))
    else:
        st = core.load_state()
        for p in pollers:
            s = st.get(p["name"], {})
            print("%-14s %-9s checks=%s %s" % (p["name"], "FINISHED" if s.get("finished") else "watching",
                                              s.get("checks", 0), s.get("last_error", "")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
