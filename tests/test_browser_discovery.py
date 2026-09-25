from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "browser_bridge" / "extension"


class TestBrowserDiscoveryStatic(unittest.TestCase):
    def setUp(self):
        self.content_js = (
            EXT / "content.js"
        ).read_text(encoding="utf-8-sig")

        self.popup_html = (
            EXT / "popup.html"
        ).read_text(encoding="utf-8-sig")

        self.popup_js = (
            EXT / "popup.js"
        ).read_text(encoding="utf-8-sig")

    def test_popup_contains_discovery_ui(self):
        for marker in (
            'id="discoveryToggle"',
            'id="discoveryPhrase"',
            'id="copyDiscovery"',
            'id="discoveryState"',
        ):
            self.assertIn(marker, self.popup_html)

        self.assertIn(
            "Покой",
            self.popup_html
        )
        self.assertIn(
            "Слушает",
            self.popup_js
        )

    def test_popup_generates_required_phrase(self):
        self.assertIn(
            "ИИ сколько будет ",
            self.popup_js
        )
        self.assertIn(
            " умножить на ",
            self.popup_js
        )
        self.assertRegex(
            self.popup_js,
            r"Math\.floor\(\s*1000000"
        )
        self.assertIn(
            "copyDiscoveryPhrase",
            self.popup_js
        )

    def test_popup_has_discovery_messages(self):
        for marker in (
            "AGX_CHAT_DISCOVERY_START",
            "AGX_CHAT_DISCOVERY_STOP",
            "AGX_CHAT_DISCOVERY_STATE",
        ):
            self.assertIn(marker, self.popup_js)

    def test_content_has_discovery_protocol(self):
        for marker in (
            "AGX_CHAT_DISCOVERY_START",
            "AGX_CHAT_DISCOVERY_STOP",
            "AGX_CHAT_DISCOVERY_STATE",
            "wait_input",
            "wait_send",
            "wait_message",
            "complete",
        ):
            self.assertIn(marker, self.content_js)

    def test_content_learns_three_targets(self):
        for marker in (
            "composerSelector",
            "sendButtonSelector",
            "messageSelector",
            "getElementSelector",
            "saveChatDiscoveryProfile",
        ):
            self.assertIn(marker, self.content_js)


    def test_content_has_dynamic_dom_fallbacks(self):
        for marker in (
            "composedPath",
            "scanForDiscoveryInput",
            "scheduleDiscoveryPoll",
            "document.body?.innerText || \"\"",
        ):
            self.assertIn(marker, self.content_js)


    def test_content_captures_real_event_target(self):
        for marker in (
            'handleChatDiscoveryInput(event)',
            '"paste"',
            '"focusin"',
        ):
            self.assertIn(marker, self.content_js)

    def test_content_supports_open_shadow_dom_discovery(self):
        for marker in (
            "collectDiscoveryEditables",
            "element.shadowRoot",
        ):
            self.assertIn(marker, self.content_js)

    def test_result_submission_prefers_learned_send_button(self):
        pattern = re.compile(
            r"function\s+findChatSubmitButton\(composer\).*?"
            r"sendButtonSelector",
            re.S,
        )
        self.assertRegex(
            self.content_js,
            pattern
        )


if __name__ == "__main__":
    unittest.main()
