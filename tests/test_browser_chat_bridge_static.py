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

    def test_command_container_is_detected_and_forwarded(self):
        self.assertIn("AGX_COMMAND_PATTERN", self.text)
        self.assertIn("extractCommandContainers(", self.text)
        self.assertIn('"AGX_COMMAND_DETECTED"', self.text)
        self.assertIn("containers: [container]", self.text)

    def test_command_result_is_auto_submitted(self):
        self.assertIn('resultContainer.startsWith("AGX1:R:")', self.text)
        self.assertIn("submitPublishedResultWhenReady(", self.text)
        self.assertIn("submitChatComposer(composer)", self.text)
        self.assertIn("agentChataiChatOutput", self.text)
        self.assertIn('"submitted"', self.text)

    def test_published_result_is_not_reprocessed_as_duplicate(self):
        self.assertIn("lastPublishedResult", self.text)
        self.assertIn("resultContainer === lastPublishedResult", self.text)
        self.assertIn("lastPublishedResult = resultContainer", self.text)

    def test_bridge_generated_composer_has_reprocessing_guard(self):
        self.assertIn("bridgeGeneratedComposer", self.text)
        self.assertIn("bridgeOwnsComposerText(", self.text)
        self.assertIn("markBridgeGeneratedComposer(", self.text)
        self.assertIn("clearBridgeGeneratedComposer(", self.text)

    def test_near_miss_command_is_surfaced_not_silently_ignored(self):
        self.assertIn("AGX_COMMAND_NEAR_MISS_PATTERN", self.text)
        self.assertIn("function reportNearMissCommands(", self.text)
        self.assertIn("reportNearMissCommands(text)", self.text)
        self.assertIn("agentChataiNearMiss", self.text)
        # near-miss detection must not fire on valid containers:
        # the short-hex {1,63} alternative is terminated by \b and the
        # strict pattern consumes full 64-hex tags first.
        self.assertIn("[A-Fa-f0-9]{1,63}\\b", self.text)

    def test_near_miss_diagnosis_names_contract_fields(self):
        self.assertIn("function describeNearMissCommand(", self.text)
        for field in (
            "session_id",
            "message_id",
            "timestamp",
            "ttl",
        ):
            self.assertIn(field, self.text)
        self.assertIn("integrity-тег", self.text)


if __name__ == "__main__":
    unittest.main()
