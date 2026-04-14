# Lead Scraping – Projektregeln

## KRITISCH: Keine Daten löschen

Dieses Projekt arbeitet mit API Keys, die Admin-Zugriff auf **Close.com** und **Airtable** haben.

### Verbotene Aktionen

- **Keine DELETE-Requests** an Close.com oder Airtable APIs – weder direkt (curl, requests, fetch) noch in Scripts
- **Keine Bulk-Löschungen** oder Bulk-Updates ohne explizite User-Bestätigung
- **Keine destruktiven API-Calls**: Dazu zählen auch Archivieren, Merge oder Überschreiben von bestehenden Datensätzen
- **Keine API Keys in Code, Commits, Logs oder Ausgaben** – Keys gehören ausschließlich in `.env`

### Erlaubte Aktionen

- **GET-Requests** (Lesen) – immer erlaubt
- **POST-Requests** (Erstellen) – erlaubt, aber bei Bulk-Operationen vorher bestätigen lassen
- **PATCH/PUT-Requests** (Aktualisieren) – nur nach expliziter User-Bestätigung und nur für einzelne Felder, nie ganze Records überschreiben

### Vor jeder schreibenden Aktion

1. Zeige dem User genau, welche Daten geschrieben/geändert werden
2. Nutze `--dry-run` wo möglich, bevor echte Änderungen gemacht werden
3. Bei Bulk-Operationen: Erst eine kleine Stichprobe, dann den Rest

## Projekt-Architektur

### Multi-Step-Pipeline

Records durchlaufen mehrere Schritte, jeder mit eigenem Status-Feld:

| Schritt | Skill | Status-Feld |
|---------|-------|-------------|
| 1. Validierung | `/verify-franchise` | `Schritt 1: Validierung` |
| 2. Impressum | `/scrape-impressum` | `Schritt 2: Impressum` |
| 3. Ansprechpartner | `/find-contacts` | `Schritt 3: Ansprechpartner` |
| 4. Portal-Kontakte | `/find-portal-contacts` | `Schritt 4: Portal-Kontakte` |

Status-Werte: leer (offen) → "In Bearbeitung" → "Erfolgreich" / "Mit Problemen"

Schritt 4 schreibt die in Franchise-Portalen gelisteten Ansprechpartner als JSON in `Franchise Portal Ansprechpartner` und wird **nicht** nach Close gesynct. Voraussetzung: `Schritt 1: Validierung = Erfolgreich`.

### Tools & Infrastruktur

- **WebSearch** für Google-Recherche (primär, kein Playwright für Google — wird geblockt)
- **Apify Google SERP Scraper** als Fallback wenn WebSearch fehlschlägt
- **Playwright MCP** navigiert zu konkreten Webseiten und liest Seiteninhalte
- **Claude AI** analysiert Inhalte direkt im Chat
- **airtable_helpers.py** liest/schreibt Airtable-Records (mit Sicherheitslogik)

Playwright darf nur für öffentliche Webseiten genutzt werden — nie für Logins oder Admin-Panels.

### Close.com-Sync (separater Schritt)

`sync_to_close.py` importiert angereicherte Leads nach Close CRM — wird separat ausgeführt.

## API-Konfiguration

- Close.com API Key: `close_api_key` in `.env`
- Airtable API Key: `airtable_api_key` in `.env`
- Apify API Key: `apify_api_key` in `.env` (Fallback für Google-Suche)
- Close.com und Airtable Keys haben **Admin-Zugriff** – entsprechend vorsichtig behandeln
