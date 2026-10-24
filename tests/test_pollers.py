import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pollers import core  # noqa: E402


class Pages:
    def __init__(self, *pages):
        self.pages, self.calls = list(pages), 0

    def __call__(self, url):
        self.calls += 1
        p = self.pages[min(self.calls - 1, len(self.pages) - 1)]
        if isinstance(p, Exception):
            raise p
        return p


class Tests(unittest.TestCase):
    def setUp(self):
        core.STATE = os.path.join(tempfile.mkdtemp(prefix="pollers-test-"), "state.json")

    def run_n(self, poller, fetcher, n):
        return [core.run_once([poller], True, fetcher) for _ in range(n)]

    def test_contains_fires_once_then_finishes(self):
        f = Pages("v1", "v1", "Version 2")
        out = self.run_n({"name": "a", "url": "u", "kind": "contains", "pattern": "Version 2"}, f, 5)
        self.assertEqual(out, [[], [], ["a"], [], []])
        self.assertEqual(f.calls, 3)  # no requests after finishing

    def test_absent(self):
        out = self.run_n({"name": "a", "url": "u", "kind": "absent", "pattern": "Sold out"}, Pages("Sold out", "In stock"), 2)
        self.assertEqual(out, [[], ["a"]])

    def test_regex(self):
        out = self.run_n({"name": "a", "url": "u", "kind": "regex", "pattern": r"v\d+\.\d+\.\d+"}, Pages("none", "tag v3.1.4"), 2)
        self.assertEqual(out, [[], ["a"]])

    def test_changed_uses_first_page_as_baseline(self):
        out = self.run_n({"name": "a", "url": "u", "kind": "changed"}, Pages("one", "one", "two"), 3)
        self.assertEqual(out, [[], [], ["a"]])

    def test_network_error_is_not_a_result(self):
        f = Pages(OSError("down"), "Version 2")
        out = self.run_n({"name": "a", "url": "u", "kind": "contains", "pattern": "Version 2"}, f, 2)
        self.assertEqual(out, [[], ["a"]])

    def test_pollers_are_independent(self):
        ps = [{"name": "a", "url": "u", "kind": "contains", "pattern": "X"},
              {"name": "b", "url": "u", "kind": "contains", "pattern": "Y"}]
        self.assertEqual(core.run_once(ps, True, Pages("X")), ["a"])
        self.assertEqual(core.run_once(ps, True, Pages("XY")), ["b"])

    def test_email_content(self):
        m = core.build_email({"name": "a", "url": "http://x", "subject": "Hi"}, "found 'X'", "a@example.com", "b@example.com")
        self.assertEqual(m["Subject"], "Hi")
        self.assertIn("will not send again", m.get_content())


if __name__ == "__main__":
    unittest.main()
