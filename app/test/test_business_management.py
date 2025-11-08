#!/usr/bin/env python3
"""
Business Management Tests

Tests für:
- Business erstellen → Ordner prüfen
- Business löschen (leer) → Ordner gelöscht
- Business löschen (mit Daten) → Fehlermeldung
- Business löschen (CASCADE) → Alles weg
- Business löschen (REASSIGN) → Daten verschoben
"""

import sys
import shutil
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from test_helpers import TestBase, TestDataFactory, cleanup_test_folders
from app.folder_manager import FolderManager


class BusinessManagementTester(TestBase):
    def __init__(self):
        super().__init__('business_management')
        self.test_data_dir = Path(__file__).parent / 'test_data'

        # Initialize FolderManager for testing
        self.folder_manager = FolderManager(
            inbox_base=str(self.test_data_dir / 'Inbox'),
            archive_base=str(self.test_data_dir / 'Archive')
        )

    def test_1_create_business_creates_folders(self):
        """Test 1: Business erstellen → Ordner werden erstellt"""
        business_id = TestDataFactory.create_test_business(
            self.db, name='TestBusiness1', prefix='T1'
        )

        self.assert_true(business_id > 0, "Business should be created")

        # Check folders exist
        inbox_ausgaben = self.test_data_dir / 'Inbox' / 'TestBusiness1' / 'Ausgaben'
        inbox_einnahmen = self.test_data_dir / 'Inbox' / 'TestBusiness1' / 'Einnahmen'
        archive_ausgaben_2025 = self.test_data_dir / 'Archive' / 'TestBusiness1' / 'Ausgaben' / '2025'
        archive_einnahmen_2025 = self.test_data_dir / 'Archive' / 'TestBusiness1' / 'Einnahmen' / '2025'

        self.assert_path_exists(inbox_ausgaben, "Inbox/Ausgaben should exist")
        self.assert_path_exists(inbox_einnahmen, "Inbox/Einnahmen should exist")
        self.assert_path_exists(archive_ausgaben_2025, "Archive/Ausgaben/2025 should exist")
        self.assert_path_exists(archive_einnahmen_2025, "Archive/Einnahmen/2025 should exist")

        return True

    def test_2_delete_empty_business_removes_folders(self):
        """Test 2: Leeres Business löschen → Ordner werden gelöscht"""
        # Create business
        business_id = TestDataFactory.create_test_business(
            self.db, name='TestBusiness2', prefix='T2'
        )

        inbox_path = self.test_data_dir / 'Inbox' / 'TestBusiness2'
        archive_path = self.test_data_dir / 'Archive' / 'TestBusiness2'

        # Verify folders exist
        self.assert_path_exists(inbox_path, "Inbox should exist before deletion")
        self.assert_path_exists(archive_path, "Archive should exist before deletion")

        # Delete business (CASCADE since it's empty)
        self.db.delete_business(business_id, cascade=True)

        # Delete folders manually (since we're testing the database logic, not the Flask route)
        self.folder_manager.delete_business_folders('TestBusiness2')

        # Verify folders are deleted
        self.assert_path_not_exists(inbox_path, "Inbox should be deleted")
        self.assert_path_not_exists(archive_path, "Archive should be deleted")

        # Verify business is deleted from database
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM businesses WHERE id = ?', (business_id,))
        business = cursor.fetchone()
        conn.close()

        self.assert_true(business is None, "Business should be deleted from database")

        return True

    def test_3_delete_business_with_data_requires_cascade_or_reassign(self):
        """Test 3: Business mit Daten löschen → Fehlermeldung ohne CASCADE/REASSIGN"""
        # Create business with invoice
        business_id = TestDataFactory.create_test_business(
            self.db, name='TestBusiness3', prefix='T3'
        )

        # Add an invoice
        TestDataFactory.create_test_invoice(
            self.db, business_id,
            invoice_type='Ausgabe',
            amount=1000.0,
            category='Büro',
            description='Test'
        )

        # Try to delete without cascade or reassign - should fail
        try:
            self.db.delete_business(business_id, cascade=False, reassign_to=None)
            # If we get here, the deletion succeeded (which is wrong)
            return False
        except Exception as e:
            # Expected to fail
            error_message = str(e)
            self.assert_in('invoice', error_message.lower(), "Error should mention invoices")
            return True

    def test_4_delete_business_with_cascade_removes_all_data(self):
        """Test 4: Business mit CASCADE löschen → Alle Daten weg"""
        # Create business with invoices
        business_id = TestDataFactory.create_test_business(
            self.db, name='TestBusiness4', prefix='T4'
        )

        # Add multiple invoices
        invoice1_id, _, _ = TestDataFactory.create_test_invoice(
            self.db, business_id, amount=1000.0
        )
        invoice2_id, _, _ = TestDataFactory.create_test_invoice(
            self.db, business_id, amount=2000.0
        )

        # Verify invoices exist
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) as count FROM invoices WHERE business_id = ?', (business_id,))
        count_before = cursor.fetchone()['count']
        self.assert_equal(count_before, 2, "Should have 2 invoices before deletion")

        # Delete with CASCADE
        self.db.delete_business(business_id, cascade=True)

        # Verify all invoices are deleted
        cursor.execute('SELECT COUNT(*) as count FROM invoices WHERE business_id = ?', (business_id,))
        count_after = cursor.fetchone()['count']
        self.assert_equal(count_after, 0, "Should have 0 invoices after CASCADE deletion")

        # Verify business is deleted
        cursor.execute('SELECT * FROM businesses WHERE id = ?', (business_id,))
        business = cursor.fetchone()
        self.assert_true(business is None, "Business should be deleted")

        conn.close()

        # Delete folders
        self.folder_manager.delete_business_folders('TestBusiness4')

        # Verify folders are deleted
        inbox_path = self.test_data_dir / 'Inbox' / 'TestBusiness4'
        archive_path = self.test_data_dir / 'Archive' / 'TestBusiness4'

        self.assert_path_not_exists(inbox_path, "Inbox should be deleted")
        self.assert_path_not_exists(archive_path, "Archive should be deleted")

        return True

    def test_5_delete_business_with_reassign_moves_data(self):
        """Test 5: Business mit REASSIGN löschen → Daten werden verschoben"""
        # Create two businesses
        business1_id = TestDataFactory.create_test_business(
            self.db, name='TestBusiness5A', prefix='5A'
        )
        business2_id = TestDataFactory.create_test_business(
            self.db, name='TestBusiness5B', prefix='5B'
        )

        # Add invoices to business1
        invoice1_id, _, _ = TestDataFactory.create_test_invoice(
            self.db, business1_id, amount=1000.0
        )
        invoice2_id, _, _ = TestDataFactory.create_test_invoice(
            self.db, business1_id, amount=2000.0
        )

        # Verify invoices belong to business1
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) as count FROM invoices WHERE business_id = ?', (business1_id,))
        count_before_b1 = cursor.fetchone()['count']
        self.assert_equal(count_before_b1, 2, "Business1 should have 2 invoices")

        cursor.execute('SELECT COUNT(*) as count FROM invoices WHERE business_id = ?', (business2_id,))
        count_before_b2 = cursor.fetchone()['count']
        self.assert_equal(count_before_b2, 0, "Business2 should have 0 invoices")

        # Delete business1 with REASSIGN to business2
        self.db.delete_business(business1_id, cascade=False, reassign_to=business2_id)

        # Verify invoices are now assigned to business2
        cursor.execute('SELECT COUNT(*) as count FROM invoices WHERE business_id = ?', (business1_id,))
        count_after_b1 = cursor.fetchone()['count']
        self.assert_equal(count_after_b1, 0, "Business1 should have 0 invoices after reassignment")

        cursor.execute('SELECT COUNT(*) as count FROM invoices WHERE business_id = ?', (business2_id,))
        count_after_b2 = cursor.fetchone()['count']
        self.assert_equal(count_after_b2, 2, "Business2 should have 2 invoices after reassignment")

        # Verify business1 is deleted
        cursor.execute('SELECT * FROM businesses WHERE id = ?', (business1_id,))
        business1 = cursor.fetchone()
        self.assert_true(business1 is None, "Business1 should be deleted")

        conn.close()

        return True

    def test_6_get_business_by_id(self):
        """Test 6: Business per ID abrufen"""
        business_id = TestDataFactory.create_test_business(
            self.db, name='TestBusiness6', prefix='T6', color='#FF0000'
        )

        business = self.db.get_business(business_id)

        self.assert_true(business is not None, "Business should exist")
        self.assert_equal(business['name'], 'TestBusiness6', "Business name should match")
        self.assert_equal(business['prefix'], 'T6', "Business prefix should match")
        self.assert_equal(business['color'], '#FF0000', "Business color should match")

        return True

    def run_all_tests(self):
        """Run all business management tests"""
        self.run_test(self.test_1_create_business_creates_folders,
                      "Create Business → Folders Created")

        self.run_test(self.test_2_delete_empty_business_removes_folders,
                      "Delete Empty Business → Folders Removed")

        self.run_test(self.test_3_delete_business_with_data_requires_cascade_or_reassign,
                      "Delete Business with Data → Requires CASCADE/REASSIGN")

        self.run_test(self.test_4_delete_business_with_cascade_removes_all_data,
                      "Delete Business with CASCADE → All Data Removed")

        self.run_test(self.test_5_delete_business_with_reassign_moves_data,
                      "Delete Business with REASSIGN → Data Moved")

        self.run_test(self.test_6_get_business_by_id,
                      "Get Business by ID")

        return self.print_summary()


if __name__ == '__main__':
    # Clean up before starting
    cleanup_test_folders()

    # Run tests
    tester = BusinessManagementTester()
    success = tester.run_all_tests()

    # Clean up after tests
    cleanup_test_folders()

    # Exit with appropriate code
    sys.exit(0 if success else 1)
