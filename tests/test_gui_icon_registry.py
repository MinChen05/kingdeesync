import unittest

from PySide6.QtGui import QIcon

from src.gui import icon_registry


class GuiIconRegistryTests(unittest.TestCase):
    def test_all_sidebar_pages_have_existing_icons(self) -> None:
        missing_files = []

        for page_id in sorted(icon_registry.PAGE_ICONS):
            source = icon_registry.page_icon_source(page_id)
            if not icon_registry.icon_path(source).exists():
                missing_files.append((page_id, source))

        self.assertEqual(missing_files, [])

    def test_required_icon_files_exist(self) -> None:
        missing = [
            source
            for source in sorted(icon_registry.required_icon_files())
            if not icon_registry.icon_path(source).exists()
        ]

        self.assertEqual(missing, [])

    def test_registered_qicons_are_not_null(self) -> None:
        null_icons = []

        for source in sorted(icon_registry.required_icon_files()):
            icon = icon_registry.qicon(source)
            if not isinstance(icon, QIcon) or icon.isNull():
                null_icons.append(source)

        self.assertEqual(null_icons, [])

    def test_icon_source_normalizes_icons_prefix(self) -> None:
        self.assertEqual(icon_registry.normalize_source("icons/dashboard.svg"), "dashboard.svg")
        self.assertEqual(icon_registry.icon_source("dashboard.svg"), "icons/dashboard.svg")
        self.assertEqual(icon_registry.icon_source("icons/dashboard.svg"), "icons/dashboard.svg")


if __name__ == "__main__":
    unittest.main()
