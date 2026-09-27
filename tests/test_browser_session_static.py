import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TestBrowserSessionStatic(unittest.TestCase):
    def test_browser_key_has_persistent_session_id(self):
        text = (
            ROOT / "browser_bridge" / "extension" / "browser_keys.js"
        ).read_text(encoding="utf-8")
        self.assertIn("sessionId", text)
        self.assertIn("newSessionId", text)
        self.assertIn("getSessionId", text)

    def test_popup_exposes_copy_session_id(self):
        html = (
            ROOT / "browser_bridge" / "extension" / "popup.html"
        ).read_text(encoding="utf-8")
        js = (
            ROOT / "browser_bridge" / "extension" / "popup.js"
        ).read_text(encoding="utf-8")
        self.assertIn('id="sessionId"', html)
        self.assertIn('id="copySessionId"', html)
        self.assertIn("copySessionId()", js)
        self.assertIn("getSessionId()", js)


if __name__ == "__main__":
    unittest.main()
