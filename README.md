# lead-scraping

Franchise-Lead-Enrichment: Daten von Franchise-Webseiten recherchieren und in Airtable anreichern.

## Setup

Erstelle eine `.env`-Datei im Root-Verzeichnis:

```env
close_api_key=DEIN_CLOSE_API_KEY
airtable_api_key=DEIN_AIRTABLE_API_KEY
```

Dependencies installieren:

```bash
pip install -r requirements.txt
```

Airtable-Felder anlegen (einmalig):

```bash
python airtable_helpers.py setup-fields
```

## Pipeline

Records durchlaufen mehrere Schritte, jeder mit eigenem Status-Tracking in Airtable.

### Schritt 1: Franchise-Validierung

```
/verify-franchise recXXXXXXXXXXXXXX      # Einzelner Record
/verify-franchise batch 10                # 10 offene Records
```

Prüft per Google-Recherche:
- Ist es ein echtes Franchise-System? (0-100% + Begründung)
- Stimmt die Website-URL?
- Wie heißt das Unternehmen offiziell?

### Schritt 2: Impressum-Enrichment

```
/scrape-impressum https://www.example.com  # Einzelne URL
/scrape-impressum recXXXXXXXXXXXXXX       # Einzelner Record
/scrape-impressum batch 10                 # 10 offene Records
```

Extrahiert per Playwright MCP + Claude AI:
- E-Mail, Telefon, Geschäftsführer, Adresse

### Close.com-Sync (separat)

```bash
python sync_to_close.py --dry-run    # Testlauf
python sync_to_close.py              # Import starten
```

## Airtable-Helpers

```bash
python airtable_helpers.py setup-fields       # Felder anlegen
python airtable_helpers.py step1 [limit]      # Records für Schritt 1
python airtable_helpers.py step2 [limit]      # Records für Schritt 2
python airtable_helpers.py list [limit]       # Offene Impressum-Records (Legacy)
python airtable_helpers.py get <record_id>    # Einzelnen Record laden
```

## Dateien

| Datei | Beschreibung |
|-------|-------------|
| `airtable_helpers.py` | Airtable API-Client (Multi-Step, Meta-API, Sicherheitslogik) |
| `sync_to_close.py` | Airtable → Close.com Lead-Import |
| `test_create_lead.py` | Test-Lead in Close erstellen |
| `.claude/skills/verify-franchise/` | Schritt 1: Franchise-Validierung |
| `.claude/skills/scrape-impressum/` | Schritt 2: Impressum-Enrichment |
| `playwright-mcp.config.json` | Playwright-Browser-Konfiguration |
