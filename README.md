# lead-scraping

Franchise-Lead-Enrichment: Impressum-Daten von Webseiten extrahieren und in Airtable anreichern.

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

## Workflow

### 1. Impressum-Enrichment (interaktiv via Claude Code)

Der Skill `/scrape-impressum` wird direkt im Claude Code Chat genutzt:

```
/scrape-impressum https://www.example.com       # Einzelne URL
/scrape-impressum recXXXXXXXXXXXXXX             # Einzelner Airtable-Record
/scrape-impressum batch 10                       # 10 offene Records abarbeiten
```

**Ablauf pro Record:**
1. Playwright MCP navigiert zur Website und findet die Impressum-Seite
2. Claude analysiert den Seiteninhalt und extrahiert E-Mail, Telefon, Geschäftsführer, Adresse
3. Ergebnisse werden angezeigt und nach Bestätigung in Airtable geschrieben

### 2. Close.com-Sync (separater Schritt)

Importiert angereicherte Leads aus Airtable nach Close CRM:

```bash
python sync_to_close.py --dry-run    # Testlauf
python sync_to_close.py              # Import starten
```

## Dateien

| Datei | Beschreibung |
|-------|-------------|
| `airtable_helpers.py` | Airtable API-Client (Lesen, Schreiben, Sicherheitslogik) |
| `sync_to_close.py` | Airtable → Close.com Lead-Import |
| `test_create_lead.py` | Test-Lead in Close erstellen |
| `.claude/skills/scrape-impressum/` | Skill-Definition für den Enrichment-Workflow |
| `playwright-mcp.config.json` | Playwright-Browser-Konfiguration |
