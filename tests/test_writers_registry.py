import unittest

from src.core.writers_registry import WriterRegistry


class WriterRegistryTests(unittest.TestCase):
    def test_ar_receivable_writer_is_registered(self) -> None:
        registry = WriterRegistry()
        self.assertTrue(registry.has("insert_ar_receivable"))


if __name__ == "__main__":
    unittest.main()
