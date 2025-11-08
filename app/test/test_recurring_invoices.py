#!/usr/bin/env python3
"""
Recurring Invoice Tests - pytest compatible

Tests für wiederkehrende Buchungen:
- Erstellen
- Monatliche Generierung
"""


def test_create_recurring_transaction(test_business):
    """Test: Wiederkehrende Buchung erstellen"""
    business_id, business_name, prefix, test_db, test_data_dir = test_business

    conn = test_db.get_connection()
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

    # Verify created
    cursor.execute('SELECT * FROM recurring_transactions WHERE id = ?', (recurring_id,))
    recurring = cursor.fetchone()
    conn.close()

    assert recurring is not None, "Recurring transaction should exist"
    assert recurring['description'] == 'Miete Büro', "Description should match"
    assert recurring['amount'] == 850.00, "Amount should match"
    assert recurring['frequency'] == 'monthly', "Frequency should be monthly"


def test_generate_monthly_invoices(test_business):
    """Test: Monatliche Generierung → Korrekte Anzahl"""
    business_id, business_name, prefix, test_db, test_data_dir = test_business

    conn = test_db.get_connection()
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
    test_db.generate_recurring_transactions()

    # Count generated invoices
    cursor.execute('''
        SELECT COUNT(*) as count FROM invoices
        WHERE business_id = ? AND is_recurring_generated = 1
    ''', (business_id,))

    count = cursor.fetchone()['count']
    conn.close()

    # Should generate 3 invoices (Jan, Feb, Mar)
    assert count == 3, "Should generate 3 monthly invoices"
