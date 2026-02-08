import logging
import os
import tempfile
import unittest

from logging_config import setup_logging, LOGS_DIR


class TestLoggingConfig(unittest.TestCase):
    def test_setup_logging_creates_rotating_and_stream_handlers(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = f"{tmpdir}/test.log"

            logger = setup_logging(name="test_logger", log_file=log_file)

            self.assertIsInstance(logger, logging.Logger)
            self.assertEqual(logger.name, "test_logger")
            self.assertEqual(len(logger.handlers), 2)

            logger.info("hello")
            for h in logger.handlers:
                h.flush()

            # File exists and is non-empty
            with open(log_file, "r", encoding="utf-8") as f:
                content = f.read()
                self.assertIn("hello", content)

    def test_default_log_goes_to_logs_dir(self):
        """Default log_file should be routed to the project's logs/ directory."""
        logger = setup_logging(name="test_default_dir")
        file_handler = [h for h in logger.handlers if hasattr(h, "baseFilename")][0]
        self.assertIn(os.sep + "logs" + os.sep, file_handler.baseFilename)
        self.assertTrue(file_handler.baseFilename.endswith("wcmkts_app.log"))

    def test_custom_log_file_goes_to_logs_dir(self):
        """A relative log_file name should be placed inside the logs/ directory."""
        logger = setup_logging(name="test_custom_dir", log_file="custom.log")
        file_handler = [h for h in logger.handlers if hasattr(h, "baseFilename")][0]
        expected = os.path.join(LOGS_DIR, "custom.log")
        self.assertEqual(file_handler.baseFilename, expected)

    def test_absolute_path_respected(self):
        """An absolute log_file path should be used as-is, not redirected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            abs_path = os.path.join(tmpdir, "abs_test.log")
            logger = setup_logging(name="test_abs_path", log_file=abs_path)
            file_handler = [h for h in logger.handlers if hasattr(h, "baseFilename")][0]
            self.assertEqual(file_handler.baseFilename, abs_path)

    def test_relative_path_with_dirs_stripped(self):
        """A relative path like 'subdir/foo.log' should be stripped to 'foo.log' in logs/."""
        logger = setup_logging(name="test_strip_dirs", log_file="subdir/foo.log")
        file_handler = [h for h in logger.handlers if hasattr(h, "baseFilename")][0]
        expected = os.path.join(LOGS_DIR, "foo.log")
        self.assertEqual(file_handler.baseFilename, expected)


if __name__ == "__main__":
    unittest.main()
