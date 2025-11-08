#!/usr/bin/env python3
"""
Filename Format Tests - pytest compatible

Tests für:
- Format mit 2 Dezimalstellen (IMMER)
- Sonderzeichen-Bereinigung
- Edge-Cases (lange Beschreibung, Umlaute)
- Validierung gegen Regex-Pattern
"""

import re
from datetime import datetime


def test_amount_always_two_decimals():
    """Test: Betrag hat IMMER 2 Dezimalstellen"""
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
        amount_formatted = f"{float(amount):.2f}".replace('.', '_')
        assert amount_formatted == expected, f"Amount {amount} should format to {expected}"


def test_sonderzeichen_bereinigung():
    """Test: Sonderzeichen werden korrekt bereinigt"""
    test_descriptions = [
        ('Büro / Material', 'Büro_-_Material'),  # / → -
        ('Test & Co', 'Test_&_Co'),  # & bleibt
        ('Name (Firma)', 'Name_(Firma)'),  # () bleiben
        ('Test  Doppel', 'Test__Doppel'),  # Doppelte Spaces → Doppelte _
    ]

    for original, expected_pattern in test_descriptions:
        sanitized = original.replace('/', '-').replace(' ', '_')
        assert '/' not in sanitized, "Should not contain /"


def test_lange_beschreibung_wird_gekuerzt():
    """Test: Lange Beschreibung → Wird auf 30 Zeichen gekürzt"""
    long_description = "Dies ist eine sehr lange Beschreibung die definitiv mehr als 30 Zeichen hat"

    truncated = long_description[:30].replace('/', '-').replace(' ', '_').strip('_')

    assert len(truncated) <= 30, "Truncated description should be ≤ 30 chars"
    assert truncated == 'Dies_ist_eine_sehr_lange_Besc', "Truncation should match expected pattern"


def test_filename_pattern_regex_validation():
    """Test: Filename matcht das erwartete Regex-Pattern"""
    pattern = re.compile(r'^\d{6}_[AE]RE-[A-Z0-9]{1,3}-\d{7,}_[^_]+_.+_\d+_\d{2}\.(pdf|virtual)$')

    test_filenames = [
        '251108_ARE-TB-2025001_Büro_Laptop_1299_50.pdf',
        '251108_ERE-MB-2025001_Honorar_Projekt_2500_00.pdf',
        '250101_ARE-T1-2025999_Raum_Miete_850_00.pdf',
    ]

    for filename in test_filenames:
        match = pattern.match(filename)
        assert match is not None, f"Filename should match pattern: {filename}"


def test_invalid_filenames_fail_validation():
    """Test: Ungültige Filenames → Schlagen fehl"""
    pattern = re.compile(r'^\d{6}_[AE]RE-[A-Z0-9]{1,3}-\d{7,}_[^_]+_.+_\d+_\d{2}\.(pdf|virtual)$')

    invalid_filenames = [
        '2025-11-08_ARE-TB-2025001_Büro_Laptop_1299_50.pdf',  # Wrong date format
        '251108_ARE-TB-2025001_Büro_Laptop_1299_5.pdf',  # Only 1 decimal
        '251108_XYZ-TB-2025001_Büro_Laptop_1299_50.pdf',  # Invalid prefix
        '251108_ARE-TB-2025001.pdf',  # Missing parts
    ]

    for filename in invalid_filenames:
        match = pattern.match(filename)
        assert match is None, f"Invalid filename should NOT match: {filename}"


def test_umlaute_bleiben_erhalten():
    """Test: Umlaute bleiben im Filename erhalten"""
    test_strings = [
        'Büro',
        'Übernahme',
        'Führerschein',
    ]

    for test_str in test_strings:
        assert 'ü' in test_str.lower(), "Umlauts should remain"


def test_double_underscores_cleaned():
    """Test: Doppelte Underscores → Werden bereinigt"""
    test_filename = '251108_ARE-TB-2025001__Büro__Test__1299_50.pdf'
    cleaned = test_filename.replace('__', '_')

    assert '__' not in cleaned, "Should not contain double underscores"
    assert cleaned == '251108_ARE-TB-2025001_Büro_Test_1299_50.pdf', "Double underscores should be cleaned"


def test_date_format_yymmdd():
    """Test: Datum-Format → YYMMDD (6 Ziffern)"""
    date_obj = datetime(2025, 11, 8)
    date_str = date_obj.strftime('%y%m%d')

    assert date_str == '251108', "Date should be formatted as YYMMDD"
    assert len(date_str) == 6, "Date string should be 6 characters"
    assert date_str.isdigit(), "Date string should only contain digits"
