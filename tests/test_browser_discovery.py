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


    def test_popup_computes_expected_result(self):
        for marker in (
            "BigInt(x)",
            "BigInt(y)",
            "currentDiscoveryResult",
            "expectedResult:",
        ):
            self.assertIn(marker, self.popup_js)

    def test_content_requires_expected_result(self):
        for marker in (
            "missing_expected_result",
            "chatDiscovery.expectedResult",
            "normalizeDiscoveryNumber",
            "findDiscoveryResultElement",
        ):
            self.assertIn(marker, self.content_js)

    def test_content_does_not_search_original_phrase_for_answer(self):
        start = self.content_js.index(
            "function runChatDiscoveryScan"
        )
        end = self.content_js.index(
            "function startChatDiscovery",
            start
        )
        scan = self.content_js[start:end]

        self.assertIn(
            "chatDiscovery.expectedResult",
            scan
        )
        self.assertNotIn(
            "findDiscoveryRenderedText",
            scan
        )


    def test_content_captures_generic_send_control_from_event_path(self):
        for marker in (
            "getTrustedUserActionTarget",
            "event?.isTrusted !== true",
            '"pointerup"',
            "event.composedPath?.()",
        ):
            self.assertIn(marker, self.content_js)


    def test_discovery_uses_trusted_user_action(self):
        start = self.content_js.index(
            "function getTrustedUserActionTarget"
        )
        end = self.content_js.index(
            "function findDiscoveryRenderedText",
            start
        )
        helper = self.content_js[start:end]

        for marker in (
            "event?.isTrusted !== true",
            "event.composedPath?.()",
            "button, [role=\"button\"], input[type=\"submit\"]",
            'typeof item.click === "function"',
        ):
            self.assertIn(marker, helper)

        self.assertNotIn(
            "composer.contains(item)",
            helper
        )
        self.assertIn(
            "item === composer",
            helper
        )


    def test_discovery_does_not_filter_send_control_state(self):
        start = self.content_js.index(
            "function handleChatDiscoveryClick"
        )
        end = self.content_js.index(
            "function extractActionContainers",
            start
        )
        handler = self.content_js[start:end]

        self.assertNotIn(
            "isDiscoverySendButton",
            handler
        )
        self.assertIn(
            "event",
            handler
        )

    def test_discovery_has_trace_instrumentation(self):
        for marker in (
            "CHAT_DISCOVERY_TRACE_LIMIT",
            "discoveryTrace(",
            "discoveryTraceEventPath",
            '"input_event"',
            '"user_action_event"',
            '"user_action_ignored"',
            '"send_control_captured"',
            '"pre_send_snapshot"',
            '"result_found"',
            '"pointerdown"',
            '"pointerup"',
            '"click"',
        ):
            self.assertIn(
                marker,
                self.content_js
            )

        self.assertIn(
            "copyDiscoveryDiagnostics",
            self.popup_html
        )
        self.assertIn(
            "copyDiscoveryDiagnosticsText",
            self.popup_js
        )

    def test_discovery_state_reports_trace(self):
        self.assertIn(
            "traceStartedAt",
            self.content_js
        )
        self.assertIn(
            "traceCount",
            self.content_js
        )
        self.assertIn(
            "trace:",
            self.content_js
        )

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
