#!/usr/bin/env python3
"""
Manual Invoice Tests

Tests für:
- Manuelle Ausgabe erstellen → Filename-Format + Betrag .2f
- Manuelle Einnahme erstellen → ERE-Prefix + Betrag .2f
- PDF-Generierung → Placeholder erstellt
- Metadaten ändern → Datei umbenannt
- Amount-Edge-Cases (0.5, 1000.1, 9999.99)
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from test_helpers import TestBase, TestDataFactory, cleanup_test_folders


class ManualInvoicesTester(TestBase):
    def __init__(self):
        super().__init__('manual_invoices')
        self.test_data_dir = Path(__file__).parent / 'test_data'

    def test_1_create_manual_expense_correct_format(self):
        """Test 1: Manuelle Ausgabe → Filename-Format korrekt"""
        business_id = TestDataFactory.create_test_business(
            self.db, name='TestBusiness1', prefix='TB'
        )

        invoice_id, invoice_number, filename = TestDataFactory.create_test_invoice(
            self.db, business_id,
            invoice_type='Ausgabe',
            amount=1299.50,
            category='Büro',
            description='Laptop HP ProBook'
        )

        # Check filename format
        self.assert_filename_format(filename, expected_amount_decimal=2)

        # Check specific parts
        self.assert_in('ARE-TB', filename, "Filename should contain ARE-TB prefix")
        self.assert_in('1299_50', filename, "Filename should contain amount 1299_50")
        self.assert_in('Büro', filename, "Filename should contain category")
        self.assert_in('Laptop', filename, "Filename should contain description")

        return True

    def test_2_create_manual_income_ere_prefix(self):
        """Test 2: Manuelle Einnahme → ERE-Prefix korrekt"""
        business_id = TestDataFactory.create_test_business(
            self.db, name='TestBusiness2', prefix='T2'
        )

        invoice_id, invoice_number, filename = TestDataFactory.create_test_invoice(
            self.db, business_id,
            invoice_type='Einnahme',
            amount=2500.00,
            category='Honorar',
            description='Projekt XYZ'
        )

        # Check ERE prefix
        self.assert_in('ERE-T2', filename, "Filename should contain ERE-T2 prefix")
        self.assert_in('2500_00', filename, "Filename should contain amount 2500_00")

        # Verify in database
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM invoices WHERE id = ?', (invoice_id,))
        invoice = cursor.fetchone()
        conn.close()

        self.assert_equal(invoice['type'], 'Einnahme', "Type should be Einnahme")
        self.assert_equal(invoice['amount'], 2500.00, "Amount should be 2500.00")

        return True

    def test_3_amount_one_decimal_converts_to_two(self):
        """Test 3: Betrag mit 1 Dezimalstelle → Konvertiert zu 2 Dezimalstellen"""
        business_id = TestDataFactory.create_test_business(
            self.db, name='TestBusiness3', prefix='T3'
        )

        # Amount: 1299.9 → Should become 1299_90
        invoice_id, invoice_number, filename = TestDataFactory.create_test_invoice(
            self.db, business_id,
            invoice_type='Ausgabe',
            amount=1299.9,
            category='Büro',
            description='Test'
        )

        self.assert_in('1299_90', filename, "Amount 1299.9 should become 1299_90")
        self.assert_not_in('1299_9', filename, "Amount should NOT be 1299_9 (missing trailing zero)")

        return True

    def test_4_amount_edge_case_zero_five(self):
        """Test 4: Edge Case → Betrag 0.50"""
        business_id = TestDataFactory.create_test_business(
            self.db, name='TestBusiness4', prefix='T4'
        )

        invoice_id, invoice_number, filename = TestDataFactory.create_test_invoice(
            self.db, business_id,
            invoice_type='Ausgabe',
            amount=0.5,
            category='Porto',
            description='Briefmarke'
        )

        self.assert_in('0_50', filename, "Amount 0.5 should become 0_50")

        return True

    def test_5_amount_edge_case_large_number(self):
        """Test 5: Edge Case → Großer Betrag 9999.99"""
        business_id = TestDataFactory.create_test_business(
            self.db, name='TestBusiness5', prefix='T5'
        )

        invoice_id, invoice_number, filename = TestDataFactory.create_test_invoice(
            self.db, business_id,
            invoice_type='Ausgabe',
            amount=9999.99,
            category='Büro',
            description='Server'
        )

        self.assert_in('9999_99', filename, "Amount 9999.99 should become 9999_99")

        return True

    def test_6_amount_edge_case_round_number(self):
        """Test 6: Edge Case → Runder Betrag 1000.00"""
        business_id = TestDataFactory.create_test_business(
            self.db, name='TestBusiness6', prefix='T6'
        )

        invoice_id, invoice_number, filename = TestDataFactory.create_test_invoice(
            self.db, business_id,
            invoice_type='Ausgabe',
            amount=1000.0,
            category='Raum',
            description='Miete'
        )

        self.assert_in('1000_00', filename, "Amount 1000.0 should become 1000_00")

        return True

    def test_7_invoice_is_auto_archived(self):
        """Test 7: Manuelle Buchung → Automatisch archiviert"""
        business_id = TestDataFactory.create_test_business(
            self.db, name='TestBusiness7', prefix='T7'
        )

        invoice_id, invoice_number, filename = TestDataFactory.create_test_invoice(
            self.db, business_id,
            invoice_type='Ausgabe',
            amount=500.0,
            category='Telefon',
            description='Handyrechnung'
        )

        # Verify invoice is marked as archived and processed
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM invoices WHERE id = ?', (invoice_id,))
        invoice = cursor.fetchone()
        conn.close()

        self.assert_equal(invoice['is_archived'], 1, "Invoice should be archived")
        self.assert_equal(invoice['processed'], 1, "Invoice should be processed")
        self.assert_equal(invoice['reviewed'], 1, "Invoice should be reviewed")

        return True

    def test_8_special_characters_in_description(self):
        """Test 8: Sonderzeichen in Beschreibung → Korrekt bereinigt"""
        business_id = TestDataFactory.create_test_business(
            self.db, name='TestBusiness8', prefix='T8'
        )

        invoice_id, invoice_number, filename = TestDataFactory.create_test_invoice(
            self.db, business_id,
            invoice_type='Ausgabe',
            amount=100.0,
            category='Büro',
            description='Büro/Material & Zubehör'
        )

        # Description should have / replaced with - and & should be handled
        self.assert_not_in('/', filename, "Filename should not contain /")
        self.assert_not_in('&', filename, "Filename should not contain &")

        return True

    def run_all_tests(self):
        """Run all manual invoice tests"""
        self.run_test(self.test_1_create_manual_expense_correct_format,
                      "Manual Expense → Correct Filename Format")

        self.run_test(self.test_2_create_manual_income_ere_prefix,
                      "Manual Income → ERE Prefix Correct")

        self.run_test(self.test_3_amount_one_decimal_converts_to_two,
                      "Amount 1299.9 → 1299_90 (2 decimals)")

        self.run_test(self.test_4_amount_edge_case_zero_five,
                      "Edge Case: Amount 0.5 → 0_50")

        self.run_test(self.test_5_amount_edge_case_large_number,
                      "Edge Case: Amount 9999.99 → 9999_99")

        self.run_test(self.test_6_amount_edge_case_round_number,
                      "Edge Case: Amount 1000.0 → 1000_00")

        self.run_test(self.test_7_invoice_is_auto_archived,
                      "Manual Invoice → Auto-Archived")

        self.run_test(self.test_8_special_characters_in_description,
                      "Special Characters → Correctly Sanitized")

        return self.print_summary()


if __name__ == '__main__':
    # Clean up before starting
    cleanup_test_folders()

    # Run tests
    tester = ManualInvoicesTester()
    success = tester.run_all_tests()

    # Clean up after tests
    cleanup_test_folders()

    # Exit with appropriate code
    sys.exit(0 if success else 1)
