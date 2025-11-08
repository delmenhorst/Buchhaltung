#!/usr/bin/env python3
"""
Test Helpers - Utilities for all tests

Provides common functions, fixtures, and assertions for test files.
"""

import sys
import shutil
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import Database


class TestBase:
    """Base class for all test suites"""

    def __init__(self, test_name):
        self.test_name = test_name
        self.test_dir = Path(__file__).parent
        self.test_data_dir = self.test_dir / 'test_data'
        self.test_data_dir.mkdir(exist_ok=True)

        # Setup test database
        test_db_path = self.test_data_dir / f'test_{test_name}.db'
        if test_db_path.exists():
            test_db_path.unlink()

        self.db = Database(str(test_db_path))
        self.passed_tests = 0
        self.failed_tests = 0

        print(f"\n{'='*60}")
        print(f"🧪 {test_name.upper()} TEST SUITE")
        print(f"{'='*60}")
        print(f"✅ Test database initialized: {test_db_path}")

    def assert_equal(self, actual, expected, message=""):
        """Assert that two values are equal"""
        if actual == expected:
            return True
        else:
            error_msg = f"Expected {expected}, got {actual}"
            if message:
                error_msg = f"{message}: {error_msg}"
            raise AssertionError(error_msg)

    def assert_not_equal(self, actual, expected, message=""):
        """Assert that two values are not equal"""
        if actual != expected:
            return True
        else:
            error_msg = f"Expected value to not be {expected}, but it was"
            if message:
                error_msg = f"{message}: {error_msg}"
            raise AssertionError(error_msg)

    def assert_true(self, condition, message=""):
        """Assert that condition is True"""
        if condition:
            return True
        else:
            error_msg = "Condition was False"
            if message:
                error_msg = message
            raise AssertionError(error_msg)

    def assert_false(self, condition, message=""):
        """Assert that condition is False"""
        if not condition:
            return True
        else:
            error_msg = "Condition was True"
            if message:
                error_msg = message
            raise AssertionError(error_msg)

    def assert_in(self, item, container, message=""):
        """Assert that item is in container"""
        if item in container:
            return True
        else:
            error_msg = f"{item} not found in {container}"
            if message:
                error_msg = f"{message}: {error_msg}"
            raise AssertionError(error_msg)

    def assert_not_in(self, item, container, message=""):
        """Assert that item is not in container"""
        if item not in container:
            return True
        else:
            error_msg = f"{item} found in {container}"
            if message:
                error_msg = f"{message}: {error_msg}"
            raise AssertionError(error_msg)

    def assert_path_exists(self, path, message=""):
        """Assert that a file/directory path exists"""
        path_obj = Path(path)
        if path_obj.exists():
            return True
        else:
            error_msg = f"Path does not exist: {path}"
            if message:
                error_msg = f"{message}: {error_msg}"
            raise AssertionError(error_msg)

    def assert_path_not_exists(self, path, message=""):
        """Assert that a file/directory path does not exist"""
        path_obj = Path(path)
        if not path_obj.exists():
            return True
        else:
            error_msg = f"Path exists but shouldn't: {path}"
            if message:
                error_msg = f"{message}: {error_msg}"
            raise AssertionError(error_msg)

    def assert_filename_format(self, filename, expected_amount_decimal=2):
        """Assert that filename follows the correct format: YYMMDD_InvoiceID_Category_Description_Amount.pdf"""
        parts = filename.replace('.pdf', '').replace('.virtual', '').split('_')

        # Check minimum parts: date, invoice_id, category, description, amount_part1, amount_part2
        if len(parts) < 6:
            raise AssertionError(f"Filename has too few parts: {filename}")

        # Check date format (YYMMDD)
        date_part = parts[0]
        if len(date_part) != 6 or not date_part.isdigit():
            raise AssertionError(f"Invalid date format in filename: {date_part}")

        # Check invoice ID format (ARE-XX-YYYY### or ERE-XX-YYYY###)
        invoice_id = parts[1]
        if not (invoice_id.startswith('ARE-') or invoice_id.startswith('ERE-')):
            raise AssertionError(f"Invalid invoice ID format: {invoice_id}")

        # Check amount has 2 decimal places (last two parts should be amount_XX)
        amount_whole = parts[-2]
        amount_decimal = parts[-1]

        if not amount_whole.isdigit():
            raise AssertionError(f"Invalid amount whole part: {amount_whole}")

        if len(amount_decimal) != expected_amount_decimal:
            raise AssertionError(f"Amount decimal part should have {expected_amount_decimal} digits, got {len(amount_decimal)}: {amount_decimal}")

        return True

    def run_test(self, test_func, test_name):
        """Run a single test and track results"""
        print(f"\n{'='*60}")
        print(f"TEST: {test_name}")
        print(f"{'='*60}")

        try:
            result = test_func()
            if result:
                print(f"✅ PASS: {test_name}")
                self.passed_tests += 1
                return True
            else:
                print(f"❌ FAIL: {test_name}")
                self.failed_tests += 1
                return False
        except AssertionError as e:
            print(f"❌ FAIL: {test_name}")
            print(f"   Reason: {e}")
            self.failed_tests += 1
            return False
        except Exception as e:
            print(f"❌ ERROR: {test_name}")
            print(f"   Exception: {e}")
            import traceback
            traceback.print_exc()
            self.failed_tests += 1
            return False

    def print_summary(self):
        """Print test summary"""
        total = self.passed_tests + self.failed_tests
        pass_rate = (self.passed_tests / total * 100) if total > 0 else 0

        print(f"\n{'='*60}")
        print(f"📊 TEST SUMMARY")
        print(f"{'='*60}")
        print(f"Total Tests:  {total}")
        print(f"✅ Passed:     {self.passed_tests}")
        print(f"❌ Failed:     {self.failed_tests}")
        print(f"📈 Pass Rate:  {pass_rate:.1f}%")
        print(f"{'='*60}")

        if self.failed_tests == 0:
            print("🎉 ALL TESTS PASSED!")
        else:
            print(f"⚠️  {self.failed_tests} test(s) failed")

        return self.failed_tests == 0


class TestDataFactory:
    """Factory for creating test data"""

    @staticmethod
    def create_test_business(db, name='TestBusiness', prefix='TB', color='#3B82F6'):
        """Create a test business"""
        test_data_dir = Path(__file__).parent / 'test_data'

        business_id = db.add_business(
            name=name,
            inbox_path=str(test_data_dir / 'Inbox' / name),
            archive_path=str(test_data_dir / 'Archive' / name),
            prefix=prefix,
            color=color
        )

        # Create folder structure
        for folder_type in ['Einnahmen', 'Ausgaben']:
            inbox_path = test_data_dir / 'Inbox' / name / folder_type
            inbox_path.mkdir(parents=True, exist_ok=True)

            for year in [2024, 2025]:
                archive_path = test_data_dir / 'Archive' / name / folder_type / str(year)
                archive_path.mkdir(parents=True, exist_ok=True)

        return business_id

    @staticmethod
    def create_test_invoice(db, business_id, invoice_type='Ausgabe',
                             amount=1299.50, category='Büro',
                             description='Test Invoice'):
        """Create a test invoice"""
        from datetime import datetime

        date_str = datetime.now().strftime('%Y-%m-%d')
        year = datetime.now().year

        # Get next invoice ID
        next_id = db.get_next_invoice_id(year=year, business_id=business_id)

        # Get business details
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT name, prefix FROM businesses WHERE id = ?', (business_id,))
        business = cursor.fetchone()

        if not business:
            raise ValueError(f"Business {business_id} not found")

        business_name = business['name']
        prefix = business['prefix']

        # Generate invoice ID
        type_prefix = 'ARE' if invoice_type == 'Ausgabe' else 'ERE'
        invoice_id = f"{type_prefix}-{prefix}-{year}{next_id:03d}"

        # Generate filename
        date_obj = datetime.now()
        date_str_short = date_obj.strftime('%y%m%d')
        category_safe = category.replace('/', '-')
        description_safe = description[:30].replace('/', '-').replace(' ', '_').strip('_')
        amount_safe = f"{float(amount):.2f}".replace('.', '_')

        filename = f"{date_str_short}_{invoice_id}_{category_safe}_{description_safe}_{amount_safe}.pdf"
        filename = filename.replace('__', '_')

        folder_type = 'Ausgaben' if invoice_type == 'Ausgabe' else 'Einnahmen'
        file_path = f"Archive/{business_name}/{folder_type}/{year}/{filename}"

        # Insert invoice
        cursor.execute('''
            INSERT INTO invoices (
                business_id, file_path, original_filename, invoice_id,
                date, amount, category, description, type,
                processed, is_archived, reviewed
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            business_id, file_path, filename, invoice_id,
            date_str, amount, category, description, invoice_type,
            1, 1, 1
        ))

        invoice_id_pk = cursor.lastrowid
        conn.commit()
        conn.close()

        return invoice_id_pk, invoice_id, filename


def cleanup_test_folders():
    """Clean up all test folders"""
    test_data_dir = Path(__file__).parent / 'test_data'

    if test_data_dir.exists():
        # Clean Inbox and Archive folders
        for subfolder in ['Inbox', 'Archive']:
            folder = test_data_dir / subfolder
            if folder.exists():
                shutil.rmtree(folder)

        print(f"✅ Test folders cleaned: {test_data_dir}")
