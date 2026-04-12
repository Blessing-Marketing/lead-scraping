# lead-scraping

Franchise-Lead-Enrichment: Daten von Franchise-Webseiten recherchieren und in Airtable anreichern. Läuft als Chat-basierter Workflow mit Claude Code Skills.

## Setup

Erstelle eine `.env`-Datei im Root-Verzeichnis:

```env
close_api_key=DEIN_CLOSE_API_KEY
airtable_api_key=DEIN_AIRTABLE_API_KEY
apify_api_key=DEIN_APIFY_API_KEY
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

Records durchlaufen mehrere Schritte, jeder mit eigenem Status-Tracking in Airtable:

| Schritt | Skill | Status-Feld | Funktion |
|---------|-------|-------------|----------|
| 1 | `/verify-franchise` | `Schritt 1: Validierung` | Franchise verifizieren, Website prüfen, Firmennamen finden |
| 2 | `/scrape-impressum` | `Schritt 2: Impressum` | E-Mail, Telefon, Geschäftsführer, Adresse extrahieren |

Status-Werte: leer (offen) → "In Bearbeitung" → "Erfolgreich" / "Mit Problemen"

### Schritt 1: Franchise-Validierung

```
/verify-franchise recXXXXXXXXXXXXXX      # Einzelner Record
/verify-franchise batch                   # Alle offenen Records
```

Prüft per WebSearch + Playwright:
- Ist es ein echtes Franchise-System? (0-100% + Begründung)
- Stimmt die Website-URL?
- Wie heißt das Unternehmen offiziell?
- Zusammenfassung, Standorte, Mitarbeiter, Gründungsdatum, Portal-URLs

### Schritt 2: Impressum-Enrichment

```
/scrape-impressum https://www.example.com  # Einzelne URL
/scrape-impressum recXXXXXXXXXXXXXX       # Einzelner Record
/scrape-impressum batch                    # Alle offenen Records
```

Extrahiert per Playwright MCP + Claude AI:
- E-Mail, Telefon, Geschäftsführer, Adresse

### Close.com-Sync (separat)

```bash
python sync_to_close.py --dry-run    # Testlauf
python sync_to_close.py              # Import starten
```

## Parallele Verarbeitung

Mehrere Claude-Code-Instanzen können gleichzeitig am selben Airtable arbeiten. Die Architektur verhindert Doppel-Verarbeitung:

- **Claim-Mechanismus**: `claim1`/`claim2` holt kleine Batches (4 Records) und setzt sofort "In Bearbeitung" — andere Instanzen sehen diese Records nicht mehr
- **Playwright-Isolation**: `launch-playwright-mcp.sh` erstellt pro Session ein eigenes Chromium-Profil unter `/tmp/`
- **Crash-sicher**: Bei Abbruch max. 4 Records in "In Bearbeitung" stecken — in Airtable manuell zurücksetzen

So startest du 3 parallele Instanzen: Einfach 3 Claude-Code-Chats öffnen und jeweils `/verify-franchise batch` eingeben.

## Airtable-Helpers

```bash
python airtable_helpers.py step1 [limit]                    # Records für Schritt 1 anzeigen (read-only)
python airtable_helpers.py step2 [limit]                    # Records für Schritt 2 anzeigen (read-only)
python airtable_helpers.py claim1 [count]                   # Records für Schritt 1 claimen (default: 4)
python airtable_helpers.py claim2 [count]                   # Records für Schritt 2 claimen (default: 4)
python airtable_helpers.py write <id> '<json>' '<step>' '<status>'  # Record schreiben
python airtable_helpers.py get <record_id>                  # Einzelnen Record laden
python airtable_helpers.py setup-fields                     # Felder anlegen
python airtable_helpers.py list [limit]                     # Offene Impressum-Records (Legacy)
```

## Dateien

| Datei | Beschreibung |
|-------|-------------|
| `airtable_helpers.py` | Airtable API-Client (Claim, Write, Multi-Step, Meta-API) |
| `sync_to_close.py` | Airtable → Close.com Lead-Import |
| `launch-playwright-mcp.sh` | Wrapper: isoliertes Chromium-Profil pro Session |
| `playwright-mcp.config.json` | Playwright-Browser-Konfiguration (Basis-Config) |
| `.claude/skills/verify-franchise/` | Schritt 1: Franchise-Validierung |
| `.claude/skills/scrape-impressum/` | Schritt 2: Impressum-Enrichment |
| `test_create_lead.py` | Test-Lead in Close erstellen |
