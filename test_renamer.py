import unittest
from unittest.mock import MagicMock, patch
import os
import renamer_lib as lib

class TestRenamerLib(unittest.TestCase):

    def test_extract_keywords_from_filename(self):
        filename = "My_Project_File.txt"
        keywords = lib.extract_keywords_from_filename(filename)
        self.assertEqual(keywords, ["My", "Project", "File"])

        filename = "report_finance_2023.pdf"
        keywords = lib.extract_keywords_from_filename(filename)
        self.assertEqual(keywords, ["report", "finance"])

    def test_extract_date_from_filename(self):
        # Test common formats
        self.assertEqual(lib.extract_date_from_filename("Report_2023-01-01.pdf"), "20230101")
        self.assertEqual(lib.extract_date_from_filename("Memo_January 15, 2023.docx"), "20230115")

        # Test default (current date) when no date is found
        # We check if it returns a string of 8 digits
        date_str = lib.extract_date_from_filename("No_Date_Here.txt")
        self.assertTrue(date_str.isdigit())
        self.assertEqual(len(date_str), 8)

    def test_smart_fallback_naming(self):
        file_info = {"src_path": "/tmp/test/budget_report.xlsx"}

        # Mock datetime to have a consistent date for fallback
        with patch('renamer_lib.extract_date_from_filename') as mock_date:
            mock_date.return_value = "20231010"

            result = lib.smart_fallback_naming(file_info)

            self.assertEqual(result["src_path"], "/tmp/test/budget_report.xlsx")
            # Expected: Subject_Description_DocType_Date_Rev0.ext
            # Subject: budget
            # Description: Report
            # DocType: DAT (default for xlsx unless application/data in keywords, wait 'report' is keyword)
            # Logic says:
            # if extension in ['.xlsx', ...]:
            #   if 'application' ... -> APP
            #   elif 'data' ... -> DAT
            #   else -> DAT
            # So it should be DAT.

            self.assertEqual(result["new_name"], "budget_Report_DAT_20231010_Rev0.xlsx")

    def test_smart_fallback_naming_word_doc(self):
        file_info = {"src_path": "/tmp/test/meeting_minutes.docx"}

        with patch('renamer_lib.extract_date_from_filename') as mock_date:
            mock_date.return_value = "20231010"
            result = lib.smart_fallback_naming(file_info)

            # Keywords: meeting, minutes
            # Subject: meeting
            # Description: Minutes
            # DocType: DOC (default) - wait, check logic.
            # if extension in [.docx]:
            #   if 'report' -> RPT
            #   elif 'memo' -> MEM
            #   elif 'form' -> FRM
            #   else -> DOC
            # So DOC.

            self.assertEqual(result["new_name"], "meeting_Minutes_DOC_20231010_Rev0.docx")

    @patch('renamer_lib.os.path.exists')
    def test_get_unique_filename(self, mock_exists):
        # Case 1: File does not exist
        mock_exists.return_value = False
        self.assertEqual(lib.get_unique_filename("/dir", "file.txt"), "file.txt")

        # Case 2: File exists once
        # We need side_effect to return True first, then False
        mock_exists.side_effect = [True, False]
        self.assertEqual(lib.get_unique_filename("/dir", "file.txt"), "file_1.txt")

    @patch('renamer_lib.anthropic.Anthropic')
    def test_create_claude_naming_suggestion_success(self, mock_anthropic_cls):
        # Setup mock
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client

        mock_message = MagicMock()
        mock_message.content = [MagicMock(text='```json\n{"subject": "Project", "description": "Plan", "document_form": "PLN", "date": "20230101", "revision": "Rev0", "reasoning": "Test"}\n```')]
        mock_client.messages.create.return_value = mock_message

        file_info = {
            "src_path": "test.txt",
            "content": "some content"
        }

        result = lib.create_claude_naming_suggestion(file_info, "fake-api-key")

        self.assertEqual(result["new_name"], "Project_Plan_PLN_20230101_Rev0.txt")
        self.assertTrue(result["claude_used"])

    @patch('renamer_lib.anthropic.Anthropic')
    def test_create_claude_naming_suggestion_failure(self, mock_anthropic_cls):
        # Setup mock to raise exception
        mock_anthropic_cls.side_effect = Exception("API Error")

        file_info = {
            "src_path": "test.txt",
            "content": "some content"
        }

        # Should fallback to smart naming
        with patch('renamer_lib.smart_fallback_naming') as mock_fallback:
            mock_fallback.return_value = {"new_name": "fallback.txt"}
            result = lib.create_claude_naming_suggestion(file_info, "fake-api-key")
            self.assertEqual(result["new_name"], "fallback.txt")

if __name__ == '__main__':
    unittest.main()
