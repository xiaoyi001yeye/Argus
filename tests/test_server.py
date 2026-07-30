import unittest
from unittest.mock import Mock, patch

from argus.server import list_log_files


class ListLogFilesToolTest(unittest.TestCase):
    def test_requires_explicit_extract_archives_flag(self) -> None:
        listing = Mock()
        listing.to_dict.return_value = {
            "files": [],
            "requires_extraction_confirmation": False,
        }
        service = Mock()
        service.list_files.return_value = listing

        with patch("argus.server._service", return_value=service):
            result = list_log_files("production", "appserver")

        service.list_files.assert_called_once_with("appserver", extract_archives=False)
        self.assertFalse(result["requires_extraction_confirmation"])

    def test_forwards_confirmed_archive_extraction(self) -> None:
        listing = Mock()
        listing.to_dict.return_value = {
            "files": [],
            "extracted_archives": ["archive.zip"],
        }
        service = Mock()
        service.list_files.return_value = listing

        with patch("argus.server._service", return_value=service):
            result = list_log_files("production", "appserver", extract_archives=True)

        service.list_files.assert_called_once_with("appserver", extract_archives=True)
        self.assertEqual(result["extracted_archives"], ["archive.zip"])


if __name__ == "__main__":
    unittest.main()
