#!/usr/bin/env python3
"""
Manual Invoice Tests - pytest compatible

Tests für manuelle Buchungen:
- Filename-Format mit 2 Dezimalstellen
- ARE/ERE-Prefix
- Amount Edge-Cases
"""


def test_create_manual_expense_correct_format(test_business, create_test_invoice):
    """Test: Manuelle Ausgabe → Filename-Format korrekt"""
    business_id, business_name, prefix, test_db, test_data_dir = test_business

    invoice_id, invoice_number, filename = create_test_invoice(
        business_id=business_id,
        invoice_type='Ausgabe',
        amount=1299.50,
        category='Büro',
        description='Laptop HP ProBook'
    )

    # Check filename contains required parts
    assert 'ARE' in filename, "Filename should contain ARE prefix"
    assert prefix in filename, f"Filename should contain business prefix {prefix}"
    assert '1299_50' in filename, "Filename should contain amount 1299_50"
    assert 'Büro' in filename, "Filename should contain category"
    assert 'Laptop' in filename, "Filename should contain description"


def test_create_manual_income_ere_prefix(test_business, create_test_invoice):
    """Test: Manuelle Einnahme → ERE-Prefix korrekt"""
    business_id, business_name, prefix, test_db, test_data_dir = test_business

    invoice_id, invoice_number, filename = create_test_invoice(
        business_id=business_id,
        invoice_type='Einnahme',
        amount=2500.00,
        category='Honorar',
        description='Projekt XYZ'
    )

    # Check ERE prefix
    assert 'ERE' in filename, "Filename should contain ERE prefix"
    assert '2500_00' in filename, "Filename should contain amount 2500_00"

    # Verify in database
    conn = test_db.get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM invoices WHERE id = ?', (invoice_id,))
    invoice = cursor.fetchone()
    conn.close()

    # Type is determined by invoice_id prefix (ERE = Einnahme, ARE = Ausgabe)
    assert invoice['invoice_id'].startswith('ERE'), "Invoice ID should start with ERE for Einnahme"
    assert invoice['amount'] == 2500.00, "Amount should be 2500.00"


def test_amount_one_decimal_converts_to_two(test_business, create_test_invoice):
    """Test: Betrag mit 1 Dezimalstelle → Konvertiert zu 2 Dezimalstellen"""
    business_id, business_name, prefix, test_db, test_data_dir = test_business

    invoice_id, invoice_number, filename = create_test_invoice(
        business_id=business_id,
        invoice_type='Ausgabe',
        amount=1299.9,
        category='Büro',
        description='Test'
    )

    # Check that amount is formatted with exactly 2 decimal places
    assert '1299_90' in filename, "Amount 1299.9 should become 1299_90"
    assert filename.endswith('1299_90.pdf'), "Filename should end with 1299_90.pdf (not 1299_9.pdf)"


def test_amount_edge_cases(test_business, create_test_invoice):
    """Test: Amount Edge-Cases → Alle mit 2 Dezimalstellen"""
    business_id, business_name, prefix, test_db, test_data_dir = test_business

    test_cases = [
        (0.5, '0_50'),
        (1000.0, '1000_00'),
        (9999.99, '9999_99'),
    ]

    for amount, expected_amount_str in test_cases:
        invoice_id, invoice_number, filename = create_test_invoice(
            business_id=business_id,
            invoice_type='Ausgabe',
            amount=amount,
            category='Test',
            description=f'Amount_{amount}'
        )

        assert expected_amount_str in filename, f"Amount {amount} should format to {expected_amount_str}"
