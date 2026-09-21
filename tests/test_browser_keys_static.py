from pathlib import Path
import unittest


class TestBrowserKeysStatic(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.source = Path(
            "browser_bridge",
            "extension",
            "browser_keys.js",
        ).read_text(
            encoding="utf-8"
        )

    def test_private_key_generation_is_non_extractable(self):
        self.assertIn(
            "false,",
            self.source,
        )

        self.assertIn(
            '["sign", "verify"]',
            self.source,
        )

    def test_private_key_is_never_exported(self):
        self.assertNotIn(
            "privateJwk",
            self.source,
        )

        self.assertNotIn(
            '"jwk"',
            self.source,
        )

        self.assertNotIn(
            "keyPair.privateKey",
            self.source.split(
                'const identity = {',
                1,
            )[0],
        )

    def test_public_key_export_remains_present(self):
        self.assertIn(
            '"spki"',
            self.source,
        )

        self.assertIn(
            "keyPair.publicKey",
            self.source,
        )


if __name__ == "__main__":
    unittest.main()
