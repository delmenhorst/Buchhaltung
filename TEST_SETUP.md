# Test-Setup für die Buchhaltungs-App

Dieses Dokument beschreibt, wie Sie die App schnell für Tests zurücksetzen können.

## Schnellstart

### 1. Datenbank zurücksetzen (ohne Test-Invoices)

```bash
python reset_test_db.py
```

Dies erstellt:
- 2 Test-Businesses (Medienkunst, Fotografie)
- 3 wiederkehrende Buchungen (Miete, Internet, Versicherung)
- Alle rückwirkenden Buchungen seit Jahresbeginn

### 2. Datenbank zurücksetzen (mit Test-Invoices)

```bash
python reset_test_db.py --load-invoices
```

Dies macht das Gleiche wie Option 1, plus:
- Lädt alle PDFs aus dem `test_invoices/` Ordner

## Test-Invoices Ordnerstruktur

Legen Sie Ihre Test-PDFs in diese Ordner:

```
test_invoices/
├── Medienkunst/
│   ├── Ausgaben/
│   │   ├── rechnung1.pdf
│   │   ├── rechnung2.pdf
│   │   └── ...
│   └── Einnahmen/
│       ├── honorar1.pdf
│       └── ...
└── Fotografie/
    ├── Ausgaben/
    │   └── ...
    └── Einnahmen/
        └── ...
```

## Was wird erstellt?

### Businesses

| Name | Prefix | Farbe |
|------|--------|-------|
| Medienkunst | MK | Rot (#FF6B6B) |
| Fotografie | FT | Türkis (#4ECDC4) |

### Wiederkehrende Buchungen

#### Medienkunst (MK)
1. **Ateliermiete**
   - Betrag: 450,00 €
   - Kategorie: Raum
   - Frequenz: Monatlich (1. des Monats)
   - Start: 01.01.2025

2. **Internet & Telefon**
   - Betrag: 39,99 €
   - Kategorie: Telefon
   - Frequenz: Monatlich (15. des Monats)
   - Start: 01.01.2025

#### Fotografie (FT)
1. **Berufshaftpflichtversicherung**
   - Betrag: 120,00 €
   - Kategorie: Versicherung
   - Frequenz: Quartalsweise (1. des Monats)
   - Start: 01.01.2025

## Nach dem Reset

1. Starten Sie die App:
   ```bash
   cd app
   source venv/bin/activate
   python app.py
   ```

2. Öffnen Sie http://localhost:5000

3. Sie sollten sehen:
   - Alle wiederkehrenden Buchungen seit Jahresbeginn im EAR-Tab
   - Alle Test-Invoices im Inbox (falls --load-invoices verwendet)
   - Die App ist bereit zum Testen!

## Tipps

- **Schnelles Testen**: Nach jedem größeren Test einfach `python reset_test_db.py` ausführen
- **Test-PDFs sammeln**: Legen Sie echte Rechnungen in `test_invoices/` ab, um realistische Tests zu haben
- **Git ignoriert**: Die Test-PDFs werden nicht ins Git-Repository committed (.gitignore)

## Workflow für Entwicklung

1. Änderungen am Code vornehmen
2. `python reset_test_db.py --load-invoices` ausführen
3. App testen
4. Wiederholen bis alles funktioniert
5. Git commit erstellen

## Fehlerbehebung

**Problem**: Script findet Module nicht
```bash
# Lösung: Virtual Environment aktivieren
cd app
source venv/bin/activate
cd ..
python reset_test_db.py
```

**Problem**: Datenbank ist gesperrt
```bash
# Lösung: App beenden, dann reset
# Ctrl+C im Terminal wo die App läuft
python reset_test_db.py
```
