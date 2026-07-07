import unittest

from src.core.sales_writer import insert_purchase_instock
from src.core.writers_registry import WriterRegistry


class WriterRegistryTests(unittest.TestCase):
    def test_ar_receivable_writer_is_registered(self) -> None:
        registry = WriterRegistry()
        self.assertTrue(registry.has("insert_ar_receivable"))

    def test_purchase_instock_writer_is_registered(self) -> None:
        registry = WriterRegistry()
        self.assertTrue(registry.has("insert_purchase_instock"))
        self.assertIs(registry.get("insert_purchase_instock"), insert_purchase_instock)


if __name__ == "__main__":
    unittest.main()
