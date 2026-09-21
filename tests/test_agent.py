import tempfile
import unittest
from pathlib import Path

from pc_agent.agent import (
    ComponentNotFoundError,
    InvalidArgumentsError,
    PCAgent,
    UnsupportedActionError,
)


class TestPCAgent(unittest.TestCase):

    def setUp(self):
        self.agent = PCAgent()

    def test_system_info(self):
        result = self.agent.execute("system.info")

        self.assertTrue(result.success)
        self.assertEqual(result.action, "system.info")
        self.assertEqual(result.result["system"], "Windows")
        self.assertIn("python", result.result)

    def test_list_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir)
            (path / "file1.txt").write_text("test", encoding="utf-8")
            (path / "folder").mkdir()

            result = self.agent.execute(
                "files.list",
                {"path": str(path)},
            )

            self.assertTrue(result.success)
            self.assertEqual(result.action, "files.list")

            names = {entry["name"] for entry in result.result["entries"]}
            self.assertEqual(names, {"file1.txt", "folder"})

    def test_list_files_requires_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "test.txt"
            file_path.write_text("test", encoding="utf-8")

            with self.assertRaises(InvalidArgumentsError):
                self.agent.execute(
                    "files.list",
                    {"path": str(file_path)},
                )

    def test_unknown_action(self):
        with self.assertRaises(UnsupportedActionError):
            self.agent.execute("something.unknown")

    def test_missing_executable(self):
        with self.assertRaises(ComponentNotFoundError):
            self.agent.execute(
                "app.open",
                {"name": "definitely_missing_agent_chat_ai_test.exe"},
            )


if __name__ == "__main__":
    unittest.main()
