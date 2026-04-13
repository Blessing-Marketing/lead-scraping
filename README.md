# Lead Scraping

Franchise-Lead-Enrichment-Pipeline: Franchise-Unternehmen recherchieren, Daten anreichern (Airtable) und nach Close.com CRM exportieren. Läuft als Chat-basierter Workflow mit Claude Code Skills.

## Setup

### Voraussetzungen

- Python 3.9+
- Claude Code mit Playwright MCP
- API-Keys für Airtable, Close.com und Apify

### Installation

1. `.env`-Datei im Root-Verzeichnis erstellen:

```env
close_api_key=DEIN_CLOSE_API_KEY
airtable_api_key=DEIN_AIRTABLE_API_KEY
apify_api_key=DEIN_APIFY_API_KEY
```

2. Dependencies installieren:

```bash
pip install -r requirements.txt
```

3. Airtable-Felder anlegen (einmalig):

```bash
python airtable_helpers.py setup-fields
```

## Pipeline-Übersicht

Records durchlaufen 3 Enrichment-Schritte und werden anschließend nach Close.com exportiert:

```
Airtable (Rohdaten)
  │
  ├─ Schritt 1: Franchise-Validierung    (/verify-franchise)
  ├─ Schritt 2: Impressum-Enrichment     (/scrape-impressum)
  ├─ Schritt 3: Ansprechpartner-Recherche (/find-contacts)
  │
  └─ Close.com-Export                     (sync_to_close.py)
```

Jeder Schritt hat ein eigenes Status-Feld in Airtable:

| Schritt | Skill | Status-Feld | Funktion |
|---------|-------|-------------|----------|
| 1 | `/verify-franchise` | `Schritt 1: Validierung` | Franchise verifizieren, Website prüfen, Firmennamen finden |
| 2 | `/scrape-impressum` | `Schritt 2: Impressum` | E-Mail, Telefon, Geschäftsführer, Adresse extrahieren |
| 3 | `/find-contacts` | `Schritt 3: Ansprechpartner` | Leitende Ansprechpartner recherchieren |

Status-Werte: leer (offen) → `"In Bearbeitung"` → `"Erfolgreich"` / `"Mit Problemen"`

Jeder Schritt baut auf dem vorherigen auf:
- Schritt 2 verarbeitet nur Records mit Schritt 1 = `"Erfolgreich"`
- Schritt 3 verarbeitet nur Records mit Schritt 2 = `"Erfolgreich"`
- Close-Export verarbeitet nur Records mit Schritt 3 = `"Erfolgreich"`

## Schritt 1: Franchise-Validierung

```
/verify-franchise recXXXXXXXXXXXXXX      # Einzelner Record
/verify-franchise batch                   # Alle offenen Records
```

Prüft per WebSearch + Playwright:
- Ist es ein echtes Franchise-System? (0–100% Score + Begründung)
- Stimmt die Website-URL?
- Wie heißt das Unternehmen offiziell? (verifizierter Unternehmensname)
- Zusammenfassung (kurz + lang), Anzahl Standorte, Mitarbeiter, Gründungsdatum
- Franchise-Portal-URLs

**Airtable-Felder die geschrieben werden:**
`Unternehmensname`, `Webseite (https-Standardisiert)`, `Ist es ein Franchise-System?`, `Ist es ein Franchise-System? Begründung`, `Zusammenfassung (kurz)`, `Zusammenfassung (lang)`, `Anzahl Standorte`, `Anzahl Mitarbeiter`, `Gründungsdatum`, `Franchise-Portal URLs`

## Schritt 2: Impressum-Enrichment

```
/scrape-impressum https://www.example.com  # Einzelne URL
/scrape-impressum recXXXXXXXXXXXXXX       # Einzelner Record
/scrape-impressum batch                    # Alle offenen Records
```

Extrahiert per Playwright MCP + Claude AI:
- E-Mail-Adresse (Impressum/Kontakt)
- Telefonnummer
- Geschäftsführer (werden in AP-Slots geschrieben)
- Adresse (Straße, PLZ, Stadt)

**Airtable-Felder die geschrieben werden:**
`Impressum Mail`, `Impressum Tel.`, `AP 1`–`AP 5` + Positionen, `Adresse`, `Postleitzahl`, `Stadt`

## Schritt 3: Ansprechpartner-Recherche

```
/find-contacts recXXXXXXXXXXXXXX      # Einzelner Record
/find-contacts batch [limit]           # Offene Records verarbeiten
```

Recherchiert leitende Ansprechpartner per WebSearch + Playwright + Apify:
- Geschäftsführer, Franchise-/Expansions-/Marketing-/Recruiting-Leiter
- E-Mail-Adressen und Telefon-Durchwahlen
- Weitere Telefonnummern (Abteilungen, Hotlines)
- Vertriebsrelevante Infos zum Unternehmen

**Airtable-Felder die geschrieben werden:**
`AP 1`–`AP 5` (+ Mail, Tel., Position), `Weitere Ansprechpartner` (JSON), `Weitere Telefonnummern` (JSON), `Relevante Infos`, `Schritt 3: Kommentar`

## Close.com-Export

```bash
python sync_to_close.py --dry-run                          # Testlauf (keine Änderungen)
python sync_to_close.py                                     # Import starten
python sync_to_close.py --leadherkunft "Franchise_Q2_2026"  # Andere Leadherkunft
python sync_to_close.py --no-update-airtable                # Airtable nicht zurückschreiben
python sync_to_close.py --include-imported                  # Auch bereits importierte nochmal
```

### Was passiert beim Import

Für jeden Airtable-Record mit `Schritt 3: Ansprechpartner = "Erfolgreich"`:

1. **Lead erstellen** — Name, Description, URL, Adresse, Custom Fields
2. **Kontakte anlegen** — AP 1–5, Weitere Ansprechpartner, Weitere Telefonnummern, Impressum
3. **Opportunity erstellen** — Status "Geprüfte Leads", Value 1000
4. **Notizen erstellen** — Relevante Infos (oben), Franchise Analyse, Werbeanzeigen, Stellenportal, LinkedIn, Dealfront
5. **Airtable zurückschreiben** — `Close Status = "done"`, `Close Lead ID` gesetzt

### Custom Fields in Close

| Close Custom Field | Wert |
|---|---|
| Branche | `"Franchise - {Branche}"` aus Airtable |
| Leadherkunft | CLI-Argument (default: `Franchise_03022026`) |
| Import ID | CLI-Argument (default: `Franchise_03022026`) |
| Lead Datensatz ID | Gleicher Wert wie Leadherkunft |
| Unternehmen | Verifizierter Unternehmensname aus Schritt 1 |
| Airtable Record ID | Airtable Record-ID |
| Airtable Record URL | Link zum Airtable-Record |

Das vollständige Feldmapping ist dokumentiert in [docs/close-sync-feldmapping.md](docs/close-sync-feldmapping.md).

## Parallele Verarbeitung

Mehrere Claude-Code-Instanzen können gleichzeitig am selben Airtable arbeiten. Die Architektur verhindert Doppel-Verarbeitung:

- **Claim-Mechanismus**: `claim1`/`claim2`/`claim3` holt kleine Batches (4 Records) und setzt sofort `"In Bearbeitung"` — andere Instanzen sehen diese Records nicht mehr
- **Playwright-Isolation**: `launch-playwright-mcp.sh` erstellt pro Session ein eigenes Chromium-Profil unter `/tmp/`
- **Crash-sicher**: Bei Abbruch max. 4 Records in `"In Bearbeitung"` stecken — in Airtable manuell zurücksetzen

So startest du 3 parallele Instanzen: Einfach 3 Claude-Code-Chats öffnen und jeweils z.B. `/find-contacts batch` eingeben.

## Airtable-Helpers (CLI)

```bash
# Records anzeigen (read-only)
python airtable_helpers.py step1 [limit]        # Offene Records für Schritt 1
python airtable_helpers.py step2 [limit]        # Offene Records für Schritt 2
python airtable_helpers.py step3 [limit]        # Offene Records für Schritt 3

# Records claimen (setzt "In Bearbeitung")
python airtable_helpers.py claim1 [count]       # Default: 4 Records
python airtable_helpers.py claim2 [count]
python airtable_helpers.py claim3 [count]

# Einzeloperationen
python airtable_helpers.py get <record_id>      # Einzelnen Record laden
python airtable_helpers.py write <id> '<json>' '<step>' '<status>'

# Setup
python airtable_helpers.py setup-fields         # Felder anlegen (einmalig)
python airtable_helpers.py list [limit]         # Offene Impressum-Records (Legacy)
```

## Tools & Infrastruktur

| Tool | Verwendung |
|---|---|
| **WebSearch** | Google-Recherche (primär) |
| **Apify Google SERP Scraper** | Fallback wenn WebSearch fehlschlägt |
| **Apify Website Content Crawler** | Fallback wenn Playwright blockiert wird |
| **Playwright MCP** | Webseiten navigieren und Inhalte lesen |
| **Claude AI** | Inhalte analysieren und strukturieren |

Playwright darf nur für **öffentliche Webseiten** genutzt werden — nie für Logins oder Admin-Panels.

## Dateien

| Datei | Beschreibung |
|---|---|
| `airtable_helpers.py` | Airtable API-Client (Claim, Write, Multi-Step, Meta-API) |
| `sync_to_close.py` | Airtable → Close.com Lead-Import |
| `test_create_lead.py` | Test-Lead in Close erstellen |
| `launch-playwright-mcp.sh` | Wrapper: isoliertes Chromium-Profil pro Session |
| `playwright-mcp.config.json` | Playwright-Browser-Konfiguration |
| `.claude/skills/verify-franchise/` | Schritt 1: Franchise-Validierung |
| `.claude/skills/scrape-impressum/` | Schritt 2: Impressum-Enrichment |
| `.claude/skills/find-contacts/` | Schritt 3: Ansprechpartner-Recherche |
| `docs/close-sync-feldmapping.md` | Vollständiges Close-Feldmapping |
