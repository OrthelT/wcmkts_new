import logging
import tempfile
import unittest

from logging_config import setup_logging


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


if __name__ == "__main__":
    unittest.main()
