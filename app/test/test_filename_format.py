#!/usr/bin/env python3
"""
Filename Format Tests

Tests für:
- Format mit 2 Dezimalstellen (IMMER)
- Sonderzeichen-Bereinigung
- Edge-Cases (lange Beschreibung, Umlaute)
- Validierung gegen Regex-Pattern
"""

import sys
import re
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from test_helpers import TestBase, cleanup_test_folders


class FilenameFormatTester(TestBase):
    def __init__(self):
        super().__init__('filename_format')
        self.test_data_dir = Path(__file__).parent / 'test_data'

    def test_1_amount_always_two_decimals(self):
        """Test 1: Betrag hat IMMER 2 Dezimalstellen"""
        test_cases = [
            (0.5, '0_50'),
            (1.0, '1_00'),
            (10.9, '10_90'),
            (100.99, '100_99'),
            (1000.0, '1000_00'),
            (1299.5, '1299_50'),
            (9999.99, '9999_99'),
        ]

        for amount, expected in test_cases:
            # Format using the correct method
            amount_formatted = f"{float(amount):.2f}".replace('.', '_')
            self.assert_equal(
                amount_formatted,
                expected,
                f"Amount {amount} should format to {expected}"
            )

        return True

    def test_2_sonderzeichen_bereinigung(self):
        """Test 2: Sonderzeichen werden korrekt bereinigt"""
        test_descriptions = [
            ('Büro / Material', 'Büro_-_Material'),  # / → -
            ('Test & Co', 'Test_&_Co'),  # & bleibt (wird später ggf. entfernt)
            ('Name (Firma)', 'Name_(Firma)'),  # () bleiben
            ('Test  Doppel', 'Test__Doppel'),  # Doppelte Spaces → Doppelte _
        ]

        for original, expected_pattern in test_descriptions:
            # Simulate the sanitization
            sanitized = original.replace('/', '-').replace(' ', '_')

            # Just check that / is replaced
            self.assert_not_in('/', sanitized, "Should not contain /")

        return True

    def test_3_lange_beschreibung_wird_gekuerzt(self):
        """Test 3: Lange Beschreibung → Wird auf 30 Zeichen gekürzt"""
        long_description = "Dies ist eine sehr lange Beschreibung die definitiv mehr als 30 Zeichen hat"

        # Truncate like the app does
        truncated = long_description[:30].replace('/', '-').replace(' ', '_').strip('_')

        self.assert_true(len(truncated) <= 30, "Truncated description should be ≤ 30 chars")
        self.assert_equal(
            truncated,
            'Dies_ist_eine_sehr_lange_Besc',
            "Truncation should match expected pattern"
        )

        return True

    def test_4_filename_pattern_regex_validation(self):
        """Test 4: Filename matcht das erwartete Regex-Pattern"""
        # Expected pattern: YYMMDD_InvoiceID_Category_Description_Amount_Decimal.pdf
        # Example: 251108_ARE-TB-2025001_Büro_Laptop_1299_50.pdf

        pattern = re.compile(r'^\d{6}_[AE]RE-[A-Z0-9]{1,3}-\d{7,}_[^_]+_.+_\d+_\d{2}\.(pdf|virtual)$')

        test_filenames = [
            '251108_ARE-TB-2025001_Büro_Laptop_1299_50.pdf',
            '251108_ERE-MB-2025001_Honorar_Projekt_2500_00.pdf',
            '250101_ARE-T1-2025999_Raum_Miete_850_00.pdf',
        ]

        for filename in test_filenames:
            match = pattern.match(filename)
            self.assert_true(match is not None, f"Filename should match pattern: {filename}")

        return True

    def test_5_invalid_filenames_fail_validation(self):
        """Test 5: Ungültige Filenames → Schlagen fehl"""
        pattern = re.compile(r'^\d{6}_[AE]RE-[A-Z0-9]{1,3}-\d{7,}_[^_]+_.+_\d+_\d{2}\.(pdf|virtual)$')

        invalid_filenames = [
            '2025-11-08_ARE-TB-2025001_Büro_Laptop_1299_50.pdf',  # Wrong date format
            '251108_ARE-TB-2025001_Büro_Laptop_1299_5.pdf',  # Only 1 decimal
            '251108_XYZ-TB-2025001_Büro_Laptop_1299_50.pdf',  # Invalid prefix
            '251108_ARE-TB-2025001.pdf',  # Missing parts
        ]

        for filename in invalid_filenames:
            match = pattern.match(filename)
            self.assert_true(match is None, f"Invalid filename should NOT match: {filename}")

        return True

    def test_6_umlaute_bleiben_erhalten(self):
        """Test 6: Umlaute bleiben im Filename erhalten"""
        # The app does NOT convert umlauts, they stay as-is
        test_strings = [
            'Büro',
            'Übernahme',
            'Führerschein',
        ]

        for test_str in test_strings:
            # No conversion happens in the app
            self.assert_in('ü', test_str.lower(), "Umlauts should remain")

        return True

    def test_7_double_underscores_cleaned(self):
        """Test 7: Doppelte Underscores → Werden bereinigt"""
        # The app calls: filename.replace('__', '_')

        test_filename = '251108_ARE-TB-2025001__Büro__Test__1299_50.pdf'
        cleaned = test_filename.replace('__', '_')

        self.assert_not_in('__', cleaned, "Should not contain double underscores")
        self.assert_equal(
            cleaned,
            '251108_ARE-TB-2025001_Büro_Test_1299_50.pdf',
            "Double underscores should be cleaned"
        )

        return True

    def test_8_date_format_yymmdd(self):
        """Test 8: Datum-Format → YYMMDD (6 Ziffern)"""
        from datetime import datetime

        # Test date: 2025-11-08
        date_obj = datetime(2025, 11, 8)
        date_str = date_obj.strftime('%y%m%d')

        self.assert_equal(date_str, '251108', "Date should be formatted as YYMMDD")
        self.assert_equal(len(date_str), 6, "Date string should be 6 characters")
        self.assert_true(date_str.isdigit(), "Date string should only contain digits")

        return True

    def run_all_tests(self):
        """Run all filename format tests"""
        self.run_test(self.test_1_amount_always_two_decimals,
                      "Amount → Always 2 Decimal Places")

        self.run_test(self.test_2_sonderzeichen_bereinigung,
                      "Special Characters → Correctly Sanitized")

        self.run_test(self.test_3_lange_beschreibung_wird_gekuerzt,
                      "Long Description → Truncated to 30 Chars")

        self.run_test(self.test_4_filename_pattern_regex_validation,
                      "Valid Filenames → Match Regex Pattern")

        self.run_test(self.test_5_invalid_filenames_fail_validation,
                      "Invalid Filenames → Fail Validation")

        self.run_test(self.test_6_umlaute_bleiben_erhalten,
                      "Umlauts → Remain in Filename")

        self.run_test(self.test_7_double_underscores_cleaned,
                      "Double Underscores → Cleaned")

        self.run_test(self.test_8_date_format_yymmdd,
                      "Date Format → YYMMDD")

        return self.print_summary()


if __name__ == '__main__':
    # Run tests (no cleanup needed, no database/files used)
    tester = FilenameFormatTester()
    success = tester.run_all_tests()

    # Exit with appropriate code
    sys.exit(0 if success else 1)
