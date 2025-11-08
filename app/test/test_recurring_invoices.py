#!/usr/bin/env python3
"""
Recurring Invoice Tests

Tests für:
- Wiederkehrende Buchung erstellen
- Auto-Generierung monatlich
- Frequenz-Logik (monthly/yearly)
- Platzhalter-PDFs korrekt
- Deaktivierung (active=0)
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from test_helpers import TestBase, TestDataFactory, cleanup_test_folders


class RecurringInvoicesTester(TestBase):
    def __init__(self):
        super().__init__('recurring_invoices')
        self.test_data_dir = Path(__file__).parent / 'test_data'

    def test_1_create_recurring_transaction(self):
        """Test 1: Wiederkehrende Buchung erstellen"""
        business_id = TestDataFactory.create_test_business(
            self.db, name='TestBusiness1', prefix='TB'
        )

        # Create recurring transaction
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO recurring_transactions (
                business_id, type, description, amount, category,
                frequency, day_of_month, start_date, end_date, active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            business_id,
            'Ausgabe',
            'Miete Büro',
            850.00,
            'Raum',
            'monthly',
            1,
            '2025-01-01',
            '2025-12-31',
            1
        ))

        recurring_id = cursor.lastrowid
        conn.commit()
        conn.close()

        # Verify created
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM recurring_transactions WHERE id = ?', (recurring_id,))
        recurring = cursor.fetchone()
        conn.close()

        self.assert_true(recurring is not None, "Recurring transaction should exist")
        self.assert_equal(recurring['description'], 'Miete Büro', "Description should match")
        self.assert_equal(recurring['amount'], 850.00, "Amount should match")
        self.assert_equal(recurring['frequency'], 'monthly', "Frequency should be monthly")

        return True

    def test_2_generate_monthly_invoices(self):
        """Test 2: Monatliche Generierung → Korrekte Anzahl"""
        business_id = TestDataFactory.create_test_business(
            self.db, name='TestBusiness2', prefix='T2'
        )

        # Create recurring transaction
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO recurring_transactions (
                business_id, type, description, amount, category,
                frequency, day_of_month, start_date, end_date, active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            business_id,
            'Ausgabe',
            'Miete',
            1000.00,
            'Raum',
            'monthly',
            1,
            '2025-01-01',
            '2025-03-31',  # 3 months
            1
        ))

        recurring_id = cursor.lastrowid
        conn.commit()

        # Generate invoices
        self.db.generate_recurring_transactions()

        # Count generated invoices
        cursor.execute('''
            SELECT COUNT(*) as count FROM invoices
            WHERE business_id = ? AND is_recurring_generated = 1
        ''', (business_id,))

        count = cursor.fetchone()['count']
        conn.close()

        # Should generate 3 invoices (Jan, Feb, Mar)
        self.assert_equal(count, 3, "Should generate 3 monthly invoices")

        return True

    def test_3_yearly_frequency(self):
        """Test 3: Jährliche Frequenz → 1 Invoice pro Jahr"""
        business_id = TestDataFactory.create_test_business(
            self.db, name='TestBusiness3', prefix='T3'
        )

        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO recurring_transactions (
                business_id, type, description, amount, category,
                frequency, day_of_month, start_date, end_date, active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            business_id,
            'Ausgabe',
            'Versicherung',
            1200.00,
            'Versicherung',
            'yearly',
            1,
            '2023-01-01',
            '2025-12-31',  # 3 years
            1
        ))

        recurring_id = cursor.lastrowid
        conn.commit()

        # Generate invoices
        self.db.generate_recurring_transactions()

        # Count generated invoices
        cursor.execute('''
            SELECT COUNT(*) as count FROM invoices
            WHERE business_id = ? AND is_recurring_generated = 1
        ''', (business_id,))

        count = cursor.fetchone()['count']
        conn.close()

        # Should generate 3 invoices (2023, 2024, 2025)
        self.assert_equal(count, 3, "Should generate 3 yearly invoices")

        return True

    def test_4_filename_has_correct_amount_format(self):
        """Test 4: Generierte Invoices → Filename mit .2f Betrag"""
        business_id = TestDataFactory.create_test_business(
            self.db, name='TestBusiness4', prefix='T4'
        )

        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO recurring_transactions (
                business_id, type, description, amount, category,
                frequency, day_of_month, start_date, end_date, active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            business_id,
            'Ausgabe',
            'Test',
            850.5,  # One decimal
            'Raum',
            'monthly',
            1,
            '2025-01-01',
            '2025-01-31',
            1
        ))

        conn.commit()

        # Generate invoices
        self.db.generate_recurring_transactions()

        # Get generated invoice
        cursor.execute('''
            SELECT file_path FROM invoices
            WHERE business_id = ? AND is_recurring_generated = 1
            LIMIT 1
        ''', (business_id,))

        invoice = cursor.fetchone()
        conn.close()

        self.assert_true(invoice is not None, "Invoice should be generated")

        file_path = invoice['file_path']
        filename = Path(file_path).name

        # Check amount format
        self.assert_in('850_50', filename, "Amount 850.5 should become 850_50")
        self.assert_not_in('850_5', filename, "Amount should NOT be 850_5")

        return True

    def test_5_deactivated_recurring_not_generated(self):
        """Test 5: Deaktivierte Buchung → Wird nicht generiert"""
        business_id = TestDataFactory.create_test_business(
            self.db, name='TestBusiness5', prefix='T5'
        )

        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO recurring_transactions (
                business_id, type, description, amount, category,
                frequency, day_of_month, start_date, end_date, active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            business_id,
            'Ausgabe',
            'Deactivated',
            500.00,
            'Sonstiges',
            'monthly',
            1,
            '2025-01-01',
            '2025-12-31',
            0  # Deactivated
        ))

        conn.commit()

        # Generate invoices
        self.db.generate_recurring_transactions()

        # Count generated invoices
        cursor.execute('''
            SELECT COUNT(*) as count FROM invoices
            WHERE business_id = ? AND description = 'Deactivated'
        ''', (business_id,))

        count = cursor.fetchone()['count']
        conn.close()

        self.assert_equal(count, 0, "Deactivated recurring should not generate invoices")

        return True

    def test_6_end_date_limits_generation(self):
        """Test 6: End-Date → Limitiert Generierung"""
        business_id = TestDataFactory.create_test_business(
            self.db, name='TestBusiness6', prefix='T6'
        )

        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO recurring_transactions (
                business_id, type, description, amount, category,
                frequency, day_of_month, start_date, end_date, active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            business_id,
            'Ausgabe',
            'Limited',
            100.00,
            'Sonstiges',
            'monthly',
            1,
            '2025-01-01',
            '2025-02-28',  # Only 2 months
            1
        ))

        conn.commit()

        # Generate invoices
        self.db.generate_recurring_transactions()

        # Count generated invoices
        cursor.execute('''
            SELECT COUNT(*) as count FROM invoices
            WHERE business_id = ? AND description = 'Limited'
        ''', (business_id,))

        count = cursor.fetchone()['count']
        conn.close()

        self.assert_equal(count, 2, "Should only generate 2 invoices within end_date")

        return True

    def run_all_tests(self):
        """Run all recurring invoice tests"""
        self.run_test(self.test_1_create_recurring_transaction,
                      "Create Recurring Transaction")

        self.run_test(self.test_2_generate_monthly_invoices,
                      "Generate Monthly Invoices → Correct Count")

        self.run_test(self.test_3_yearly_frequency,
                      "Yearly Frequency → 1 Invoice per Year")

        self.run_test(self.test_4_filename_has_correct_amount_format,
                      "Generated Filename → Amount .2f Format")

        self.run_test(self.test_5_deactivated_recurring_not_generated,
                      "Deactivated Recurring → Not Generated")

        self.run_test(self.test_6_end_date_limits_generation,
                      "End Date → Limits Generation")

        return self.print_summary()


if __name__ == '__main__':
    # Clean up before starting
    cleanup_test_folders()

    # Run tests
    tester = RecurringInvoicesTester()
    success = tester.run_all_tests()

    # Clean up after tests
    cleanup_test_folders()

    # Exit with appropriate code
    sys.exit(0 if success else 1)
