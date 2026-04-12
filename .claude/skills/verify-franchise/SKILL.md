---
name: verify-franchise
description: Verifiziere Franchise-Unternehmen — prüfe ob es ein echtes Franchise ist, finde den Unternehmensnamen und verifiziere die Website-URL.
argument-hint: "Record-ID (recXXX) oder 'batch [limit]'"
user-invocable: true
---

# Franchise-Validierung (Schritt 1)

Du verifizierst Franchise-Unternehmen aus Airtable: Existiert das Franchise? Ist es wirklich ein Franchise-System? Stimmt die Website? Wie heißt das Unternehmen offiziell?

**Tools**:
- `WebSearch` für Google-Recherche (primär)
- Apify Google SERP Scraper als Fallback wenn WebSearch fehlschlägt
- `Playwright MCP` für das Aufrufen konkreter Webseiten

---

## Modi

### Modus 1: Einzelner Record

Argument beginnt mit `rec`: `/verify-franchise recXXXXXXXXXXXXXX`

1. Record aus Airtable laden:
   ```bash
   python3 airtable_helpers.py get <record_id>
   ```
2. Prüfe ob `Schritt 1: Validierung` bereits gesetzt ist. Falls ja: User fragen ob nochmal verarbeiten.
3. Status auf "In Bearbeitung" setzen:
   ```bash
   python3 -c "from airtable_helpers import set_step_status; set_step_status('RECORD_ID', 'Schritt 1: Validierung', 'In Bearbeitung')"
   ```
4. Recherche-Workflow durchführen (siehe unten)
5. Ergebnisse dem User zeigen
6. Nach Bestätigung: Daten in Airtable schreiben + Status "Erfolgreich" oder "Mit Problemen"

### Modus 2: Batch

Argument ist `batch`: `/verify-franchise batch [limit]`

1. Records laden:
   ```bash
   python3 airtable_helpers.py step1 [limit]
   ```
2. Zeige: "X Records brauchen Validierung."
3. **Parallel-Batch-Verarbeitung**: Statt Records einzeln nacheinander zu verarbeiten, immer **4 Records gleichzeitig** abarbeiten:
   - Für alle 4 Records parallel: Status auf "In Bearbeitung" setzen (1 Bash-Call)
   - Für alle 4 Records parallel: WebSearch-Aufrufe starten (bis zu 4 WebSearch gleichzeitig)
   - Ergebnisse aller 4 Records in **einem** `python3 -c` Bash-Call nach Airtable schreiben (update_record_fields + set_step_status für alle 4 in einem Script)
   - Dann die nächsten 4 Records
4. **Full-Auto-Modus**: Daten werden direkt geschrieben, KEINE Bestätigungen nötig.
   - Fortschritt ist crash-sicher: Status-Felder in Airtable tracken den Stand
   - Bei Session-Abbruch: Einfach `/verify-franchise batch` neu starten — bereits verarbeitete Records werden übersprungen
5. Alle 10 Records: Kurze Fortschritts-Zusammenfassung anzeigen (X/Y erledigt)
6. Am Ende: Gesamtzusammenfassung (erfolgreich / mit Problemen / übersprungen)
7. Bei Fehlern eines einzelnen Records: Status "Mit Problemen" setzen und mit dem nächsten Record fortfahren — **niemals den Batch abbrechen**

---

## Recherche-Workflow

Für jeden Record führe diese Schritte durch — **IMMER alle Schritte, auch wenn ein Schritt bereits gut aussieht**:

### Schritt A: Website-Erreichbarkeitscheck (Playwright)

Zuerst prüfen, ob die aktuelle Airtable-URL erreichbar ist und zum Unternehmen gehört:

1. `browser_navigate` → Airtable-URL des Unternehmens
2. `browser_snapshot` → Prüfe:
   - **Seite lädt**: Ist der Firmenname oder die Marke auf der Seite sichtbar?
   - **Seite lädt nicht**: DNS-Fehler, Timeout, 403, 404 → als "nicht erreichbar" merken
   - **Domain geparkt** (Sedo, IONOS, GoDaddy Parking): → als "geparkt" merken
   - **Redirect auf andere Domain**: → neue Domain notieren
3. Ergebnis merken (erreichbar/nicht erreichbar/geparkt/redirect), aber **IMMER weiter mit Schritt B**

### Schritt B: Franchise-Suche (WebSearch)

**Immer durchführen**, unabhängig vom Ergebnis von Schritt A:

1. `WebSearch` → "{NAME DES FRANCHISE-UNTERNEHMENS} Franchise" (bei Fehler: Apify-Fallback, siehe unten)
2. Analysiere die Suchergebnisse auf:
   - **Franchise-Portale**: franchise-portal.de, franchisedirekt.com, FranchiseCHECK.de, franchiseERFOLGE.de
   - **Deutscher Franchiseverband (DFV)**: franchiseverband.com
   - **Eigene Website**: Erwähnt sie "Franchise", "Franchisenehmer", "Franchise-Partner"?
   - **News**: Berichte über Franchise-Expansion, neue Standorte
   - **LinkedIn/Xing**: Profile mit "Franchise-Partner" für diese Marke

### Schritt C: Website-Verifizierung via Suche (WebSearch)

**Immer durchführen**, auch wenn Schritt A die Seite als erreichbar bestätigt hat:

1. `WebSearch` → "{NAME DES FRANCHISE-UNTERNEHMENS}" (ohne "Franchise") (bei Fehler: Apify-Fallback)
2. Vergleiche die URL aus den Top-Suchergebnissen mit der URL in Airtable (`Webseite`)
3. Prüfe ob die Domain aus Google mit der Airtable-URL übereinstimmt (gleiche Domain, egal ob www/https)
4. **Abgleich mit Schritt A:**
   - Airtable-URL erreichbar UND Google-URL stimmt überein → "Website korrekt"
   - Airtable-URL erreichbar ABER Google zeigt andere URL → Beide dem User zeigen, entscheiden lassen
   - Airtable-URL nicht erreichbar UND Google zeigt andere URL → URL-Abweichung in Begründung vermerken (kein "Mit Problemen" — die Recherche war trotzdem erfolgreich)
   - Airtable-URL nicht erreichbar UND Google findet auch nichts → URL-Problem in Begründung vermerken, Recherche mit den verfügbaren Infos fortsetzen

### Schritt D: Franchise-Name prüfen

Prüfe ob der aktuelle `NAME DES FRANCHISE-UNTERNEHMENS` in Airtable korrekt ist:

1. Vergleiche den Airtable-Namen mit dem, was Google-Ergebnisse und die Website zeigen
2. **Typische Abweichungen:**
   - Schreibweise anders (z.B. "McDonalds" vs. "McDonald's")
   - Alter Name, Marke wurde umbenannt
   - Name enthält fälschlich die Rechtsform (z.B. "Locatec GmbH" statt "Locatec")
   - Falsche Zuordnung (Name gehört zu einem anderen Unternehmen)
3. **Franchise-Name korrekt**: Keine Änderung nötig
4. **Franchise-Name weicht ab**: Korrektur vorschlagen und dem User zeigen, nach Bestätigung ändern

### Schritt E: Unternehmensname finden

1. Suche in den Google-Ergebnissen aus Schritt B+C nach dem juristischen Namen (GmbH, AG, UG, KG, Ltd., LLC etc.)
2. Falls nicht gefunden: `browser_navigate` zum Impressum der (ggf. neuen) Website → `browser_snapshot`
3. Claude extrahiert den offiziellen Firmennamen aus dem Impressum
4. Falls kein Impressum erreichbar: Unternehmensname leer lassen (wird in Schritt 2 nachgeholt)

### Schritt F: Franchise-Bewertung

Bewerte anhand ALLER gesammelten Informationen (Schritt A–E):

**Starke Positiv-Signale** (je +20-25%):
- Auf franchise-portal.de oder franchisedirekt.com gelistet
- DFV-Mitglied (Deutscher Franchiseverband)
- Eigene Website wirbt aktiv Franchisenehmer ("Franchise-Partner werden")

**Moderate Positiv-Signale** (je +10-15%):
- News über Franchise-Expansion
- Mehrere Standorte mit lokalen Betreibern erkennbar
- LinkedIn-Profile mit "Franchise-Partner" für diese Marke

**Negativ-Signale** (reduzieren den Prozentsatz):
- Keine Franchise-Hinweise in den Top-10 Google-Ergebnissen (-30%)
- Nur ein einzelner Standort erkennbar (-20%)
- Website offline oder Domain geparkt (-10%, aber kein "Mit Problemen" wenn Recherche sonst erfolgreich)
- Ergebnisse deuten auf Lizenzmodell statt Franchise (-15%)
- Unternehmen scheint aufgelöst/insolvent (-25%)

**Ergebnis**: Prozentsatz (0-100%) + deutsche Begründung (1-3 Sätze)

### Wann "Mit Problemen" setzen?

"Mit Problemen" wird **nur** gesetzt, wenn die Recherche selbst nicht erfolgreich abgeschlossen werden konnte:
- Unternehmen ist über Google/Web überhaupt nicht auffindbar (keinerlei Treffer)
- Franchise existiert nachweislich nicht mehr (aufgelöst, insolvent, abgemeldet)
- Technische Fehler verhindern die Datenerhebung komplett (alle Quellen blockiert)

**Kein "Mit Problemen"** bei:
- URL in Airtable ist falsch/nicht erreichbar, aber Unternehmen wurde über Google gefunden → "Erfolgreich", URL-Abweichung in Begründung vermerken
- Einzelne Felder konnten nicht befüllt werden (z.B. Standortzahl unbekannt) → "Erfolgreich", leere Felder sind okay
- Franchise-Score ist niedrig → "Erfolgreich" mit niedrigem Score

### Schritt G: Franchise-Details extrahieren

Aus den **bereits vorhandenen** Suchergebnissen (Schritt B+C) und ggf. dem Impressum (Schritt E) extrahiere:

1. **Zusammenfassung (kurz)**: 1 Satz — was macht das Franchise? Branche, Kerngeschäft.
   - Beispiel: "Locatec ist ein Franchise-System für professionelle Leck- und Leitungsortung in Gebäuden."
2. **Zusammenfassung (lang)**: 5 Sätze — ausführlichere Beschreibung mit Alleinstellungsmerkmalen, Zielgruppe, Geschäftsmodell.
3. **Anzahl Standorte**: Exakte Zahl wenn in Suchergebnissen genannt, sonst "ca. X". Wenn unbekannt: leer lassen.
4. **Anzahl Mitarbeiter**: Exakte Zahl wenn bekannt, sonst "ca. X". Wenn unbekannt: leer lassen.
5. **Gründungsdatum**: Jahr (z.B. "2011") oder volles Datum wenn bekannt. Wenn unbekannt: leer lassen.
6. **Franchise-Portal URLs**: Alle URLs aus den Suchergebnissen die auf Franchise-Portale zeigen, eine pro Zeile:
   - franchise-portal.de, franchiseportal.de, franchisedirekt.com, franchiseverband.com
   - FranchiseCHECK.de, franchiseERFOLGE.de, fuer-gruender.de/franchiseboerse
   - **Kein zusätzliches Scraping** — nur URLs die in Schritt B+C bereits aufgetaucht sind

---

## Google-Suche: WebSearch + Apify-Fallback

### Primär: WebSearch

Nutze das `WebSearch`-Tool für alle Google-Suchen. Das ist schnell und zuverlässig.

### Fallback: Apify Google SERP Scraper

Wenn `WebSearch` fehlschlägt (Fehler, keine Ergebnisse, oder nicht verfügbar), nutze den Apify-Fallback:

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
        'queries': 'SUCHBEGRIFF HIER',
        'maxPagesPerQuery': 1,
        'resultsPerPage': 10,
        'languageCode': 'de',
        'countryCode': 'de',
    },
    timeout=120,
)
# Apify gibt 201 Created zurück
if resp.status_code not in (200, 201):
    print(f'Fehler: {resp.status_code} {resp.text[:300]}')
else:
    results = resp.json()
    for item in results:
        if 'organicResults' in item:
            for r in item['organicResults'][:10]:
                print(f\"  {r.get('title', '?')}\")
                print(f\"  {r.get('url', '?')}\")
                print(f\"  {r.get('description', '')[:150]}\")
                print()
"
```

**Wann Fallback nutzen:**
- WebSearch gibt einen Fehler zurück
- WebSearch liefert 0 Ergebnisse für einen erwartbar findenbaren Begriff
- WebSearch ist temporär nicht verfügbar

**Nicht nötig wenn:** WebSearch normale Ergebnisse liefert, auch wenn wenige.

---

## Ergebnis-Format

Zeige die Ergebnisse dem User so:

```
Franchise: [NAME DES FRANCHISE-UNTERNEHMENS]
Franchise-Name korrekt: Ja / Nein → Korrektur: "..."
Webseite (Airtable):   [aktuelle URL]
Webseite (Playwright):  [erreichbar/nicht erreichbar/geparkt/redirect → neue URL]
Webseite (Google):      [URL aus Suche]

Ergebnisse:
  Franchise-System:       85%
  Begründung:             "Auf franchise-portal.de gelistet..."
  Unternehmensname:       Beispiel GmbH & Co. KG
  Website korrekt:        Ja / Nein → neue URL: https://...
  Zusammenfassung (kurz): "Beispiel ist ein Franchise für..."
  Zusammenfassung (lang): "Beispiel ist ein Franchise... (5 Sätze)"
  Standorte:              62 / ca. 60 / unbekannt
  Mitarbeiter:            250 / ca. 200 / unbekannt
  Gründungsdatum:         2011
  Franchise-Portal URLs:  https://franchiseportal.de/..., https://franchiseverband.com/...

Airtable-Update:
  NAME DES FRANCHISE-UNTERNEHMENS           → [nur bei Korrektur, nach Bestätigung]
  Unternehmensname                          → Beispiel GmbH & Co. KG
  Ist es ein Franchise-System?              → 0.85
  Ist es ein Franchise-System? Begründung   → "..."
  Zusammenfassung (kurz)                    → "..."
  Zusammenfassung (lang)                    → "..."
  Anzahl Standorte                          → "62" / "ca. 60"
  Anzahl Mitarbeiter                        → "250" / "ca. 200"
  Gründungsdatum                            → "2011"
  Franchise-Portal URLs                     → "https://...\nhttps://..."
  Webseite                                  → [nur bei Änderung, nach Bestätigung]
  Schritt 1: Validierung                    → Erfolgreich
  Schritt 1: Datum                          → [automatisch]
```

---

## Airtable schreiben

Zum Schreiben nutze den Python-Helper:

```bash
python3 -c "
from airtable_helpers import update_record_fields, set_step_status

# Daten schreiben (protect_existing=True: nie überschreiben)
update_record_fields('RECORD_ID', {
    'Unternehmensname': 'Beispiel GmbH & Co. KG',
    'Ist es ein Franchise-System?': 0.85,
    'Ist es ein Franchise-System? Begründung': 'Auf franchise-portal.de gelistet...',
    'Zusammenfassung (kurz)': 'Beispiel ist ein Franchise für...',
    'Zusammenfassung (lang)': 'Beispiel ist ein Franchise... (5 Sätze)',
    'Anzahl Standorte': '62',
    'Anzahl Mitarbeiter': 'ca. 250',
    'Gründungsdatum': '2011',
    'Franchise-Portal URLs': 'https://franchiseportal.de/...\nhttps://franchiseverband.com/...',
}, protect_existing=True)

# Status setzen (überschreibt immer, Datum wird automatisch gesetzt)
set_step_status('RECORD_ID', 'Schritt 1: Validierung', 'Erfolgreich')
print('Erfolgreich aktualisiert')
"
```

Wenn die Website-URL korrigiert werden muss (nur nach expliziter User-Bestätigung):
```bash
python3 -c "
from airtable_helpers import update_record_fields
update_record_fields('RECORD_ID', {
    'Webseite': 'https://neue-url.de',
}, protect_existing=False)
print('Website-URL aktualisiert')
"
```

Wenn der Franchise-Name korrigiert werden muss (nur nach expliziter User-Bestätigung):
```bash
python3 -c "
from airtable_helpers import update_record_fields
update_record_fields('RECORD_ID', {
    'NAME DES FRANCHISE-UNTERNEHMENS': 'Korrekter Franchise-Name',
}, protect_existing=False)
print('Franchise-Name aktualisiert')
"
```

**Hinweis:** `Webseite (https-Standardisiert)` ist ein berechnetes Feld — nur `Webseite` schreiben.

---

## Sicherheitsregeln

1. **Nie bestehende Daten überschreiben** — außer Website-URL nach expliziter User-Bestätigung
2. **Vor jedem Schreibvorgang dem User zeigen**, welche Felder geschrieben werden
3. **Keine DELETE-Requests** an Airtable — siehe CLAUDE.md
4. **API Keys nie im Output zeigen**
5. **WebSearch primär, Apify nur als Fallback** — spart Apify-Credits
6. **Bei Unsicherheit: User fragen**

## Airtable-Konfiguration

- Base ID: `appXQm1LLHe3HdXXa`
- Table ID: `tblLfuRRrMMUPXeJR`
- View "Close Offen": `viwW2r72sFCjIuUat`
- Status-Feld: `Schritt 1: Validierung`
- Datums-Feld: `Schritt 1: Datum` (wird automatisch von `set_step_status` gesetzt)
- Daten-Felder: `Unternehmensname`, `Ist es ein Franchise-System?`, `Ist es ein Franchise-System? Begründung`, `Zusammenfassung (kurz)`, `Zusammenfassung (lang)`, `Anzahl Standorte`, `Anzahl Mitarbeiter`, `Gründungsdatum`, `Franchise-Portal URLs`
- Korrigierbar (nach Bestätigung): `NAME DES FRANCHISE-UNTERNEHMENS`, `Webseite`
- Helper: `airtable_helpers.py` (im Projekt-Root)
- Apify API Key: `apify_api_key` in `.env`
