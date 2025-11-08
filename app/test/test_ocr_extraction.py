"""
Test suite for OCR extraction functions
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ocr_processor import OCRProcessor
from income_processor import IncomeProcessor


def test_amount_extraction():
    """Test German number format amount extraction"""
    processor = OCRProcessor(use_llm=False)

    test_cases = [
        # (input_text, expected_amount)
        ("Brutto: 1.299,99 €", 1299.99),
        ("€ 1.299,99", 1299.99),
        ("29,99 EUR", 29.99),
        ("Gesamt 99,00€", 99.00),
        ("Betrag: 1.234.567,89 €", 1234567.89),
        ("Total: 12,50 €", 12.50),
        ("Amount: 999,99€", 999.99),
        ("Summe 1.000,00 EUR", 1000.00),
    ]

    passed = 0
    failed = 0

    print("\n=== AMOUNT EXTRACTION TESTS ===")
    for text, expected in test_cases:
        result = processor._extract_amount(text)
        if result == expected:
            print(f"✓ PASS: '{text}' -> {result}")
            passed += 1
        else:
            print(f"✗ FAIL: '{text}' -> {result} (expected: {expected})")
            failed += 1

    print(f"\nResults: {passed} passed, {failed} failed")
    return failed == 0


def test_date_extraction():
    """Test date extraction"""
    processor = OCRProcessor(use_llm=False)

    test_cases = [
        ("Rechnungsdatum: 01.11.2025", "2025-11-01"),
        ("Datum: 15.12.2024", "2024-12-15"),
        ("Invoice Date: 31.01.2025", "2025-01-31"),
        ("Date: 2025-03-15", "2025-03-15"),
    ]

    passed = 0
    failed = 0

    print("\n=== DATE EXTRACTION TESTS ===")
    for text, expected in test_cases:
        result = processor._extract_date(text)
        if result == expected:
            print(f"✓ PASS: '{text}' -> {result}")
            passed += 1
        else:
            print(f"✗ FAIL: '{text}' -> {result} (expected: {expected})")
            failed += 1

    print(f"\nResults: {passed} passed, {failed} failed")
    return failed == 0


def test_category_prediction():
    """Test category prediction"""
    processor = OCRProcessor(use_llm=False)

    test_cases = [
        ("MacBook Pro 14 Zoll Laptop", "Büro"),
        ("Adobe Creative Cloud Lizenz", "Büro"),
        ("Miete Studio Berlin", "Raum"),
        ("Telekom Rechnung Mobilfunk", "Telefon"),
        ("DB Ticket München-Berlin", "Fahrtkosten"),
        ("Udemy Kurs Python", "Fortbildung"),
        ("Haftpflichtversicherung", "Versicherung"),
        ("DHL Paket Versand", "Porto"),
        ("Google Ads Kampagne", "Werbung"),
        ("Sonstiger Beleg", "Sonstiges"),
    ]

    passed = 0
    failed = 0

    print("\n=== CATEGORY PREDICTION TESTS ===")
    for text, expected in test_cases:
        result = processor._predict_category(text)
        if result == expected:
            print(f"✓ PASS: '{text[:30]}...' -> {result}")
            passed += 1
        else:
            print(f"✗ FAIL: '{text[:30]}...' -> {result} (expected: {expected})")
            failed += 1

    print(f"\nResults: {passed} passed, {failed} failed")
    return failed == 0


def test_income_category_prediction():
    """Test income category prediction"""
    processor = IncomeProcessor(use_llm=False)

    test_cases = [
        ("Honorar Projekt XYZ", "Honorar"),
        ("Lizenzgebühren GEMA", "Lizenzgebühren"),
        ("Workshop Python Grundlagen", "Workshops"),
        ("Stipendium Künstlerförderung", "Stipendien"),
        ("Verkauf Kunstwerk Edition", "Verkäufe"),
        ("Sonstige Einnahme", "Sonstiges"),
    ]

    passed = 0
    failed = 0

    print("\n=== INCOME CATEGORY PREDICTION TESTS ===")
    for text, expected in test_cases:
        result = processor._predict_category(text)
        if result == expected:
            print(f"✓ PASS: '{text[:30]}...' -> {result}")
            passed += 1
        else:
            print(f"✗ FAIL: '{text[:30]}...' -> {result} (expected: {expected})")
            failed += 1

    print(f"\nResults: {passed} passed, {failed} failed")
    return failed == 0


def test_full_document_extraction():
    """Test full document extraction"""
    processor = OCRProcessor(use_llm=False)

    test_document = """
    RECHNUNG

    Firma Test GmbH
    Musterstraße 123
    12345 Berlin

    Rechnungsdatum: 01.11.2025
    Rechnungsnummer: R-2025-1234

    Artikel: MacBook Pro 14"
    Menge: 1
    Preis: 1.299,99 €

    Netto: 1.092,43 €
    MwSt 19%: 207,56 €
    Brutto: 1.299,99 €

    Zahlbar innerhalb 14 Tagen.
    """

    print("\n=== FULL DOCUMENT EXTRACTION TEST ===")
    date = processor._extract_date(test_document)
    amount = processor._extract_amount(test_document)
    category = processor._predict_category(test_document)
    description = processor._extract_description(test_document)

    print(f"Date: {date}")
    print(f"Amount: {amount}")
    print(f"Category: {category}")
    print(f"Description: {description}")

    # Validate
    passed = True
    if date != "2025-11-01":
        print(f"✗ Date extraction failed: {date}")
        passed = False
    if amount != 1299.99:
        print(f"✗ Amount extraction failed: {amount}")
        passed = False
    if category != "Büro":
        print(f"✗ Category prediction failed: {category}")
        passed = False

    if passed:
        print("✓ Full document extraction PASSED")
    else:
        print("✗ Full document extraction FAILED")

    return passed


if __name__ == '__main__':
    print("=" * 60)
    print("OCR EXTRACTION TEST SUITE")
    print("=" * 60)

    all_passed = True

    all_passed &= test_amount_extraction()
    all_passed &= test_date_extraction()
    all_passed &= test_category_prediction()
    all_passed &= test_income_category_prediction()
    all_passed &= test_full_document_extraction()

    print("\n" + "=" * 60)
    if all_passed:
        print("✓ ALL TESTS PASSED")
        sys.exit(0)
    else:
        print("✗ SOME TESTS FAILED")
        sys.exit(1)
