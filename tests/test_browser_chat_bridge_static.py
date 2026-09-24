import unittest
from pathlib import Path


class TestBrowserChatBridgeStatic(unittest.TestCase):
    def setUp(self):
        self.text = (
            Path(__file__).resolve().parents[1]
            / "browser_bridge"
            / "extension"
            / "content.js"
        ).read_text(encoding="utf-8")

    def test_chat_output_bridge_exists(self):
        self.assertIn("function publishResultToChat(", self.text)
        self.assertIn("function findChatComposer(", self.text)
        self.assertIn("function setComposerText(", self.text)
        self.assertIn("function submitChatComposer(", self.text)

    def test_mutation_observer_tracks_text_changes(self):
        self.assertIn("characterData: true", self.text)
        self.assertIn("scheduleInspectDocument(", self.text)

    def test_result_is_published_after_direct_action(self):
        self.assertIn("response.resultContainer", self.text)
        self.assertIn("publishResultToChat(", self.text)

    def test_result_is_published_after_confirmation(self):
        self.assertIn("result.resultContainer", self.text)
        self.assertIn("publishResultToChat(", self.text)


if __name__ == "__main__":
    unittest.main()

