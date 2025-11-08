# Buchhaltungs-App - Projektdokumentation

**Zweck**: Automatisierte Buchhaltung für Freiberufler/Künstler mit OCR und KI-gestützter Dokumentenverarbeitung

**Status**: Funktionsfähig, in Entwicklung
**Letzte Aktualisierung**: 2. November 2025

---

## 📋 Übersicht

Diese App ist eine **Flask-basierte Web-Anwendung** zur automatischen Verarbeitung von Rechnungen und Einnahmenbelegen. Sie wurde speziell für Freiberufler und Künstler entwickelt, die mehrere Geschäftsbereiche verwalten müssen.

### Hauptfunktionen

1. **Multi-Business-Verwaltung**: Verwalte mehrere Geschäftsbereiche/Projekte getrennt
2. **Automatische OCR-Verarbeitung**: Extrahiert Text aus PDFs und Bildern
3. **KI-gestützte Datenextraktion**: Verwendet Ollama LLM für intelligente Extraktion
4. **Auto-Processing**: Background Worker überwacht Inbox-Ordner automatisch
5. **Paperless-Style Archivierung**: Automatisches Sortieren nach Jahr/Kategorie
6. **EAR-System**: Einnahmen-Ausgaben-Rechnung mit laufender Bilanz

---

## 🏗️ Projekt-Struktur

```
Buchhaltung/
├── Inbox/                          # Eingangsordner für neue Dokumente
│   └── [BusinessName]/             # Pro Geschäftsbereich
│       ├── Einnahmen/              # Eingangsrechnungen
│       └── Ausgaben/               # Ausgaben-Belege
│
├── Archive/                        # Archiv für verarbeitete Dokumente
│   └── [Year]/                     # Jahr-basierte Organisation
│       ├── Einnahmen/              # Archivierte Einnahmen
│       └── Ausgaben/               # Archivierte Ausgaben
│
└── app/                            # Flask-Anwendung
    ├── app.py                      # Haupt-App (Flask Routes)
    ├── database.py                 # SQLite Datenbank-Interface
    ├── auto_processor.py           # Background Worker
    ├── ocr_processor.py            # OCR für Ausgaben
    ├── income_processor.py         # OCR für Einnahmen
    ├── llm_extractor.py            # LLM-basierte Extraktion
    ├── folder_manager.py           # Ordnerstruktur-Verwaltung
    ├── image_converter.py          # Bild → PDF Konvertierung
    ├── excel_export.py             # Excel-Export
    ├── invoices.db                 # SQLite Datenbank
    ├── templates/                  # HTML Templates
    └── static/                     # CSS/JS/Assets
```

---

## 🔧 Technologie-Stack

### Backend
- **Flask 3.0+**: Web-Framework
- **SQLite**: Datenbank (über `sqlite3`)
- **Pytesseract**: OCR-Engine
- **Ollama**: Lokales LLM (gemma3:27b)
- **Pillow**: Bildverarbeitung
- **pdf2image**: PDF zu Bild Konvertierung

### Frontend
- **HTML/CSS/JavaScript**: Klassisches Server-Side Rendering
- **Bootstrap-ähnliches Design**: Responsives Layout

### Dependencies
```
Flask>=3.0.0
pytesseract>=0.3.10
Pillow>=10.4.0
pdf2image>=1.17.0
openpyxl>=3.1.0
python-dateutil>=2.8.0
ollama>=0.1.0
```

---

## 📊 Datenbank-Schema

### Table: `businesses`
Speichert Geschäftsbereiche (z.B. "Medienkunst", "Fotografie")

```sql
CREATE TABLE businesses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,              -- z.B. "Medienkunst"
    prefix TEXT NOT NULL UNIQUE,            -- z.B. "MK"
    color TEXT DEFAULT '#007AFF',           -- UI-Farbe
    inbox_path TEXT,                        -- Pfad zum Inbox-Ordner
    archive_path TEXT,                      -- Pfad zum Archive-Ordner
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

### Table: `invoices`
Zentrale Tabelle für alle Dokumente (Einnahmen + Ausgaben)

```sql
CREATE TABLE invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id INTEGER,                    -- Zuordnung zu Business
    file_path TEXT NOT NULL UNIQUE,         -- Aktueller Dateipfad
    original_filename TEXT NOT NULL,
    invoice_id TEXT,                        -- ARE-MK-2025001 oder ERE-MK-2025001

    -- Basis-Daten
    date TEXT,                              -- YYYY-MM-DD
    amount REAL,
    category TEXT,
    description TEXT,
    ocr_text TEXT,                          -- Kompletter OCR-Text

    -- Status-Flags
    reviewed BOOLEAN DEFAULT 0,             -- Manuell geprüft?
    processed BOOLEAN DEFAULT 0,            -- Verarbeitet?
    is_archived BOOLEAN DEFAULT 0,          -- Im Archive?
    flagged BOOLEAN DEFAULT 0,              -- Markiert?

    -- Einnahmen-spezifische Felder
    invoice_number TEXT,                    -- Rechnungsnummer
    customer_name TEXT,
    customer_address TEXT,
    payment_due_date TEXT,
    payment_terms TEXT,
    tax_rate REAL,
    tax_amount REAL,
    net_amount REAL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (business_id) REFERENCES businesses(id)
)
```

**Wichtig**:
- `invoice_id` mit Präfix **ARE** = Ausgaben (Ausgaben-Rechnung-Eingang)
- `invoice_id` mit Präfix **ERE** = Einnahmen (Einnahmen-Rechnung-Eingang)
- Format: `ARE-{PREFIX}-{YEAR}{NUMBER}` z.B. `ARE-MK-2025001`

---

## 🤖 Auto-Processing Workflow

Der `AutoProcessor` ist ein Background-Worker der kontinuierlich läuft:

### 1. Überwachung (alle 10 Sekunden)
```python
check_interval = 10  # Sekunden
```

### 2. Für jedes neue Dokument:

#### Schritt 1: Bild-Konvertierung
```python
if is_image(file):
    convert_to_pdf(file)  # HEIC/JPG → PDF
    delete_original()
```

#### Schritt 2: Dokumenttyp-Erkennung
- Basiert auf Ordner: `Einnahmen/` oder `Ausgaben/`
- Bestimmt welcher Processor verwendet wird

#### Schritt 3: OCR + KI-Extraktion
```python
# Für Ausgaben
ocr_processor.process_file()
    → Tesseract OCR (deu+eng)
    → LLM Extraktion (gemma3:27b)
    → Fallback: Regex-Pattern

# Extrahiert:
- Datum (YYYY-MM-DD)
- Betrag (float)
- Beschreibung (String)
- Kategorie (aus vordefinierter Liste)
```

#### Schritt 4: Automatische Archivierung
```python
if alle_pflichtfelder_vorhanden(datum, betrag, kategorie):
    # Generiere Invoice-ID
    invoice_id = generate_id()  # ARE-MK-2025001

    # Verschiebe nach Archive
    move_to: Archive/{YEAR}/{Einnahmen|Ausgaben}/

    # Markiere als reviewed=True, processed=True
else:
    # Bleibt in Inbox für manuelle Überprüfung
    reviewed=False, processed=True
```

### Kategorien

**Ausgaben**:
- Büro (Hardware, Software, Bürobedarf)
- Raum (Miete, Nebenkosten)
- Telefon (Internet, Mobilfunk)
- Fahrtkosten (Benzin, Bahn, Taxi)
- Fortbildung (Kurse, Bücher)
- Versicherung
- Porto (Versand)
- Werbung (Marketing)
- Sonstiges

**Einnahmen**:
- Honorar (Haupteinnahmequelle)
- Lizenzgebühren
- Workshops
- Stipendien
- Verkäufe
- Sonstiges

---

## 🔍 LLM-Integration (Ollama)

### Setup
```bash
# Installation
brew install ollama  # macOS
ollama serve         # Server starten

# Model herunterladen
ollama pull gemma3:27b
```

### Verwendung in der App

Die App verwendet **gemma3:27b** für intelligente Extraktion:

```python
# llm_extractor.py
class LLMExtractor:
    def __init__(self, model='gemma3:27b'):
        self.model = model
```

**Warum gemma3:27b?**
- Bessere Genauigkeit als llama3.2:3b
- Versteht Kontext (Netto vs. Brutto)
- Robuste JSON-Ausgabe
- ~27GB Model-Größe

**Fallback**: Falls Ollama nicht verfügbar, nutzt die App Regex-basierte Extraktion

### Prompt-Beispiel (Ausgaben)
```
Du bist ein Experte für die Analyse von Rechnungen.
Extrahiere folgende Informationen aus dem OCR-Text:

OCR TEXT:
[...]

Extrahiere:
1. Rechnungsdatum (Format: YYYY-MM-DD)
2. Gesamtbetrag (nur Zahl, z.B. 29.99)
3. Kurze Beschreibung (max 30 Zeichen)
4. Kategorie (wähle aus: Büro, Raum, Telefon, ...)

Antworte NUR mit einem JSON-Objekt:
{
  "date": "YYYY-MM-DD",
  "amount": 0.00,
  "description": "...",
  "category": "..."
}
```

---

## 🌐 Flask Routes

### Dashboard & Übersicht
- `GET /` → Dashboard mit Statistiken
- `GET /stats` → Detaillierte Statistiken
- `GET /documents` → EAR-Tabelle (alle Dokumente)

### Ausgaben-Management
- `GET /expenses` → Ausgaben-Inbox
- `POST /process/<file_id>` → Manuell OCR starten
- `GET /review` → Überprüfungs-Seite
- `POST /api/invoice/<file_id>` → Rechnung aktualisieren
- `DELETE /api/invoice/<file_id>` → Rechnung löschen

### Einnahmen-Management
- `GET /income` → Einnahmen-Inbox
- `POST /income/process/<file_id>` → OCR für Einnahme
- `POST /api/income/<file_id>` → Einnahme aktualisieren

### Business-Verwaltung
- `GET /settings` → Einstellungen
- `GET /api/businesses` → Liste aller Businesses
- `POST /api/businesses` → Neues Business erstellen
- `PUT /api/businesses/<id>` → Business aktualisieren
- `DELETE /api/businesses/<id>` → Business löschen

### Unified Inbox
- `GET /inbox` → Alle Dokumente aller Businesses
- `GET /api/inbox` → API für Inbox-Daten
- `POST /api/inbox/scan` → Manuelle Inbox-Scan

### Auto-Processor
- `GET /api/auto-processor/status` → Status des Workers
- `POST /api/auto-processor/toggle` → Start/Stop Worker

### Export
- `GET /export/excel` → Excel-Export aller Dokumente

### Datei-Verwaltung
- `GET /file/<file_id>` → Datei-Vorschau (PDF/Bild)
- `POST /api/invoice/<file_id>/flag` → Dokument markieren

---

## 💾 Datenfluss-Beispiel

### Szenario: Neue Rechnung landet in Inbox

```
1. Datei landet in: Inbox/Medienkunst/Ausgaben/laptop.pdf

2. Auto-Processor erkennt neue Datei (alle 10s)
   → Fügt zu DB hinzu: invoices.add_file()
   → business_id = 1 (Medienkunst)

3. OCR-Verarbeitung
   → ocr_processor.process_file('laptop.pdf')
   → Tesseract extrahiert Text
   → LLM analysiert Text

   Ergebnis:
   {
     'date': '2025-11-02',
     'amount': 1299.99,
     'description': 'MacBook Pro 14"',
     'category': 'Büro'
   }

4. Datenbank-Update
   → db.update_ocr_results(file_id, result)
   → processed = True
   → reviewed = True (weil alle Felder vorhanden)

5. Invoice-ID generieren
   → get_next_invoice_id(year=2025, business_id=1)
   → Ergebnis: "ARE-MK-2025001"

6. Auto-Archivierung
   Von: Inbox/Medienkunst/Ausgaben/laptop.pdf
   Nach: Archive/2025/Ausgaben/laptop.pdf

   → file_path in DB aktualisiert
   → is_archived = True

7. Status: ✅ Fertig archiviert
```

### Bei unvollständiger Extraktion:
```
Falls date ODER amount ODER category fehlt:
  → reviewed = False
  → Dokument bleibt in Inbox
  → Erscheint in Review-Seite für manuelle Korrektur
  → Badge-Counter in UI wird erhöht
```

---

## 🎨 Business-Konzept

Die App unterstützt **mehrere getrennte Geschäftsbereiche**:

### Beispiel-Setup
```
Business 1:
  Name: "Medienkunst"
  Prefix: "MK"
  Color: #007AFF

  Invoice-IDs: ARE-MK-2025001, ARE-MK-2025002, ...
                ERE-MK-2025001, ERE-MK-2025002, ...

Business 2:
  Name: "Fotografie"
  Prefix: "FT"
  Color: #FF3B30

  Invoice-IDs: ARE-FT-2025001, ARE-FT-2025002, ...
```

### Vorteile
- ✅ Getrennte Buchhaltung pro Business
- ✅ Einzigartige Invoice-IDs
- ✅ Separate Ordnerstruktur
- ✅ Filterbare Statistiken
- ✅ Business-spezifischer Export

---

## 📱 UI-Seiten

### 1. Dashboard (`dashboard_new.html`)
- Übersicht: Einnahmen, Ausgaben, Profit
- Monat/Jahr Statistiken
- Kategorien-Charts
- Recent Activity
- Business-Filter

### 2. Expenses Inbox (`inbox_expenses.html`)
- Liste aller Ausgaben-Belege
- Status-Anzeige (processed, reviewed, archived)
- Quick-Edit Funktionen
- Inline-PDF-Vorschau
- Batch-Operations

### 3. Income Inbox (`inbox_income.html`)
- Analog zu Expenses
- Einnahmen-spezifische Felder
- Kunden-Daten

### 4. Unified Inbox (`inbox_unified.html`)
- Alle Dokumente aller Businesses
- Multi-Business-Ansicht
- Auto-refresh
- Drag & Drop Upload (geplant)

### 5. EAR-Tabelle (`ear_table.html`)
- Einnahmen-Ausgaben-Rechnung
- Laufende Bilanz
- Filter nach Datum/Kategorie/Business
- Export-Funktion

### 6. Settings (`settings.html`)
- Business-Verwaltung
- Auto-Processor Settings
- Ordner-Konfiguration

---

## 🔐 Wichtige Design-Entscheidungen

### 1. Warum eine zentrale `invoices` Tabelle?
Statt separate Tabellen für Einnahmen/Ausgaben:
- **Einfachere EAR-Berechnung** (eine Query)
- **Gemeinsame ID-Sequenz** pro Business
- **Flexibilität** für spätere Erweiterungen
- Unterscheidung über `invoice_id` Präfix (ARE/ERE)

### 2. Warum Paperless-Style?
- **Automatische Organisation** nach Jahr
- **Keine manuellen Ordner** notwendig
- **Skalierbar** über Jahre hinweg
- Analog zu bewährten DMS-Systemen

### 3. Warum lokales LLM (Ollama)?
- **Datenschutz**: Alles offline/lokal
- **Kosten**: Keine API-Kosten
- **Performance**: Nach erstem Load sehr schnell
- **Offline**: Keine Internet-Abhängigkeit

### 4. Warum Background Worker?
- **User-Friendly**: Keine manuelle Verarbeitung nötig
- **Responsive**: UI blockiert nicht
- **Skalierbar**: Kann viele Dateien verarbeiten
- **Flexibel**: Kann gestoppt/gestartet werden

---

## 🚀 Deployment & Setup

### Erstmaliges Setup
```bash
# 1. Repository klonen/öffnen
cd /Users/denis/Developer/Buchhaltung

# 2. Virtual Environment
cd app
python3 -m venv venv
source venv/bin/activate

# 3. Dependencies installieren
pip install -r requirements.txt

# 4. Tesseract installieren (macOS)
brew install tesseract
brew install tesseract-lang  # Deutsche Sprache

# 5. Ollama setup (optional, empfohlen)
brew install ollama
ollama serve &
ollama pull gemma3:27b

# 6. App starten
python app.py

# Server läuft auf: http://localhost:5000
```

### Ordnerstruktur initialisieren
```bash
# Automatisch beim ersten Start oder via Settings-Page:
# - Erstellt Inbox/Archive Ordner
# - Erstellt Business-Ordner
# - Initialisiert Datenbank
```

---

## 🧪 Testing

Testdateien unter `app/test/`:
- `test_basic_functionality.py` - Basis-Tests
- `test_document_processing.py` - OCR/Processing Tests

```bash
# Tests ausführen
python -m pytest app/test/
```

---

## 📈 Performance-Hinweise

### OCR-Geschwindigkeit
- **Erster Durchlauf**: ~5-10 Sekunden (LLM Model lädt)
- **Weitere Dokumente**: ~2-3 Sekunden pro Dokument
- **Ohne LLM (Regex)**: ~0.5 Sekunden

### Datenbank
- SQLite für kleine bis mittlere Datenmenge (~10.000 Dokumente)
- Bei größeren Mengen: Migration zu PostgreSQL empfohlen

### Auto-Processor
- Check-Intervall: 10 Sekunden (anpassbar)
- Threading: Blockiert nicht den Flask-Server
- RAM: ~4-6 GB mit LLM geladen

---

## 🔮 Geplante Features / TODOs

### High Priority
- [ ] PDF-Vorschau direkt im Browser verbessern
- [ ] Bulk-Upload via Drag & Drop
- [ ] Export-Templates (CSV, DATEV)
- [ ] Suche über OCR-Text

### Medium Priority
- [ ] Email-Import (Rechnungen per Mail)
- [ ] Kategorie-Learning (ML für bessere Auto-Kategorisierung)
- [ ] Mobile-Responsive Design verbessern
- [ ] Benachrichtigungen bei neuen Dokumenten

### Low Priority
- [ ] Multi-User Support
- [ ] Cloud-Sync (Nextcloud/Dropbox)
- [ ] REST API für externe Tools
- [ ] Docker Container

---

## 🐛 Bekannte Probleme

### 1. HEIC-Bilder
- Müssen erst zu PDF konvertiert werden
- ImageConverter kümmert sich automatisch darum

### 2. OCR bei schlechter Qualität
- Regex-Fallback oft unzuverlässig
- Lösung: Bessere Scans/Fotos verwenden

### 3. Datum-Parsing
- Europäische Datumsformate manchmal problematisch
- LLM hilft, aber nicht 100% sicher

### 4. Business-Löschen
- Nur möglich wenn keine Rechnungen zugeordnet
- Sicherheits-Feature

---

## 📚 Code-Referenzen für Agents

### Wichtige Funktionen

#### Neue Rechnung verarbeiten
```python
# File: auto_processor.py:86
def _auto_process_file(file_id, business, doc_type_folder):
    # Kompletter Workflow von OCR bis Archivierung
```

#### Invoice-ID generieren
```python
# File: database.py:265
def get_next_invoice_id(year=None, business_id=None):
    # Format: ARE-{PREFIX}-{YEAR}{NUMBER}
```

#### OCR + LLM Extraktion
```python
# File: ocr_processor.py:27
def process_file(file_path):
    # 1. OCR via Tesseract
    # 2. LLM Extraktion
    # 3. Fallback Regex
```

#### Business erstellen
```python
# File: folder_manager.py:23
def create_business_folders(business_name):
    # Erstellt Inbox + Archive Struktur
```

---

## 🎯 Für zukünftige Code-Agenten

### Wenn du etwas ändern/hinzufügen willst:

1. **Datenbank-Schema**: Siehe `database.py:14` - `init_db()`
2. **Routes**: Alle in `app.py` definiert
3. **OCR-Logik**: `ocr_processor.py` (Ausgaben) und `income_processor.py` (Einnahmen)
4. **Auto-Processing**: `auto_processor.py` - Background Worker
5. **UI**: Templates in `templates/`, Base-Template: `base_new.html`

### Konventionen:
- **Invoice-IDs**: Immer mit Präfix `ARE-` oder `ERE-`
- **Datumsformat**: Immer `YYYY-MM-DD` in DB
- **File-Paths**: Absolute Pfade in DB speichern
- **Business-Filter**: Alle Listen-Queries sollten business_id unterstützen

### Testing:
- Neue Features immer mit Test-Dokumenten testen
- Auto-Processor kann via API gestoppt werden für Debug
- LLM kann über `use_llm=False` deaktiviert werden

---

## 📞 Kontakt & Support

**Entwickelt für**: Freiberufler, Künstler, Selbstständige
**Lizenz**: Private/Educational Use
**Python Version**: 3.14+
**Framework**: Flask 3.0+

---

**Ende der Dokumentation** - Viel Erfolg bei der Weiterentwicklung!
