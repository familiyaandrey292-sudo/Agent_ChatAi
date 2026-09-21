from pathlib import Path
import unittest


class TestBrowserCancelStatic(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.source = Path(
            "browser_bridge",
            "extension",
            "content.js",
        ).read_text(
            encoding="utf-8"
        )

    def test_cancel_button_sends_cancel_message(self):
        self.assertIn(
            'type: "AGX_CANCEL_ACTION"',
            self.source,
        )

        self.assertIn(
            "confirmationToken",
            self.source,
        )

    def test_cancel_success_clears_confirmation_ui(self):
        self.assertIn(
            "agentChataiConfirmationCancelled",
            self.source,
        )

        self.assertIn(
            "removeConfirmationBar();",
            self.source,
        )


if __name__ == "__main__":
    unittest.main()
