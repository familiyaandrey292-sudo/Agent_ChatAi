import time
import unittest

from gateway.confirmation import ConfirmationStore


class TestConfirmationStore(unittest.TestCase):

    def test_create_and_consume(self):
        store = ConfirmationStore(ttl_seconds=120)
        container = "AGX1:A:test-container"

        token = store.create(container)

        self.assertEqual(
            store.consume(token),
            container,
        )

    def test_token_is_one_time(self):
        store = ConfirmationStore(ttl_seconds=120)
        token = store.create("AGX1:A:one-time")

        store.consume(token)

        with self.assertRaises(ValueError):
            store.consume(token)

    def test_cancel_invalidates_token(self):
        store = ConfirmationStore(ttl_seconds=120)
        token = store.create("AGX1:A:cancel-me")

        store.cancel(token)

        with self.assertRaises(ValueError):
            store.consume(token)
    def test_duplicate_container_reuses_pending_token(self):
        store = ConfirmationStore(ttl_seconds=120)
        container = "AGX1:A:duplicate"

        first = store.create(container)
        second = store.create(container)

        self.assertEqual(first, second)

    def test_new_token_is_created_after_cancel(self):
        store = ConfirmationStore(ttl_seconds=120)
        container = "AGX1:A:reuse-after-cancel"

        first = store.create(container)
        store.cancel(first)

        second = store.create(container)

        self.assertNotEqual(first, second)
    def test_invalid_token_is_rejected(self):
        store = ConfirmationStore(ttl_seconds=120)

        with self.assertRaises(ValueError):
            store.consume("invalid-token")

    def test_expired_token_is_rejected(self):
        store = ConfirmationStore(ttl_seconds=1)
        token = store.create("AGX1:A:expires")

        time.sleep(1.1)

        with self.assertRaises(ValueError):
            store.consume(token)


if __name__ == "__main__":
    unittest.main()
