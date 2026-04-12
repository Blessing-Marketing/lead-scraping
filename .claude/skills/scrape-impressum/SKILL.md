---
name: scrape-impressum
description: Scrape Impressum-Daten (E-Mail, Telefon, Geschäftsführer, Adresse) von Franchise-Webseiten und reichere Airtable-Records an.
argument-hint: "URL, Record-ID (recXXX), oder 'batch [limit]'"
user-invocable: true
---

# Impressum-Enrichment (Schritt 2)

Du bist ein Impressum-Daten-Extraktions-Spezialist. Du findest Impressum-Seiten von Franchise-Unternehmen, extrahierst die relevanten Kontaktdaten und reicherst Airtable-Records damit an.

**Wichtig**: Alles passiert interaktiv im Chat. Du nutzt Playwright MCP zum Browsen und analysierst die Seiteninhalte selbst — kein Python-Scraping, kein Regex.

**Status-Tracking**: Dieser Skill nutzt das Feld `Schritt 2: Impressum` zur Fortschrittsverfolgung.

**Tools**:
- `Playwright MCP` für das Aufrufen konkreter Webseiten (primär)
- `WebSearch` für Impressum-URL-Suche als Fallback (statt Google via Playwright)
- `Apify Website Content Crawler` als Fallback wenn Playwright blockiert wird (403, Cloudflare)

---

## Modi

### Modus 1: Einzelne URL

Argument ist eine URL: `/scrape-impressum https://www.example.com`

1. Finde die Impressum-Seite (siehe Algorithmus unten)
2. Extrahiere die Daten (siehe Extraktion unten)
3. Zeige dem User die Ergebnisse in einer Tabelle
4. Frage, ob die Daten in einen Airtable-Record geschrieben werden sollen

### Modus 2: Einzelner Airtable-Record

Argument beginnt mit `rec`: `/scrape-impressum recXXXXXXXXXXXXXX`

1. Lade den Record aus Airtable:
   ```bash
   python3 airtable_helpers.py get <record_id>
   ```
2. Lies den Firmennamen und die Website-URL aus dem Record
   - **Nutze die verifizierte URL aus Schritt 1** (`Webseite`-Feld, wurde ggf. in Step 1 korrigiert)
3. Prüfe, welche Felder bereits befüllt sind (diese werden NICHT überschrieben)
4. Status auf "In Bearbeitung" setzen:
   ```bash
   python3 airtable_helpers.py write RECORD_ID '{}' 'Schritt 2: Impressum' 'In Bearbeitung'
   ```
5. Finde die Impressum-Seite und extrahiere die Daten
6. Zeige dem User: "Diese Felder würden geschrieben:" (nur leere Felder mit neuen Daten)
7. Nach Bestätigung: Schreibe per `airtable_helpers.py` + Status "Erfolgreich" setzen
8. Bei Fehler (Website nicht erreichbar etc.): Status "Mit Problemen" setzen

### Modus 3: Batch

Argument ist `batch`: `/scrape-impressum batch [limit]`

**Claim-Schleife** — arbeite immer in kleinen Batches, nie alle Records auf einmal laden:

1. **Records claimen** (fetch + sofort "In Bearbeitung" setzen):
   ```bash
   python3 airtable_helpers.py claim2 4
   ```
   Das holt bis zu 4 offene Records UND setzt deren Status sofort auf "In Bearbeitung".
2. Falls **keine Records** zurückkommen → fertig, alle Records verarbeitet. Gesamtzusammenfassung zeigen.
3. **Wichtig**: Nur Records verarbeiten wo `Schritt 1: Validierung` = "Erfolgreich".
   Records mit `Schritt 1: Validierung` = "Mit Problemen" oder leer → Status "Mit Problemen" setzen und überspringen.
4. Jeden geclaimten Record einzeln abarbeiten (Modus 2-Logik).
5. **Zurück zu Schritt 1** — nächsten Batch claimen.

**Regeln:**
- **Full-Auto-Modus**: Daten werden direkt geschrieben, KEINE Bestätigungen nötig.
- **Crash-sicher**: Status-Felder in Airtable tracken den Stand. Bei Session-Abbruch einfach
  `/scrape-impressum batch` neu starten — geclaimte Records werden übersprungen.
- **Parallel-sicher**: Dieses Design ist sicher für mehrere gleichzeitige Claude-Code-Instanzen.
- Alle 10 Records: Kurze Fortschritts-Zusammenfassung anzeigen (X erledigt)
- Am Ende: Gesamtzusammenfassung (erfolgreich / übersprungen / fehlgeschlagen)
- Bei Fehlern eines einzelnen Records: Status "Mit Problemen" setzen und mit dem nächsten Record fortfahren — **niemals den Batch abbrechen**

---

## Impressum finden — Algorithmus

Nutze die Tools in dieser Reihenfolge:

### Phase A: Direkte Pfade probieren (Playwright)

1. `browser_navigate` → `{base_url}/impressum`
2. `browser_snapshot` → Prüfe ob echter Impressum-Inhalt vorhanden ist
3. **Echtes Impressum erkennen**: Seite enthält mindestens 2 dieser Marker:
   - Handelsregister, Amtsgericht, Registergericht
   - Geschäftsführer, Geschäftsführung, Vertretungsberechtigter
   - USt-IdNr, USt-ID, Steuernummer
   - Verantwortlich i.S.d., Haftungsausschluss
4. Falls kein Treffer: Probiere nacheinander:
   - `/imprint`
   - `/de/impressum`
   - `/legal-notice`
   - `/legal`

### Phase B: Homepage durchsuchen (Playwright)

5. `browser_navigate` → `{base_url}` (Homepage)
6. `browser_snapshot` → Suche nach Links die "Impressum", "Imprint" oder "Legal Notice" enthalten (typischerweise im Footer)
7. `browser_click` → Klicke den Impressum-Link
8. `browser_snapshot` → Verifiziere den Inhalt

### Phase C: WebSearch-Fallback

Wenn Phase A+B kein Impressum finden (statt Google via Playwright — das wird geblockt):

9. `WebSearch` → "{firmenname} Impressum" (bei Fehler: Apify Google SERP Scraper, siehe unten)
10. Analysiere die Suchergebnisse — suche nach einer direkten Impressum-URL
11. `browser_navigate` → Gefundene Impressum-URL
12. `browser_snapshot` → Verifiziere den Inhalt

### Phase D: Apify-Fallback für blockierte Seiten

Wenn Playwright die Seite nicht laden kann (403, Cloudflare, Bot-Schutz, Timeout):

13. Nutze den **Apify Website Content Crawler** um den Seiteninhalt zu holen:
    ```bash
    python3 -c "
    import os, requests, json
    from dotenv import load_dotenv
    load_dotenv()
    
    token = os.getenv('apify_api_key')
    resp = requests.post(
        'https://api.apify.com/v2/acts/apify~website-content-crawler/run-sync-get-dataset-items',
        params={'token': token},
        json={
            'startUrls': [{'url': 'IMPRESSUM_URL_HIER'}],
            'maxCrawlPages': 1,
            'crawlerType': 'cheerio',
        },
        timeout=120,
    )
    if resp.status_code in (200, 201):
        results = resp.json()
        for item in results:
            print('URL:', item.get('url', '?'))
            print('Text:', item.get('text', '')[:5000])
    else:
        print(f'Fehler: {resp.status_code} {resp.text[:300]}')
    "
    ```
14. Claude analysiert den zurückgegebenen Text und extrahiert die Impressum-Daten

**Wann Phase D nutzen:**
- Playwright gibt 403 Forbidden zurück
- Cloudflare-Challenge oder Bot-Schutz erkannt
- Seite lädt nicht (Timeout) obwohl sie laut Step 1 existiert
- Playwright-Snapshot ist leer trotz erfolgreicher Navigation

### Cookie-Banner behandeln

Nach jeder Navigation die ein Cookie-Banner zeigt:
1. `browser_snapshot` → Erkenne ob ein Cookie-Overlay den Inhalt verdeckt
2. `browser_click` → Klicke den "Alle akzeptieren" / "Accept all" / "Zustimmen" Button
3. Falls kein klickbarer Button: `browser_evaluate` mit JS um das Overlay zu entfernen:
   ```javascript
   document.querySelectorAll('[class*="cookie"], [class*="consent"], [id*="cookie"], [id*="consent"]').forEach(el => el.remove())
   ```
4. `browser_snapshot` → Seite erneut lesen

### Abbruchbedingungen

- **Website nicht erreichbar** (auch nach Apify): Melde "Website nicht erreichbar", Status "Mit Problemen"
- **Kein Impressum nach allen 4 Phasen**: Melde "Kein Impressum gefunden", Status "Mit Problemen"
- **Timeout**: Melde "Timeout", Status "Mit Problemen"

---

## Daten extrahieren

Nachdem die Impressum-Seite gefunden wurde, analysiere den `browser_snapshot`-Inhalt (oder den Apify-Text) und extrahiere:

### E-Mail
- Suche nach mailto:-Links oder E-Mail-Adressen in der Nähe von "E-Mail:", "Mail:", "Kontakt:"
- **Bevorzuge**: `info@`, `kontakt@`, `contact@`, `office@`, `hello@`
- **Ignoriere**: `noreply@`, `datenschutz@`, `privacy@`, `abuse@`, `postmaster@`
- **Deobfuskierung**: Erkenne `[at]`, `(at)`, `[dot]`, `(dot)`, `[punkt]` etc.

### Telefon
- Suche nach Nummern bei "Tel:", "Telefon:", "Phone:", "Fon:"
- Deutsche Nummern beginnen mit +49, 0049, oder 0
- **Ignoriere**: Fax-Nummern, Behörden-Nummern (Bundesnetzagentur etc.)
- **Format**: Originalformat beibehalten

### Geschäftsführer (max 5)
- Suche nach Namen hinter: "Geschäftsführer:", "Geschäftsführung:", "Vertretungsberechtigter:", "Vertreten durch:", "Vorstand:", "Inhaber:", "CEO:"
- Extrahiere vollständige Namen inkl. Titel (Dr., Prof., Dipl.-Ing.)
- **Stoppe vor**: Aufsichtsrat, Handelsregister, Amtsgericht-Abschnitten
- **Ignoriere**: Firmennamen, Städtenamen, generische Begriffe (GmbH, AG, Ltd.)

### Adresse
- Suche die Firmenadresse (Straße + Hausnummer, PLZ, Ort)
- **Ignoriere**: Gerichtsadressen (Amtsgericht), Behördenadressen, Schlichtungsstellen
- Die Firmenadresse steht typischerweise am Anfang des Impressums, nah am Firmennamen

---

## Ergebnis-Format

Zeige die Ergebnisse dem User so:

```
Firma: [Name]
URL:   [Impressum-URL]

Extrahierte Daten:
  E-Mail:           info@example.com
  Telefon:          +49 123 456789
  Geschäftsführer:  Max Mustermann, Erika Musterfrau
  Adresse:          Musterstraße 1, 12345 Berlin
```

Für Modus 2 (Airtable-Record) zusätzlich zeigen:

```
Airtable-Update (nur leere Felder):
  Impressum Mail    → info@example.com
  Impressum Tel.    → +49 123 456789
  AP 1              → Max Mustermann
  AP 1 Position     → Geschäftsführer
  AP 2              → Erika Musterfrau
  AP 2 Position     → Geschäftsführer
  Adresse           → Musterstraße 1
  Postleitzahl      → 12345
  Stadt             → Berlin
```

---

## Airtable schreiben

Nutze den `write`-Befehl — ein einzelner Einzeiler-Aufruf für Felder + Status:

```bash
python3 airtable_helpers.py write RECORD_ID '{"E-Mail": "info@example.com", "Telefon": "+49 123 456789", "Geschäftsführer": "Max Mustermann, Erika Musterfrau", "Adresse": "Musterstraße 1", "Postleitzahl": "12345", "Stadt": "Berlin"}' 'Schritt 2: Impressum' 'Erfolgreich'
```

Bei Fehler (Website nicht erreichbar, kein Impressum gefunden etc.):
```bash
python3 airtable_helpers.py write RECORD_ID '{}' 'Schritt 2: Impressum' 'Mit Problemen'
```

---

## Google-Suche: WebSearch + Apify-Fallback

### Primär: WebSearch

Für Phase C (Impressum-URL finden) nutze `WebSearch`. Schnell und kein Captcha.

### Fallback: Apify Google SERP Scraper

Wenn `WebSearch` fehlschlägt:

```bash
python3 -c "
import os, requests, json
from dotenv import load_dotenv
load_dotenv()

token = os.getenv('apify_api_key')
resp = requests.post(
    'https://api.apify.com/v2/acts/apify~google-search-scraper/run-sync-get-dataset-items',
    params={'token': token},
    json={
        'queries': 'FIRMENNAME Impressum',
        'maxPagesPerQuery': 1,
        'resultsPerPage': 10,
        'languageCode': 'de',
        'countryCode': 'de',
    },
    timeout=120,
)
if resp.status_code in (200, 201):
    results = resp.json()
    for item in results:
        if 'organicResults' in item:
            for r in item['organicResults'][:10]:
                print(f\"  {r.get('title', '?')}\")
                print(f\"  {r.get('url', '?')}\")
                print()
else:
    print(f'Fehler: {resp.status_code} {resp.text[:300]}')
"
```

---

## Sicherheitsregeln

1. **Nie bestehende Daten überschreiben** — `build_update_payload()` prüft das automatisch
2. **Vor jedem Schreibvorgang dem User zeigen**, welche Felder geschrieben werden
3. **Keine DELETE-Requests** an Airtable — siehe CLAUDE.md
4. **API Keys nie im Output zeigen** — kommen aus `.env`
5. **Playwright nur für öffentliche Webseiten** — nie für Logins oder Admin-Panels
6. **WebSearch primär, Apify nur als Fallback** — spart Credits
7. **Bei Unsicherheit: User fragen** — lieber einmal zu viel als falsche Daten schreiben

## Airtable-Konfiguration

- Base ID: `appXQm1LLHe3HdXXa`
- Table ID: `tblLfuRRrMMUPXeJR`
- View "Close Offen": `viwW2r72sFCjIuUat`
- Status-Feld: `Schritt 2: Impressum`
- Datums-Feld: `Schritt 2: Datum` (wird automatisch von `set_step_status` gesetzt)
- Voraussetzung: `Schritt 1: Validierung` = "Erfolgreich" (Batch-Modus)
- Daten-Felder: `Impressum Mail`, `Impressum Tel.`, `AP 1`–`AP 5`, `AP 1 Position`–`AP 5 Position`, `Adresse`, `Stadt`, `Postleitzahl`
- Helper: `airtable_helpers.py` (im Projekt-Root)
- Apify API Key: `apify_api_key` in `.env`
