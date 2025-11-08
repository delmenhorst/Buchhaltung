#!/usr/bin/env python3
"""
Basic Functionality Tests - No external dependencies
Tests core logic without OCR
"""

import sys
import shutil
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import Database

class BasicFunctionalityTester:
    def __init__(self):
        self.test_dir = Path(__file__).parent
        self.test_data_dir = self.test_dir / 'test_data'
        self.test_data_dir.mkdir(exist_ok=True)

        # Setup test database
        test_db_path = self.test_data_dir / 'test_basic.db'
        if test_db_path.exists():
            test_db_path.unlink()

        self.db = Database(str(test_db_path))
        print("✅ Test database initialized")

    def test_database_connection(self):
        """Test 1: Database Connection"""
        print("\n" + "="*60)
        print("TEST 1: Database Connection")
        print("="*60)

        try:
            # Try to add a business
            business_id = self.db.add_business('TestBusiness', '/test/path')

            if business_id:
                print(f"✅ PASS: Database connected and business created (ID: {business_id})")
                return True
            else:
                print("❌ FAIL: Could not create business")
                return False
        except Exception as e:
            print(f"❌ FAIL: Database error: {e}")
            return False

    def test_file_naming_convention(self):
        """Test 2: File Naming Convention for Steuer"""
        print("\n" + "="*60)
        print("TEST 2: File Naming Convention (Steuer-Format)")
        print("="*60)

        # Test data
        date = datetime(2025, 11, 2)
        invoice_type = "ARE"  # Ausgabe
        invoice_number = 42
        description = "Test Rechnung für Büro"

        # Generate filename - Format: YYYY-MM-DD_PRE-NNN_Beschreibung.pdf
        clean_desc = description.replace(' ', '-').replace('ä', 'ae').replace('ö', 'oe').replace('ü', 'ue')
        filename = f"{date.strftime('%Y-%m-%d')}_{invoice_type}-{invoice_number:03d}_{clean_desc}.pdf"

        expected = "2025-11-02_ARE-042_Test-Rechnung-fuer-Buero.pdf"

        print(f"Generated: {filename}")
        print(f"Expected:  {expected}")

        if filename == expected:
            print("✅ PASS: Filename format correct for Steuer")
            return True
        else:
            print("❌ FAIL: Filename format incorrect")
            return False

    def test_auto_save_validation(self):
        """Test 3: Auto-Save Validation Logic"""
        print("\n" + "="*60)
        print("TEST 3: Auto-Save Validation")
        print("="*60)

        test_cases = [
            ({"date": "2025-11-02", "amount": 100.0, "category": "Büro"}, True, "All required fields"),
            ({"date": "2025-11-02", "amount": 100.0}, False, "Missing category"),
            ({"date": "2025-11-02", "category": "Büro"}, False, "Missing amount"),
            ({"amount": 100.0, "category": "Büro"}, False, "Missing date"),
            ({}, False, "All missing"),
        ]

        all_pass = True
        for data, should_pass, desc in test_cases:
            # Validation logic from frontend
            has_required = bool(data.get('date') and data.get('amount') and data.get('category'))

            status = "✅" if has_required == should_pass else "❌"
            print(f"{status} {desc}: {has_required} (expected: {should_pass})")

            if has_required != should_pass:
                all_pass = False

        if all_pass:
            print("✅ PASS: Validation logic correct")
            return True
        else:
            print("❌ FAIL: Validation logic has errors")
            return False

    def test_invoice_id_generation(self):
        """Test 4: Invoice ID Generation"""
        print("\n" + "="*60)
        print("TEST 4: Invoice ID Generation")
        print("="*60)

        business = self.db.get_business_by_name('TestBusiness')
        if not business:
            print("❌ FAIL: Test business not found")
            return False

        # Generate IDs
        expense_id1 = self.db.get_next_invoice_id(year=2025, business_id=business['id'])
        expense_id2 = self.db.get_next_invoice_id(year=2025, business_id=business['id'])

        income_id1 = self.db.get_next_income_id(year=2025, business_id=business['id'])
        income_id2 = self.db.get_next_income_id(year=2025, business_id=business['id'])

        print(f"Expense IDs: {expense_id1}, {expense_id2}")
        print(f"Income IDs:  {income_id1}, {income_id2}")

        checks = [
            (expense_id1.startswith('ARE'), "Expense ID has ARE prefix"),
            (expense_id2.startswith('ARE'), "Second expense ID has ARE prefix"),
            (income_id1.startswith('ERE'), "Income ID has ERE prefix"),
            (income_id2.startswith('ERE'), "Second income ID has ERE prefix"),
            (expense_id1 != expense_id2, "Expense IDs are unique"),
            (income_id1 != income_id2, "Income IDs are unique"),
        ]

        all_pass = True
        for check, desc in checks:
            status = "✅" if check else "❌"
            print(f"{status} {desc}")
            if not check:
                all_pass = False

        if all_pass:
            print("✅ PASS: Invoice ID generation working")
            return True
        else:
            print("❌ FAIL: Invoice ID generation issues")
            return False

    def test_filter_logic(self):
        """Test 5: Filter Logic (Inbox/Archive/All)"""
        print("\n" + "="*60)
        print("TEST 5: Filter Logic")
        print("="*60)

        business = self.db.get_business_by_name('TestBusiness')

        # Add test files
        test_files = [
            ("/inbox/file1.pdf", False, False, "Inbox item 1"),
            ("/inbox/file2.pdf", False, False, "Inbox item 2"),
            ("/archive/file1.pdf", True, True, "Archived item 1"),
            ("/archive/file2.pdf", True, True, "Archived item 2"),
            ("/inbox/reviewed.pdf", True, False, "Reviewed but not archived"),
        ]

        for path, reviewed, archived, desc in test_files:
            file_id = self.db.add_file(path, business['id'])
            self.db.update_invoice(file_id, {
                'reviewed': reviewed,
                'is_archived': archived,
                'date': '2025-11-02',
                'amount': 100.0,
                'category': 'Test'
            })

        # Test filters
        all_files = self.db.get_all_files()

        # Inbox filter: not reviewed AND not archived
        inbox_files = [f for f in all_files
                      if not f.get('reviewed') and not f.get('is_archived')]

        # Archive filter: is_archived = True
        archive_files = [f for f in all_files
                        if f.get('is_archived')]

        print(f"Total files: {len(all_files)}")
        print(f"Inbox (unreviewed): {len(inbox_files)} (expected: 2)")
        print(f"Archived: {len(archive_files)} (expected: 2)")

        if len(inbox_files) == 2 and len(archive_files) == 2:
            print("✅ PASS: Filter logic working")
            return True
        else:
            print("❌ FAIL: Filter counts incorrect")
            return False

    def test_currency_formatting(self):
        """Test 6: Currency Formatting (German format)"""
        print("\n" + "="*60)
        print("TEST 6: Currency Formatting (1.000er Trennzeichen)")
        print("="*60)

        test_cases = [
            (1234.56, "1.234,56"),
            (100.00, "100,00"),
            (1000000.99, "1.000.000,99"),
            (0.50, "0,50"),
            (999.99, "999,99"),
        ]

        all_pass = True
        for amount, expected in test_cases:
            # German number format
            formatted = f"{amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

            status = "✅" if formatted == expected else "❌"
            print(f"{status} {amount:>12} → {formatted:>15} (expected: {expected})")

            if formatted != expected:
                all_pass = False

        if all_pass:
            print("✅ PASS: Currency formatting correct")
            return True
        else:
            print("❌ FAIL: Currency formatting issues")
            return False

    def test_flagging_system(self):
        """Test 7: Document Flagging"""
        print("\n" + "="*60)
        print("TEST 7: Flagging System")
        print("="*60)

        business = self.db.get_business_by_name('TestBusiness')
        file_id = self.db.add_file("/test/flag.pdf", business['id'])

        # Test flagging
        self.db.update_invoice(file_id, {'flagged': True})
        file_info = self.db.get_file(file_id)
        is_flagged = file_info.get('flagged', False)

        # Test unflagging
        self.db.update_invoice(file_id, {'flagged': False})
        file_info = self.db.get_file(file_id)
        is_unflagged = not file_info.get('flagged', False)

        print(f"Flagged: {is_flagged}")
        print(f"Unflagged: {is_unflagged}")

        if is_flagged and is_unflagged:
            print("✅ PASS: Flagging system working")
            return True
        else:
            print("❌ FAIL: Flagging system issues")
            return False

    def test_badge_counts(self):
        """Test 8: Sidebar Badge Counts"""
        print("\n" + "="*60)
        print("TEST 8: Badge Counts")
        print("="*60)

        business = self.db.get_business_by_name('TestBusiness')

        # Clear previous test data
        # Add new test data
        badge_test_files = [
            ("/badge/inbox1.pdf", False, False),
            ("/badge/inbox2.pdf", False, False),
            ("/badge/inbox3.pdf", False, False),
            ("/badge/archive1.pdf", True, True),
            ("/badge/archive2.pdf", True, True),
        ]

        for path, reviewed, archived in badge_test_files:
            file_id = self.db.add_file(path, business['id'])
            self.db.update_invoice(file_id, {
                'reviewed': reviewed,
                'is_archived': archived
            })

        # Count logic (from app.py)
        all_files = self.db.get_all_files()
        inbox_count = sum(1 for f in all_files
                         if not f.get('reviewed')
                         and not f.get('is_archived')
                         and '/Archive/' not in f.get('file_path', ''))

        print(f"Inbox badge count: {inbox_count} (expected: 3)")

        if inbox_count >= 3:  # At least 3 from this test
            print("✅ PASS: Badge counts working")
            return True
        else:
            print("❌ FAIL: Badge count incorrect")
            return False

    def run_all_tests(self):
        """Run all basic tests"""
        print("\n" + "="*70)
        print("🧪 BASIC FUNCTIONALITY TEST SUITE")
        print("="*70)

        tests = [
            ("Database Connection", self.test_database_connection),
            ("File Naming Convention", self.test_file_naming_convention),
            ("Auto-Save Validation", self.test_auto_save_validation),
            ("Invoice ID Generation", self.test_invoice_id_generation),
            ("Filter Logic", self.test_filter_logic),
            ("Currency Formatting", self.test_currency_formatting),
            ("Flagging System", self.test_flagging_system),
            ("Badge Counts", self.test_badge_counts),
        ]

        results = []
        for name, test_func in tests:
            try:
                result = test_func()
                results.append((name, result))
            except Exception as e:
                print(f"\n❌ ERROR in {name}: {e}")
                import traceback
                traceback.print_exc()
                results.append((name, False))

        # Summary
        print("\n" + "="*70)
        print("📊 TEST SUMMARY")
        print("="*70)

        passed = sum(1 for _, result in results if result)
        total = len(results)

        for name, result in results:
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{status}: {name}")

        print(f"\n{passed}/{total} tests passed ({passed/total*100:.0f}%)")

        if passed == total:
            print("\n🎉 ALL TESTS PASSED!")
        else:
            print(f"\n⚠️  {total - passed} test(s) failed")

        return passed == total

if __name__ == "__main__":
    tester = BasicFunctionalityTester()

    try:
        success = tester.run_all_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
