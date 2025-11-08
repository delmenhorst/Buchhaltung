import ollama
import json
from datetime import datetime

class LLMExtractor:
    """Use Ollama LLM to extract invoice data from OCR text"""

    def __init__(self, model='gemma3:4b'):
        """
        Initialize LLM Extractor

        Args:
            model: Ollama model to use. Recommendations:
                   - gemma3:4b (balanced, good for extraction)
                   - llama3.2:3b (fast, good for extraction)
                   - gemma3:27b (very accurate, slower)
        """
        self.model = model
        self.available = self._check_ollama()

    def _check_ollama(self):
        """Check if Ollama is available and model exists"""
        try:
            # Try to list models
            ollama.list()
            return True
        except Exception as e:
            print(f"⚠️  Ollama not available: {e}")
            print("   Install: https://ollama.com")
            print(f"   Then run: ollama pull {self.model}")
            return False

    def extract_invoice_data(self, ocr_text):
        """
        Extract structured invoice data using LLM with Structured Outputs

        Returns dict with: date, amount, description, category
        """
        if not self.available:
            return None

        # Define JSON schema for structured output
        schema = {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "Rechnungsdatum im Format YYYY-MM-DD"
                },
                "amount": {
                    "type": "number",
                    "description": "Gesamtbetrag als Zahl (z.B. 29.99)"
                },
                "description": {
                    "type": "string",
                    "description": "Kurze Beschreibung (max 30 Zeichen)"
                },
                "category": {
                    "type": "string",
                    "enum": ["Büro", "Raum", "Telefon", "Fahrtkosten", "Fortbildung", "Versicherung", "Porto", "Werbung", "Sonstiges"],
                    "description": "Kategorie der Ausgabe"
                }
            },
            "required": ["date", "amount", "description", "category"]
        }

        prompt = f"""Analysiere folgende Rechnung und extrahiere die wichtigsten Informationen:

OCR TEXT:
{ocr_text[:2000]}

Extrahiere:
- Rechnungsdatum (YYYY-MM-DD)
- Gesamtbetrag (nur Zahl)
- Kurze Beschreibung (was wurde gekauft)
- Kategorie (passende aus der Liste)"""

        try:
            response = ollama.chat(
                model=self.model,
                messages=[{
                    'role': 'user',
                    'content': prompt
                }],
                format=schema,  # ← Structured Output!
                options={
                    'temperature': 0.1,
                }
            )

            # With structured outputs, response is already valid JSON
            data = json.loads(response['message']['content'])

            # Validate and clean data
            return self._validate_extraction(data)

        except Exception as e:
            print(f"⚠️  LLM extraction failed: {e}")
            return None

    def _validate_extraction(self, data):
        """Validate and clean extracted data"""
        result = {}

        # Validate date
        if 'date' in data:
            try:
                datetime.strptime(data['date'], '%Y-%m-%d')  # Validate format
                result['date'] = data['date']
            except:
                result['date'] = None
        else:
            result['date'] = None

        # Validate amount
        if 'amount' in data:
            try:
                amount = float(data['amount'])
                if amount > 0:
                    result['amount'] = amount
                else:
                    result['amount'] = None
            except:
                result['amount'] = None
        else:
            result['amount'] = None

        # Clean description
        if 'description' in data:
            desc = str(data['description']).strip()[:50]
            result['description'] = desc if desc else None
        else:
            result['description'] = None

        # Validate category
        valid_categories = [
            'Büro', 'Raum', 'Telefon', 'Fahrtkosten',
            'Fortbildung', 'Versicherung', 'Porto', 'Werbung', 'Sonstiges'
        ]

        category = data.get('category', 'Sonstiges')
        if category in valid_categories:
            result['category'] = category
        else:
            result['category'] = 'Sonstiges'

        return result

    def extract_income_data(self, ocr_text):
        """
        Extract structured income data using LLM with Structured Outputs

        Returns dict with: date, amount, description, category
        """
        if not self.available:
            return None

        # Define JSON schema for structured output
        schema = {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "Datum im Format YYYY-MM-DD"
                },
                "amount": {
                    "type": "number",
                    "description": "Betrag als Zahl (z.B. 20000.00)"
                },
                "description": {
                    "type": "string",
                    "description": "Kurze Beschreibung (max 30 Zeichen, Projekt/Auftraggeber)"
                },
                "category": {
                    "type": "string",
                    "enum": ["Honorar", "Lizenzgebühren", "Workshops", "Stipendien", "Verkäufe", "Sonstiges"],
                    "description": "Kategorie der Einnahme"
                }
            },
            "required": ["date", "amount", "description", "category"]
        }

        prompt = f"""Analysiere folgenden Einnahmen-Beleg und extrahiere die wichtigsten Informationen:

OCR TEXT:
{ocr_text[:2000]}

Extrahiere:
- Datum (YYYY-MM-DD)
- Betrag (nur Zahl)
- Kurze Beschreibung (Projekt/Auftraggeber)
- Kategorie (passende aus der Liste)"""

        try:
            response = ollama.chat(
                model=self.model,
                messages=[{
                    'role': 'user',
                    'content': prompt
                }],
                format=schema,  # ← Structured Output!
                options={
                    'temperature': 0.1,
                }
            )

            # With structured outputs, response is already valid JSON
            data = json.loads(response['message']['content'])

            # Validate with income categories
            return self._validate_income_extraction(data)

        except Exception as e:
            print(f"⚠️  LLM extraction failed: {e}")
            return None

    def _validate_income_extraction(self, data):
        """Validate and clean extracted income data"""
        result = {}

        # Validate date
        if 'date' in data:
            try:
                datetime.strptime(data['date'], '%Y-%m-%d')  # Validate format
                result['date'] = data['date']
            except:
                result['date'] = None
        else:
            result['date'] = None

        # Validate amount
        if 'amount' in data:
            try:
                amount = float(data['amount'])
                if amount > 0:
                    result['amount'] = amount
                else:
                    result['amount'] = None
            except:
                result['amount'] = None
        else:
            result['amount'] = None

        # Clean description
        if 'description' in data:
            desc = str(data['description']).strip()[:50]
            result['description'] = desc if desc else None
        else:
            result['description'] = None

        # Validate category (income categories)
        valid_categories = [
            'Honorar', 'Lizenzgebühren', 'Workshops',
            'Stipendien', 'Verkäufe', 'Sonstiges'
        ]

        category = data.get('category', 'Sonstiges')
        if category in valid_categories:
            result['category'] = category
        else:
            result['category'] = 'Sonstiges'

        return result

    def is_available(self):
        """Check if LLM is available"""
        return self.available
