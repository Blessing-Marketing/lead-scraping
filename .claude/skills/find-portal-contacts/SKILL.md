---
name: find-portal-contacts
description: Finde in Franchise-Portalen (franchise-portal.de, franchisedirekt.com, FranchiseCHECK.de, franchiseERFOLGE.de, franchiseverband.com, fuer-gruender.de/franchiseboerse) die für ein Franchise-Unternehmen hinterlegten Ansprechpartner und speichere sie als JSON in Airtable.
argument-hint: "Record-ID (recXXX) oder 'batch [limit]'"
user-invocable: true
---

# Portal-Ansprechpartner finden (Schritt 4)

Du bist ein Portal-Recherche-Spezialist. Für ein Franchise-Unternehmen besuchst du die Franchise-Portale, in denen es gelistet ist, und extrahierst die dort hinterlegten Ansprechpartner (meist Franchise-Manager, Expansions-Verantwortliche oder Geschäftsführer). Diese Personen sind für die Sales-Ansprache besonders wertvoll — sie suchen aktiv neue Franchise-Partner.

**Wichtig**: Alles passiert interaktiv im Chat. Du nutzt WebSearch, Playwright MCP und Apify als Tools — kein Python-Scraping, kein Regex.

**Status-Tracking**: Dieser Skill nutzt das Feld `Schritt 4: Portal-Kontakte` zur Fortschrittsverfolgung.

**Datenziel**: Feld `Franchise Portal Ansprechpartner` (JSON-Array als Text). **Kein Close-Sync** in dieser Iteration.

**Tools**:
- `WebSearch` für Google-Suche nach Portal-Listungen (Fallback wenn `Franchise-Portal URLs` leer ist)
- `Playwright MCP` für Portal-Seiten
- `Apify Google SERP Scraper` als Fallback wenn WebSearch fehlschlägt
- `Apify Website Content Crawler` als Fallback wenn Playwright blockiert wird

---

## Relevante Portale

- **franchise-portal.de** / **franchiseportal.de**
- **franchisedirekt.com**
- **FranchiseCHECK.de**
- **franchiseERFOLGE.de**
- **franchiseverband.com** (Deutscher Franchiseverband)
- **fuer-gruender.de/franchiseboerse**

---

## Modi

### Modus 1: Einzelner Airtable-Record

Argument beginnt mit `rec`: `/find-portal-contacts recXXXXXXXXXXXXXX`

1. Lade den Record:
   ```bash
   python3 airtable_helpers.py get <record_id>
   ```
2. Prüfe, dass `Schritt 1: Validierung` = "Erfolgreich" ist. Wenn nicht → abbrechen mit Hinweis.
3. Prüfe ob `Schritt 4: Portal-Kontakte` bereits gesetzt ist (wenn ja: User fragen ob erneut verarbeiten).
4. Status auf "In Bearbeitung" setzen:
   ```bash
   python3 airtable_helpers.py write RECORD_ID '{}' 'Schritt 4: Portal-Kontakte' 'In Bearbeitung'
   ```
5. Recherche durchführen (siehe Algorithmus unten).
6. **Einzelmodus**: Gefundenes JSON dem User zeigen, nach Bestätigung schreiben.
7. Schreibe per `airtable_helpers.py write` + Status "Erfolgreich"/"Mit Problemen".

### Modus 2: Batch

Argument ist `batch`: `/find-portal-contacts batch [limit]`

**Claim-Schleife** — arbeite immer in kleinen Batches:

1. **Records claimen** (fetch + sofort "In Bearbeitung" setzen):
   ```bash
   python3 airtable_helpers.py claim4 4
   ```
   Das holt bis zu 4 offene Records UND setzt deren Status sofort auf "In Bearbeitung".
2. Falls **keine Records** zurückkommen → fertig. Gesamtzusammenfassung zeigen.
3. `claim4` holt automatisch nur Records wo `Schritt 1: Validierung` = "Erfolgreich" (Filter in der Query).
4. Jeden geclaimten Record abarbeiten: Recherche durchführen, Daten direkt nach Airtable schreiben.
5. **Zurück zu Schritt 1** — nächsten Batch claimen.

**Regeln:**
- **Full-Auto-Modus**: Daten werden direkt geschrieben, KEINE Bestätigungen nötig.
- **Crash-sicher**: Status-Felder tracken den Stand. Bei Session-Abbruch einfach `/find-portal-contacts batch` neu starten.
- **Parallel-sicher**: Design ist sicher für mehrere gleichzeitige Claude-Code-Instanzen.
- Alle 10 Records: kurze Fortschritts-Zusammenfassung.
- Am Ende: Gesamtzusammenfassung (erfolgreich / fehlgeschlagen / Summe der gefundenen Portal-Kontakte).
- Bei Fehlern eines einzelnen Records: Status "Mit Problemen" setzen und mit dem nächsten Record fortfahren — **niemals den Batch abbrechen**.

---

## Recherche-Algorithmus

### Phase A: Portal-URLs sammeln

1. Lies das Feld `Franchise-Portal URLs` aus dem Record (newline-separiert).
2. **Wenn das Feld gefüllt ist**: Nimm diese URLs als Startliste.
3. **Wenn das Feld leer ist oder nur offensichtliche Nicht-Portal-URLs enthält**: Führe WebSearch aus:
   ```
   "{Firmenname}" site:franchise-portal.de OR site:franchisedirekt.com OR site:franchiseCHECK.de OR site:franchiseERFOLGE.de OR site:franchiseverband.com OR site:fuer-gruender.de
   ```
   Extrahiere die Portal-Detail-URLs aus den Treffern.
4. **Apify Google SERP Scraper** als Fallback wenn WebSearch keine Ergebnisse liefert (siehe Code-Beispiel in Phase D).
5. **Deduplizieren**: Pro Portal-Domain maximal eine URL — die spezifischste Detailseite für das Unternehmen.
6. **Abbruch-Kriterium**: Wenn nach WebSearch + Apify keine einzige Portal-URL gefunden wurde → Status "Mit Problemen" setzen, Feld `Franchise Portal Ansprechpartner` leer lassen, mit nächstem Record fortfahren.

### Phase B: Portal-Seite besuchen & Kontakt extrahieren (Playwright)

Für **jede** Portal-URL:

1. `browser_navigate` → URL
2. **Cookie-Banner** schließen falls nötig:
   - `browser_click` auf "Alle akzeptieren" / "Accept all" / "Zustimmen"
   - Fallback via `browser_evaluate`:
     ```javascript
     document.querySelectorAll('[class*="cookie"], [class*="consent"], [id*="cookie"], [id*="consent"]').forEach(el => el.remove())
     ```
3. `browser_snapshot` → Seiteninhalt analysieren.
4. Suche nach Abschnitten mit Ansprechpartner-Info. Typische Labels:
   - "Ansprechpartner", "Ihr Ansprechpartner", "Kontakt", "Ihr Kontakt"
   - "Franchise-Manager", "Franchise-Leiter", "Expansionsleiter"
   - "Geschäftsführer", "Inhaber"
   - Personen-Kachel/Karten mit Foto + Name + Telefon + E-Mail
5. Falls der Kontakt hinter einem Aufklapper/Tab versteckt ist:
   - `browser_click` auf "Mehr anzeigen", "Kontakt anzeigen", "Ansprechpartner anzeigen"
   - `browser_snapshot` erneut
6. Falls Playwright blockiert wird (ERR_TUNNEL_CONNECTION_FAILED, 403, Cloudflare, Timeout, leerer Snapshot) → **Apify Website Content Crawler** (siehe Phase D).

**Was extrahieren:**
- **Name**: Vollständiger Name inkl. Titel (Dr., Prof., Dipl. Ing. etc.)
- **Telefon**: Im Format `+49 XXXX XXXXXXX` normalisieren (immer mit Landesvorwahl, Leerzeichen als Trenner, Durchwahlen mit `-`)
- **E-Mail**: direkte E-Mail-Adresse falls angezeigt
- **Portal**: Kurzname der Quelle (z.B. `"franchise-portal.de"`, `"franchisedirekt.com"`) — nicht die volle URL

**Name allein reicht — das ist der Normalfall.** In den allermeisten Fällen zeigen Franchise-Portale nur den Namen des Ansprechpartners (oft mit Foto), während die Kontaktaufnahme ausschließlich über Info-Formulare des Portals läuft. Telefon und E-Mail werden bewusst nicht öffentlich angezeigt. **Suche NICHT aktiv nach Kontaktdaten** über externe Quellen (Website, LinkedIn, Google) — dafür gibt es den separaten Skill `/find-contacts` (Schritt 3). In diesem Skill geht es nur um das, was direkt auf der Portal-Seite sichtbar ist. Wenn nur der Name da ist → `telefon: null`, `email: null` eintragen. Das ist kein Mangel, sondern Normalfall.

### Phase C: Deduplizierung über Portale hinweg

Wenn dieselbe Person auf mehreren Portalen auftaucht (Name-Match, fuzzy — gleicher Nachname + Vorname oder Vorname-Initial):

- **Ein einziger JSON-Eintrag** für diese Person
- Feld `portal` als Komma-Liste aller Quellen: `"franchise-portal.de, franchisedirekt.com"`
- Telefon/E-Mail: die vollständigere Variante übernehmen; bei Konflikt den Wert vom ersten Portal behalten und im Kommentar vermerken

### Phase D: Apify-Fallbacks

#### D1: Apify Google SERP Scraper (wenn WebSearch fehlschlägt)

```bash
python3 apify_serp.py '"FIRMENNAME" site:franchise-portal.de OR site:franchisedirekt.com OR site:franchiseCHECK.de OR site:franchiseERFOLGE.de OR site:franchiseverband.com'
```

#### D2: Apify Website Content Crawler (wenn Playwright blockiert)

**Trigger-Bedingungen** (eine reicht): `ERR_TUNNEL_CONNECTION_FAILED`, HTTP 403, Cloudflare-Challenge, Timeout, leerer Snapshot.

```bash
python3 apify_crawl.py 'PORTAL_DETAIL_URL'
```

---

## Datenformat: Franchise Portal Ansprechpartner

Gespeichert wird ein **JSON-Array** als Text im Feld `Franchise Portal Ansprechpartner`. Pro gefundenem Kontakt exakt diese vier Felder:

```json
[
  {
    "name": "Maria Schneider",
    "telefon": "+49 30 123456-10",
    "email": "m.schneider@beispiel-franchise.de",
    "portal": "franchise-portal.de"
  },
  {
    "name": "Thomas Bauer",
    "telefon": "+49 89 9876543",
    "email": null,
    "portal": "franchisedirekt.com, franchiseverband.com"
  }
]
```

**Feld-Definitionen:**

| Feld | Typ | Pflicht | Beschreibung |
|------|-----|---------|-------------|
| `name` | string | ja | Vollständiger Name (inkl. Titel) |
| `telefon` | string \| null | ja | Normalisierte Telefonnummer, `null` wenn nicht gefunden |
| `email` | string \| null | ja | E-Mail-Adresse, `null` wenn nicht gefunden |
| `portal` | string | ja | Kurzname des Portals (z.B. `"franchise-portal.de"`); bei Deduplizierung Komma-Liste |

**Leerer Treffer**: Wenn auf allen Portalen keine Person extrahierbar war → `[]` (leeres Array als String: `"[]"`).

**JSON-Format**: Nutze `json.dumps(kontakte, ensure_ascii=False, indent=2)` für gute Lesbarkeit in der Airtable-Zelle.

---

## Ergebnis-Format

Zeige dem User:

```
Firma: [Name]
Geprüfte Portale (N): franchise-portal.de, franchisedirekt.com, franchiseverband.com

Gefundene Portal-Ansprechpartner (M):
  1. Maria Schneider | +49 30 123456-10 | m.schneider@beispiel-franchise.de | franchise-portal.de
  2. Thomas Bauer   | +49 89 9876543   | (keine E-Mail)                    | franchisedirekt.com, franchiseverband.com

Kommentar: 2 Ansprechpartner aus 3 Portalen extrahiert. Auf FranchiseCHECK.de gelistet, aber keine Person sichtbar.
```

Für Modus 1 (Einzelmodus) zusätzlich den genauen Airtable-Write zeigen.

---

## Airtable schreiben

Einzelner Aufruf für Feld + Status:

```bash
python3 airtable_helpers.py write RECORD_ID '{"Franchise Portal Ansprechpartner": "[\n  {\n    \"name\": \"Maria Schneider\",\n    \"telefon\": \"+49 30 123456-10\",\n    \"email\": \"m.schneider@beispiel-franchise.de\",\n    \"portal\": \"franchise-portal.de\"\n  }\n]"}' 'Schritt 4: Portal-Kontakte' 'Erfolgreich'
```

Bei Fehler (keine Portal-URLs, keine Kontakte extrahierbar):

```bash
python3 airtable_helpers.py write RECORD_ID '{"Franchise Portal Ansprechpartner": "[]"}' 'Schritt 4: Portal-Kontakte' 'Mit Problemen'
```

Der `write`-Befehl setzt automatisch auch `Schritt 4: Datum` über `set_step_status`.

---

## Status-Regeln

### "Erfolgreich" setzen wenn:

- Mindestens eine Portal-Seite konnte besucht werden UND
- Mindestens ein Ansprechpartner wurde extrahiert
- Auch wenn nur Name ohne Telefon/E-Mail verfügbar war — Name allein ist bereits Mehrwert

### "Mit Problemen" setzen wenn:

- Keine Portal-URLs gefunden (weder im Feld noch via WebSearch/Apify)
- Alle Portal-Seiten blockiert (auch via Apify-Fallback nicht erreichbar)
- Portale geladen, aber **null** Personen extrahierbar (Feld bleibt `"[]"`)

---

## Bash-Regeln (für autonomen Lauf wichtig)

- **Niemals** `for`/`while`-Loops, `&&`-Ketten oder mehrzeilige Heredocs in Bash-Calls — solche zusammengesetzten Commands können nicht per Allow-Rule whitelisted werden und triggern jedes Mal eine Bestätigungs-Abfrage.
- **Niemals** `python3 -c "..."` mit Inline-Code — stattdessen die Helper-Skripte (`apify_serp.py`, `apify_crawl.py`, `airtable_helpers.py`) nutzen.
- Mehrere ähnliche Operationen → mehrere **parallele** Single-Tool-Calls in einer Message (z.B. 4× `python3 airtable_helpers.py get recXXX` parallel statt einer `for`-Schleife).

## Sicherheitsregeln

1. **Keine DELETE-Requests** an Airtable — siehe CLAUDE.md
2. **API Keys nie im Output zeigen** — kommen aus `.env`
3. **Playwright nur für öffentliche Portal-Seiten** — nie für Logins oder Admin-Panels
4. **WebSearch primär, Apify nur als Fallback** — spart Credits
5. **Niemals Close-Sync triggern** — dieser Skill schreibt ausschließlich nach Airtable
6. **`protect_existing` beachten**: `update_record_fields` überschreibt per Default keine befüllten Felder. Wenn `Franchise Portal Ansprechpartner` bereits JSON enthält, nur im Einzelmodus nach Bestätigung überschreiben.
7. **Batch-Modus**: Daten direkt schreiben, keine Bestätigungen nötig
8. **Einzelmodus**: Ergebnisse dem User zeigen, nach Bestätigung schreiben

---

## Voraussetzungen / Setup

Einmalig (nach Merge dieses Skills), um die drei neuen Airtable-Felder anzulegen:

```bash
python3 airtable_helpers.py setup-fields --dry-run   # Vorschau
python3 airtable_helpers.py setup-fields             # Anlegen
```

Legt an (idempotent, überspringt existierende Felder):
- `Schritt 4: Portal-Kontakte` (singleSelect)
- `Schritt 4: Datum` (dateTime)
- `Franchise Portal Ansprechpartner` (multilineText)

---

## Airtable-Konfiguration

- Base ID: `appXQm1LLHe3HdXXa`
- Table ID: `tblLfuRRrMMUPXeJR`
- View "Close Offen": `viwW2r72sFCjIuUat`
- Status-Feld: `Schritt 4: Portal-Kontakte`
- Datums-Feld: `Schritt 4: Datum` (wird automatisch von `set_step_status` gesetzt)
- Daten-Feld: `Franchise Portal Ansprechpartner` (multilineText, JSON als Text)
- Quell-Feld: `Franchise-Portal URLs` (multilineText, aus Schritt 1)
- Voraussetzung: `Schritt 1: Validierung` = "Erfolgreich"
- Helper: `airtable_helpers.py` (im Projekt-Root)
- Apify API Key: `apify_api_key` in `.env`
