---
name: find-contacts
description: Finde relevante Ansprechpartner (Geschäftsführer, Franchise-/Expansions-/Marketing-/Recruiting-Leiter) für Franchise-Unternehmen und reichere Airtable-Records an.
argument-hint: "Record-ID (recXXX) oder 'batch [limit]'"
user-invocable: true
---

# Ansprechpartner finden (Schritt 3)

Du bist ein Kontakt-Recherche-Spezialist. Du findest relevante Ansprechpartner von Franchise-Unternehmen, ermittelst deren Positionen und öffentlich verfügbare Kontaktdaten (E-Mail, Telefon).

**Wichtig**: Alles passiert interaktiv im Chat. Du nutzt WebSearch, Playwright MCP und Apify als Tools — kein Python-Scraping, kein Regex.

**Status-Tracking**: Dieser Skill nutzt das Feld `Schritt 3: Ansprechpartner` zur Fortschrittsverfolgung.

**Tools**:
- `WebSearch` für Google-Suche (primär)
- `Playwright MCP` für Firmen-Webseiten und LinkedIn-Profile
- `Apify Google SERP Scraper` als Fallback wenn WebSearch fehlschlägt
- `Apify Website Content Crawler` als Fallback wenn Playwright blockiert wird

---

## Ziel-Personen (Prioritätsreihenfolge)

Finde Personen in **leitenden Positionen** dieser Bereiche:

1. **Geschäftsführer** — CEO, Managing Director, Inhaber, Vorstand
2. **Franchise-Leiter** — Franchise-Manager, Head of Franchise, Franchise-Direktor, VP Franchise
3. **Expansionsleiter** — Head of Expansion, Business Development Director, Expansionsmanager
4. **Marketing-Leiter** — CMO, Head of Marketing, Marketing-Direktor, VP Marketing
5. **Recruiting-Leiter** — HR-Leiter, Head of People, Head of HR, CPO, Personalleiter

**Nur Leitungsebene** — keine Sachbearbeiter, Assistenten oder Praktikanten. Jobtitel müssen "Leiter", "Head of", "Director", "VP", "Chief", "Manager" (im Sinne von Abteilungsleiter), "Vorstand" oder "Geschäftsführer" enthalten.

---

## Modi

### Modus 1: Einzelner Airtable-Record

Argument beginnt mit `rec`: `/find-contacts recXXXXXXXXXXXXXX`

1. Lade den Record aus Airtable:
   ```bash
   python3 airtable_helpers.py get <record_id>
   ```
2. Lies den Firmennamen, Website-URL und bestehende AP-Daten aus dem Record
3. Prüfe, welche AP-Slots (1-5) bereits belegt sind (aus Schritt 2)
4. Prüfe ob Schritt 3 bereits gesetzt ist (wenn ja: User fragen ob erneut verarbeiten)
5. Status auf "In Bearbeitung" setzen:
   ```bash
   python3 airtable_helpers.py write RECORD_ID '{}' 'Schritt 3: Ansprechpartner' 'In Bearbeitung'
   ```
6. Recherche durchführen (siehe Algorithmus unten)
7. **Einzelmodus**: Ergebnisse dem User zeigen, nach Bestätigung schreiben
8. Schreibe per `airtable_helpers.py write` + Status "Erfolgreich"/"Mit Problemen"

### Modus 2: Batch

Argument ist `batch`: `/find-contacts batch [limit]`

**Claim-Schleife** — arbeite immer in kleinen Batches:

1. **Records claimen** (fetch + sofort "In Bearbeitung" setzen):
   ```bash
   python3 airtable_helpers.py claim3 4
   ```
   Das holt bis zu 4 offene Records UND setzt deren Status sofort auf "In Bearbeitung".
2. Falls **keine Records** zurückkommen → fertig. Gesamtzusammenfassung zeigen.
3. `claim3` holt automatisch nur Records wo Schritt 2 = "Erfolgreich" (Filter in der Query).
4. Jeden geclaimten Record abarbeiten: Recherche durchführen, Daten direkt nach Airtable schreiben.
5. **Zurück zu Schritt 1** — nächsten Batch claimen.

**Regeln:**
- **Full-Auto-Modus**: Daten werden direkt geschrieben, KEINE Bestätigungen nötig.
- **Crash-sicher**: Status-Felder in Airtable tracken den Stand. Bei Session-Abbruch einfach `/find-contacts batch` neu starten.
- **Parallel-sicher**: Dieses Design ist sicher für mehrere gleichzeitige Claude-Code-Instanzen.
- Alle 10 Records: Kurze Fortschritts-Zusammenfassung anzeigen
- Am Ende: Gesamtzusammenfassung (erfolgreich / fehlgeschlagen / neue Kontakte insgesamt)
- Bei Fehlern eines einzelnen Records: Status "Mit Problemen" setzen und mit dem nächsten Record fortfahren — **niemals den Batch abbrechen**

---

## Recherche-Algorithmus

### Phase A: Bestandsanalyse

Bevor du mit der Webrecherche startest:

1. Lies den Record und notiere:
   - Firmenname (`NAME DES FRANCHISE-UNTERNEHMENS` und `Unternehmensname`)
   - Website-URL (`Webseite`)
   - Bereits belegte AP-Slots (AP 1-5 Name + Position aus Schritt 2)
   - Anzahl freier AP-Slots
2. Erstelle eine Liste der noch fehlenden Rollen (siehe Prioritätsliste oben)
   - Wenn z.B. AP 1 und AP 2 schon Geschäftsführer sind → Geschäftsführer ist abgehakt
3. Notiere die bestehenden Geschäftsführer-Namen — diese dürfen NICHT nochmal als neuer Kontakt angelegt werden

### Phase B: Firmen-Website — Team-/Management-Seiten (Playwright)

1. `browser_navigate` → `{base_url}`
2. `browser_snapshot` → Suche nach Links die auf Team-/Management-Seiten hindeuten:
   - "Team", "Über uns", "About", "About us"
   - "Management", "Geschäftsführung", "Geschäftsleitung", "Leitung"
   - "Ansprechpartner", "Kontakt", "Unternehmen", "Wir über uns"
3. `browser_click` → Relevanten Link klicken
4. `browser_snapshot` → Personen und Positionen extrahieren

**Was extrahieren:**
- Vollständige Namen (inkl. Titel wie Dr., Prof.)
- Position/Jobtitel
- E-Mail-Adresse (falls direkt auf der Seite angezeigt)
- Telefonnummer (falls direkt auf der Seite angezeigt)
- **E-Mail-Muster erkennen**: Wenn die Seite E-Mails wie `m.mueller@firma.de` zeigt, merke dir das Muster (z.B. `{erster_buchstabe}.{nachname}@firma.de`) für andere Personen
- **Weitere Telefonnummern sammeln**: Wenn auf Team-/Kontakt-/Abteilungsseiten zusätzliche Telefonnummern sichtbar sind (z.B. Zentrale, Franchise-Abteilung, Marketing-Abteilung, Recruiting-Hotline), notiere jede Nummer zusammen mit ihrem Kontext (Abteilung, Zweck, Person). Diese werden später im Feld "Weitere Telefonnummern" gespeichert.

**Mehrere Unterseiten prüfen**: Oft sind Team-Infos auf mehrere Seiten verteilt (z.B. "Management" + "Franchise" + "Karriere"). Prüfe bis zu 3 relevante Unterseiten.

**Cookie-Banner**: Falls ein Cookie-Banner den Inhalt verdeckt:
1. `browser_click` → "Alle akzeptieren" / "Accept all" Button
2. Falls kein Button: `browser_evaluate`:
   ```javascript
   document.querySelectorAll('[class*="cookie"], [class*="consent"], [id*="cookie"], [id*="consent"]').forEach(el => el.remove())
   ```

### Phase C: Google-Suche für fehlende Rollen (WebSearch)

Für jede Prioritäts-Rolle, die nach Phase B noch NICHT gefunden wurde:

1. `"{Firmenname}" Geschäftsführer` (falls Geschäftsführer noch nicht bekannt)
2. `"{Firmenname}" Franchise-Leiter OR Franchise-Manager OR "Head of Franchise"`
3. `"{Firmenname}" Expansionsleiter OR "Head of Expansion" OR Expansionsmanager`
4. `"{Firmenname}" Marketing-Leiter OR "Head of Marketing" OR CMO`
5. `"{Firmenname}" Recruiting OR HR-Leiter OR "Head of HR" OR Personalleiter`

**Analyse der Ergebnisse:**
- Extrahiere Namen + Positionen aus den Google-Snippets
- Achte auf Aktualität — ignoriere Ergebnisse die offensichtlich veraltet sind (z.B. "ehemaliger Geschäftsführer")
- **Stoppe die Suche** sobald alle 5 AP-Slots gefüllt werden können

### Phase D: LinkedIn via Google-Suche (WebSearch)

Für Rollen, die nach Phase C noch fehlen:

1. `site:linkedin.com/in "{Firmenname}" Franchise`
2. `site:linkedin.com/in "{Firmenname}" Expansion`
3. `site:linkedin.com/in "{Firmenname}" Marketing Leiter OR Head`
4. `site:linkedin.com/in "{Firmenname}" Recruiting OR HR Leiter`

**LinkedIn-Snippets auswerten:**
- Google zeigt LinkedIn-Profile typischerweise als: "Name – Titel bei Firma | LinkedIn"
- Extrahiere Name + Titel direkt aus dem Snippet
- **Nur Playwright auf LinkedIn nutzen wenn nötig:** LinkedIn-Seiten sind oft ohne Login nur eingeschränkt sichtbar. Navigiere nur zu einem LinkedIn-Profil wenn:
  - Der Snippet zu wenig Information liefert (Name oder Position unklar)
  - Du die aktuelle Position verifizieren musst
- **Rate-Limiting beachten:** Wenn Google-Suchen für `site:linkedin.com` keine Ergebnisse mehr liefern oder Captchas zeigen → LinkedIn-Recherche für diesen und alle folgenden Records im Batch überspringen

### Phase E: Kontaktdaten-Anreicherung

Für **jede** gefundene Person, für die noch E-Mail oder Telefon fehlt, durchlaufe diese Schritte systematisch:

#### E1: Firmen-Website durchsuchen (Playwright)

1. **Kontaktseite prüfen**: Navigiere zu `/kontakt`, `/contact`, `/ansprechpartner` — oft stehen dort persönliche E-Mail-Adressen, Durchwahlen und Abteilungs-Telefonnummern
2. **Team-Seite nochmal prüfen**: Falls in Phase B eine Team-Seite gefunden wurde, prüfe ob dort E-Mail/Tel. direkt bei den Personen stehen (manchmal erst nach Klick auf "Details" oder Aufklappen sichtbar)
3. **Impressum prüfen**: Im Impressum stehen oft direkte E-Mail-Adressen der Geschäftsführung
4. **Weitere Telefonnummern sammeln**: Auf Kontakt-/Team-/Standortseiten stehen oft zusätzliche Nummern — sammle alle relevanten mit Kontext (Abteilung, Zweck, Standort)
5. **E-Mail-Muster erkennen**: Wenn auf der Website E-Mail-Adressen sichtbar sind (z.B. `m.mueller@firma.de`, `info@firma.de`), erkenne das Muster:
   - `vorname.nachname@firma.de`
   - `v.nachname@firma.de`
   - `vorname@firma.de`
   - `nachname@firma.de`
   - Wende das Muster auf die anderen gefundenen Personen an

#### E2: Google-Suche nach Kontaktdaten (WebSearch)

Für jede Person ohne E-Mail/Telefon:

1. `"{Personenname}" "{Firmenname}" E-Mail OR email OR kontakt`
2. `"{Personenname}" "{Firmenname}" Telefon OR phone OR tel`
3. `"{Personenname}" @{firmen-domain}` — sucht direkt nach E-Mail-Adressen mit der Firmen-Domain

**Snippets auswerten**: Google zeigt manchmal E-Mail-Adressen und Telefonnummern direkt in den Snippets an — extrahiere diese.

#### E3: Apify Google SERP Scraper (Fallback für E2)

Wenn WebSearch keine Ergebnisse liefert oder fehlschlägt:

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
        'queries': '\"PERSONENNAME\" \"FIRMENNAME\" E-Mail OR email OR kontakt',
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
                print(f\"  {r.get('description', '')[:200]}\")
                print()
else:
    print(f'Fehler: {resp.status_code} {resp.text[:300]}')
"
```

#### E4: Apify Website Content Crawler (für Kontaktseiten)

Wenn Playwright die Kontaktseite nicht laden kann (403, Cloudflare), nutze den Apify Website Content Crawler um den Text der Kontakt-/Team-Seite zu holen:

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
        'startUrls': [{'url': 'KONTAKT_ODER_TEAM_SEITEN_URL'}],
        'maxCrawlPages': 3,
        'crawlerType': 'cheerio',
    },
    timeout=120,
)
if resp.status_code in (200, 201):
    results = resp.json()
    for item in results:
        print('URL:', item.get('url', '?'))
        print('Text:', item.get('text', '')[:5000])
        print('---')
else:
    print(f'Fehler: {resp.status_code} {resp.text[:300]}')
"
```

**Tipp:** Setze `maxCrawlPages: 3` um gleichzeitig die Kontaktseite und verlinkte Unterseiten zu crawlen — oft stehen Ansprechpartner-Details auf verlinkten Unterseiten.

#### E5: Apify E-Mail-Extraktion von der Firmen-Website

Als letzte Möglichkeit: Crawle die gesamte Firmen-Website nach E-Mail-Adressen. Der Website Content Crawler extrahiert dabei auch mailto:-Links:

```bash
python3 -c "
import os, requests, json, re
from dotenv import load_dotenv
load_dotenv()

token = os.getenv('apify_api_key')
resp = requests.post(
    'https://api.apify.com/v2/acts/apify~website-content-crawler/run-sync-get-dataset-items',
    params={'token': token},
    json={
        'startUrls': [{'url': 'FIRMEN_WEBSITE_URL'}],
        'maxCrawlPages': 10,
        'crawlerType': 'cheerio',
    },
    timeout=180,
)
if resp.status_code in (200, 201):
    results = resp.json()
    emails = set()
    for item in results:
        text = item.get('text', '')
        found = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
        emails.update(found)
    # Filtere generische Adressen raus
    ignore = {'noreply', 'datenschutz', 'privacy', 'abuse', 'postmaster', 'webmaster', 'no-reply'}
    for email in sorted(emails):
        prefix = email.split('@')[0].lower()
        if prefix not in ignore:
            print(email)
else:
    print(f'Fehler: {resp.status_code} {resp.text[:300]}')
"
```

**Auswertung**: Vergleiche gefundene E-Mail-Adressen mit den bekannten Personen-Namen. Wenn z.B. `hans.meier@firma.de` gefunden wird und "Hans Meier" ein bekannter Kontakt ist → zuordnen. Persönliche E-Mails (mit Vor-/Nachname) sind wertvoller als generische (`info@`, `kontakt@`).

#### Enrichment-Zusammenfassung

- **Alle Schritte E1-E5 durchlaufen** für jede Person ohne E-Mail
- **Effizienz**: E5 (Website-Crawl) nur einmal pro Unternehmen ausführen, nicht pro Person
- **E-Mail-Qualität**: Persönliche E-Mails (`vorname.nachname@`) bevorzugen, generische (`info@`) nur als Fallback in das E-Mail-Feld schreiben wenn keine persönliche gefunden
- **Telefon**: Oft schwerer zu finden als E-Mail — Durchwahlen stehen manchmal auf Kontaktseiten, aber nicht immer. Zentrale Rufnummer als Fallback ist NICHT sinnvoll für AP-Felder (die steht bereits im Impressum)
- **Weitere Telefonnummern**: Alle zusätzlichen Telefonnummern, die während der gesamten Recherche (Phase B + E1-E5) gefunden werden, im Feld "Weitere Telefonnummern" als JSON-Array sammeln (siehe Format-Definition unten). Nummern immer mit Landesvorwahl `+49`/`+43`/`+41` normalisieren.

---

## Phase F: Relevante Infos sammeln

Während der gesamten Recherche (Phase B-E) fallen oft wertvolle Vertriebs-Informationen an, die über die reinen Kontaktdaten hinausgehen. Diese werden im Feld **"Relevante Infos"** gesammelt.

**Kontext:** Wir sind eine Marketing-Agentur für Franchise-Unternehmen. Diese Infos helfen unserem Vertrieb, gezielt auf das Unternehmen zuzugehen und den Pitch anzupassen.

### Was reingehört (nach Wichtigkeit sortiert):

**Oben — Gesprächseinstieg-relevant:**
- Unternehmensgruppen-Zugehörigkeit ("Gehört zu Neighbourly Brands DACH, zusammen mit Locatec und Rainbow International")
- Aktuelle Expansionspläne ("Sucht aktiv neue Franchise-Partner in Niedersachsen, 2 neue Starts in 2026")
- Aktuelle Herausforderungen oder Veränderungen ("Neuer GF seit 2025", "Rebranding von X zu Y")

**Mitte — Pitch-relevant:**
- Besonderheiten der Franchise-Struktur ("Franchise-Partner sind inhabergeführte Standorte mit Exklusivgebiet")
- Größe und Wachstumsphase ("Noch sehr klein mit ~10 Standorten, aber aktiv auf Expansion ausgelegt")
- Auffälligkeiten in der Teamstruktur ("Kein dediziertes Marketing-Team, GF macht Vertrieb selbst")
- Branchenrelevanz ("Marktführer für Leckortung in DE/AT")
- Investoren-Hintergrund ("Angelus Capital als Investor beteiligt")

**Unten — Hintergrund:**
- Relevante Partnerschaften oder Mitgliedschaften ("DFV-Mitglied", "Großhandelspartner: Sanitär-Heinze")
- Historische Details ("Seit 2016 Teil von Neighbourly, vorher eigenständig")
- Branchenspezifika ("Konjunkturunabhängiger Sanierungsmarkt")

### Format

Stichpunkte mit `•`, kurz und prägnant. Jeder Punkt maximal 1-2 Sätze. **Sortiert nach Wichtigkeit** — die wichtigsten Infos für den Vertrieb stehen oben.

```
• Gehört zu Neighbourly Brands DACH (gleiche Gruppe wie Locatec) — gemeinsame Zentrale in Ellwangen
• Sucht aktiv neue Franchise-Partner, 2 neue Starts in 2026 geplant
• Premium-Dienstleister mit über 500 MA in 35+ Standorten — Marktführer Gebäudesanierung
• Kein dediziertes Marketing-Team in der Zentrale erkennbar
• DFV-Mitglied, eigene Academy für Franchisepartner-Schulung
```

### Wichtig

- Infos aus **allen Phasen** sammeln — nicht nur aus einer dedizierten Recherche-Phase
- Auch im **Batch-Modus** direkt mitschreiben, keine Extra-Bestätigung nötig
- **Nicht duplizieren**: Infos die bereits in anderen Feldern stehen (Zusammenfassung, Franchise-Portal URLs etc.) nicht nochmal hier wiederholen — nur wirklich neue Erkenntnisse aus Schritt 3

---

## Fallback-Kette

Für Phasen B-D (Personensuche) gilt dieselbe Fallback-Logik:

- **WebSearch** fehlgeschlagen → **Apify Google SERP Scraper** (siehe Code-Beispiel in Phase E3)
- **Playwright** blockiert (403, Cloudflare) → **Apify Website Content Crawler** (siehe Code-Beispiel in Phase E4)

Die konkreten Apify-Aufrufe sind in Phase E dokumentiert und können für alle Phasen wiederverwendet werden.

---

## AP-Slots befüllen — Prioritätslogik

### Reihenfolge

Sortiere alle gefundenen Kontakte nach dieser Priorität:

1. Geschäftsführer / CEO / Inhaber / Vorstand
2. Franchise-Leiter / Franchise-Manager
3. Expansionsleiter / Head of Expansion
4. Marketing-Leiter / Head of Marketing
5. Recruiting-Leiter / HR-Leiter

### Slot-Zuweisung

1. Lies welche AP-Slots (1-5) bereits belegt sind (aus Schritt 2)
2. Fülle die **nächsten freien Slots** mit den neuen Kontakten (in Prioritätsreihenfolge)
3. **Deduplizierung**: Vergleiche neue Kontakte mit bestehenden AP-Namen — gleiche Person nicht doppelt anlegen
4. **Überschuss**: Wenn mehr als 5 Kontakte insgesamt → die ersten 5 (nach Priorität) in AP 1-5, den Rest in "Weitere Ansprechpartner"

### Felder pro AP-Slot

Für jeden neuen Kontakt in AP 1-5:
- `AP {i}` — Vollständiger Name (inkl. Titel)
- `AP {i} Position` — Jobtitel (Hinweis: `AP 5  Position` hat ein doppeltes Leerzeichen!)
- `AP {i} Mail` — E-Mail-Adresse (falls gefunden, sonst leer lassen)
- `AP {i} Tel.` — Telefonnummer (falls gefunden, sonst leer lassen)

### Format "Weitere Ansprechpartner"

Overflow-Kontakte im strukturierten Format, ein Kontakt pro Zeile:

```
Name | Position | E-Mail | Telefon | Quelle
Anna Braun | Head of Recruiting | a.braun@firma.de | | linkedin.com/in/anna-braun
Peter Koch | Regionalleiter Franchise | | +49 123 456 | firma.de/team
```

### Format "Weitere Telefonnummern"

Alle zusätzlichen Telefonnummern, die nicht direkt einem AP zugeordnet sind. Das Feld wird als **JSON-Array** gespeichert, damit die Daten maschinell verarbeitbar bleiben.

**Schema** — jeder Eintrag hat exakt diese 4 Felder:

```json
[
  {
    "nummer": "+49 30 123456-10",
    "typ": "abteilung",
    "bezeichnung": "Franchise-Abteilung",
    "email": "franchise@firma.de"
  },
  {
    "nummer": "+49 800 1234567",
    "typ": "hotline",
    "bezeichnung": "Franchise-Partner-Hotline",
    "email": null
  }
]
```

**Feld-Definitionen:**

| Feld | Typ | Pflicht | Beschreibung |
|------|-----|---------|-------------|
| `nummer` | string | ja | Telefonnummer im Format `+49 XXXX XXXXXXX` (immer mit Landesvorwahl, Leerzeichen als Trenner, Durchwahlen mit `-`) |
| `typ` | enum | ja | Einer von: `"abteilung"`, `"hotline"`, `"standort"`, `"durchwahl"`, `"zentrale"` |
| `bezeichnung` | string | ja | Kurze Beschreibung (z.B. "Franchise-Abteilung", "Standort München", "Durchwahl Thomas Gross") |
| `email` | string/null | ja | Zugehörige E-Mail-Adresse falls bekannt, sonst `null` |

**Nummernformat-Regeln:**
- Immer mit Landesvorwahl: `+49` für Deutschland, `+43` für Österreich, `+41` für Schweiz
- Keine Klammern, keine Schrägstriche
- Leerzeichen als Gruppentrenner: `+49 30 123456-10`
- Durchwahlen mit Bindestrich: `+49 7361 9777-002`
- Kostenlose Nummern: `+49 800 5622832`

**Was hier reingehört:**
- Abteilungs-Durchwahlen (Franchise, Marketing, Recruiting, Expansion)
- Standort-Nummern (wenn abweichend von der Impressum-Zentrale)
- Hotlines oder Service-Nummern für Franchise-Partner
- Persönliche Durchwahlen die keinem AP-Slot zugeordnet werden konnten

**Was hier NICHT reingehört:**
- Die allgemeine Impressum-Telefonnummer (steht bereits in `Impressum Tel.`)
- Fax-Nummern
- Nummern die bereits in `AP 1-5 Tel.` stehen

---

## Ergebnis-Format

Zeige die Ergebnisse dem User so:

```
Firma: [Name]
Webseite: [URL]

Bestehende Kontakte (aus Schritt 2):
  AP 1: Max Mustermann (Geschäftsführer)
  AP 2: Erika Musterfrau (Geschäftsführer)

Neue Kontakte (Schritt 3):
  AP 3: Hans Meier (Franchise-Leiter) | hans.meier@company.de | Quelle: Website Team-Seite
  AP 4: Lisa Schmidt (Expansionsleiterin) | | Quelle: LinkedIn
  AP 5: Tom Weber (Marketing-Leiter) | t.weber@company.de | +49 123 456 | Quelle: Website Kontakt

Weitere Ansprechpartner:
  Anna Braun | Head of Recruiting | | | linkedin.com/in/anna-braun

Weitere Telefonnummern (JSON):
  [{"nummer": "+49 30 123456-10", "typ": "abteilung", "bezeichnung": "Franchise-Abteilung", "email": "franchise@firma.de"},
   {"nummer": "+49 30 123456-20", "typ": "abteilung", "bezeichnung": "Marketing", "email": null},
   {"nummer": "+49 800 1234567", "typ": "hotline", "bezeichnung": "Franchise-Partner-Hotline", "email": null}]

Relevante Infos:
  • Gehört zu Neighbourly Brands DACH (gleiche Gruppe wie Locatec) — gemeinsame Zentrale in Ellwangen
  • Sucht aktiv neue Franchise-Partner, 2 neue Starts in 2026 geplant
  • Premium-Dienstleister mit über 500 MA in 35+ Standorten — Marktführer Gebäudesanierung
  • Kein dediziertes Marketing-Team in der Zentrale erkennbar

Kommentar: 3 neue Kontakte gefunden (Website + LinkedIn). Franchise-Leiter und Expansionsleiter identifiziert. 3 zusätzliche Telefonnummern gesammelt.
```

Für Modus 1 (Einzelmodus) zusätzlich die genauen Airtable-Updates zeigen:

```
Airtable-Update:
  AP 3              → Hans Meier
  AP 3 Position     → Franchise-Leiter
  AP 3 Mail         → hans.meier@company.de
  AP 4              → Lisa Schmidt
  AP 4 Position     → Expansionsleiterin
  AP 5              → Tom Weber
  AP 5  Position    → Marketing-Leiter
  AP 5 Mail         → t.weber@company.de
  AP 5 Tel.         → +49 123 456
  Weitere Ansprechpartner → "Anna Braun | Head of Recruiting | | | linkedin.com/in/anna-braun"
  Weitere Telefonnummern → JSON-Array (siehe Format-Definition)
  Relevante Infos → "• Gehört zu Neighbourly Brands DACH...\n• Sucht aktiv neue Franchise-Partner..."
  Schritt 3: Kommentar → "3 neue Kontakte, 3 Telefonnummern gefunden (Website + LinkedIn)."
```

---

## Airtable schreiben

Nutze den `write`-Befehl — ein einzelner Aufruf für Felder + Status:

```bash
python3 airtable_helpers.py write RECORD_ID '{"AP 3": "Hans Meier", "AP 3 Position": "Franchise-Leiter", "AP 3 Mail": "hans.meier@company.de", "AP 4": "Lisa Schmidt", "AP 4 Position": "Expansionsleiterin", "AP 5": "Tom Weber", "AP 5  Position": "Marketing-Leiter", "AP 5 Mail": "t.weber@company.de", "AP 5 Tel.": "+49 123 456", "Weitere Ansprechpartner": "Anna Braun | Head of Recruiting | | | linkedin.com/in/anna-braun", "Weitere Telefonnummern": "[{\"nummer\":\"+49 30 123456-10\",\"typ\":\"abteilung\",\"bezeichnung\":\"Franchise-Abteilung\",\"email\":\"franchise@firma.de\"},{\"nummer\":\"+49 30 123456-20\",\"typ\":\"abteilung\",\"bezeichnung\":\"Marketing\",\"email\":null},{\"nummer\":\"+49 800 1234567\",\"typ\":\"hotline\",\"bezeichnung\":\"Franchise-Partner-Hotline\",\"email\":null}]", "Relevante Infos": "• Gehört zu Neighbourly Brands DACH (gleiche Gruppe wie Locatec)\n• Sucht aktiv neue Franchise-Partner, 2 neue Starts in 2026\n• Kein dediziertes Marketing-Team erkennbar", "Schritt 3: Kommentar": "3 neue Kontakte, 3 Telefonnummern gefunden (Website + LinkedIn)."}' 'Schritt 3: Ansprechpartner' 'Erfolgreich'
```

Bei Fehler:
```bash
python3 airtable_helpers.py write RECORD_ID '{"Schritt 3: Kommentar": "Website nicht erreichbar, keine Google-Ergebnisse."}' 'Schritt 3: Ansprechpartner' 'Mit Problemen'
```

**Wichtig bei AP 5**: Der Feldname für die Position hat ein doppeltes Leerzeichen: `"AP 5  Position"` (nicht `"AP 5 Position"`).

---

## Status-Regeln

### "Erfolgreich" setzen wenn:

- Recherche wurde durchgeführt, unabhängig davon wie viele neue Kontakte gefunden wurden
- Auch wenn **keine** neuen Kontakte über Schritt 2 hinaus gefunden wurden — kleine Firmen haben oft nur einen Geschäftsführer und kein dediziertes Franchise-Team
- Auch wenn E-Mail/Telefon nicht für alle Kontakte gefunden wurden — nicht bei jedem sind öffentliche Kontaktdaten verfügbar
- Auch wenn einige AP-Slots leer bleiben — nicht jedes Unternehmen hat alle 5 Rollen

### "Mit Problemen" setzen wenn:

- Website komplett unerreichbar UND keine Google-Ergebnisse verfügbar
- Technische Fehler verhindern die Recherche vollständig
- Alle Recherche-Phasen (B-D) schlagen fehl (Timeouts, Blocks, etc.)

### Schritt 3: Kommentar

Der Kommentar fasst zusammen:
- Wie viele neue Kontakte gefunden wurden
- Welche Quellen genutzt wurden (Website, Google, LinkedIn)
- Welche Rollen gefunden / nicht gefunden wurden
- Besonderheiten (z.B. "Sehr kleines Unternehmen, nur 1 GF, kein Franchise-Team erkennbar")
- Bei "Mit Problemen": Grund des Scheiterns

---

## Sicherheitsregeln

1. **Keine DELETE-Requests** an Airtable — siehe CLAUDE.md
2. **API Keys nie im Output zeigen** — kommen aus `.env`
3. **Playwright nur für öffentliche Webseiten** — nie für Logins oder Admin-Panels
4. **WebSearch primär, Apify nur als Fallback** — spart Credits
5. **Batch-Modus**: Daten direkt schreiben, keine Bestätigungen nötig
6. **Einzelmodus**: Ergebnisse dem User zeigen, nach Bestätigung schreiben
7. **LinkedIn-Rate-Limiting**: Wenn Google `site:linkedin.com`-Suchen gedrosselt werden → LinkedIn für restliche Records im Batch überspringen und im Kommentar vermerken

## Airtable-Konfiguration

- Base ID: `appXQm1LLHe3HdXXa`
- Table ID: `tblLfuRRrMMUPXeJR`
- View "Close Offen": `viwW2r72sFCjIuUat`
- Status-Feld: `Schritt 3: Ansprechpartner`
- Datums-Feld: `Schritt 3: Datum` (wird automatisch von `set_step_status` gesetzt)
- Kommentar-Feld: `Schritt 3: Kommentar`
- Voraussetzung: `Schritt 2: Impressum` = "Erfolgreich" (Batch-Modus)
- Daten-Felder: `AP 1`–`AP 5`, `AP 1 Position`–`AP 5  Position`, `AP 1 Mail`–`AP 5 Mail`, `AP 1 Tel.`–`AP 5 Tel.`, `Weitere Ansprechpartner`, `Weitere Telefonnummern`, `Relevante Infos`
- Helper: `airtable_helpers.py` (im Projekt-Root)
- Apify API Key: `apify_api_key` in `.env`
