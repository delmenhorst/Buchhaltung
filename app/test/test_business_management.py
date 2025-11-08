#!/usr/bin/env python3
"""
Business Management Tests - pytest compatible

Kritische Tests für Business-Verwaltung:
- Business erstellen
- Business löschen (CASCADE)
"""

from pathlib import Path


def test_create_business_creates_folders(test_db, test_data_dir, folder_manager):
    """Test: Business erstellen → Ordner werden erstellt"""
    business_name = 'TestBiz'
    business_id = test_db.add_business(
        name=business_name,
        inbox_path=str(test_data_dir / 'Inbox' / business_name),
        archive_path=str(test_data_dir / 'Archive' / business_name),
        prefix='TZ',
        color='#FF0000'
    )

    assert business_id > 0, "Business should be created"

    # Create folders
    folder_manager.create_business_folders(business_name)

    # Check folders exist
    inbox_ausgaben = test_data_dir / 'Inbox' / business_name / 'Ausgaben'
    inbox_einnahmen = test_data_dir / 'Inbox' / business_name / 'Einnahmen'

    assert inbox_ausgaben.exists(), "Inbox/Ausgaben should exist"
    assert inbox_einnahmen.exists(), "Inbox/Einnahmen should exist"


def test_delete_business_with_cascade(test_db, test_data_dir, folder_manager, create_test_invoice):
    """Test: Business mit CASCADE löschen → Alle Daten weg"""
    business_name = 'DeleteMe'
    business_id = test_db.add_business(
        name=business_name,
        inbox_path=str(test_data_dir / 'Inbox' / business_name),
        archive_path=str(test_data_dir / 'Archive' / business_name),
        prefix='DM',
        color='#00FF00'
    )

    # Create folders
    folder_manager.create_business_folders(business_name)

    # Add invoices
    invoice1_id, _, _ = create_test_invoice(business_id, amount=1000.0)
    invoice2_id, _, _ = create_test_invoice(business_id, amount=2000.0)

    # Verify invoices exist
    conn = test_db.get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) as count FROM invoices WHERE business_id = ?', (business_id,))
    count_before = cursor.fetchone()['count']
    assert count_before == 2, "Should have 2 invoices before deletion"

    # Delete with CASCADE
    test_db.delete_business(business_id, cascade=True)

    # Verify all invoices are deleted
    cursor.execute('SELECT COUNT(*) as count FROM invoices WHERE business_id = ?', (business_id,))
    count_after = cursor.fetchone()['count']
    assert count_after == 0, "Should have 0 invoices after CASCADE deletion"

    # Verify business is deleted
    cursor.execute('SELECT * FROM businesses WHERE id = ?', (business_id,))
    business = cursor.fetchone()
    assert business is None, "Business should be deleted"

    conn.close()

    # Delete folders
    folder_manager.delete_business_folders(business_name)

    # Verify folders are deleted
    inbox_path = test_data_dir / 'Inbox' / business_name
    archive_path = test_data_dir / 'Archive' / business_name

    assert not inbox_path.exists(), "Inbox should be deleted"
    assert not archive_path.exists(), "Archive should be deleted"
