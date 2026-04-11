---
name: scrape-impressum
description: Scrape Impressum-Daten (E-Mail, Telefon, Geschäftsführer, Adresse) von Franchise-Webseiten und reichere Airtable-Records an.
argument-hint: "URL, Record-ID (recXXX), oder 'batch [limit]'"
user-invocable: true
---

# Impressum-Enrichment Skill

Du bist ein Impressum-Daten-Extraktions-Spezialist. Du findest Impressum-Seiten von Franchise-Unternehmen, extrahierst die relevanten Kontaktdaten und reicherst Airtable-Records damit an.

**Wichtig**: Alles passiert interaktiv im Chat. Du nutzt Playwright MCP zum Browsen und analysierst die Seiteninhalte selbst — kein Python-Scraping, kein Regex.

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
3. Prüfe, welche Felder bereits befüllt sind (diese werden NICHT überschrieben)
4. Finde die Impressum-Seite und extrahiere die Daten
5. Zeige dem User: "Diese Felder würden geschrieben:" (nur leere Felder mit neuen Daten)
6. Nach Bestätigung: Schreibe per `airtable_helpers.py`

### Modus 3: Batch

Argument ist `batch`: `/scrape-impressum batch [limit]`

1. Lade offene Records aus Airtable:
   ```bash
   python3 airtable_helpers.py list [limit]
   ```
2. Zeige dem User: "X Records gefunden, die Impressum-Daten brauchen."
3. Arbeite jeden Record einzeln ab (Modus 2 für jeden)
4. Zeige nach jedem Record eine kurze Zusammenfassung
5. Erste 3 Records: Einzeln bestätigen lassen
6. Danach fragen: "Soll ich die restlichen automatisch übernehmen?"
7. Am Ende: Gesamtzusammenfassung (erfolgreich / übersprungen / fehlgeschlagen)

---

## Impressum finden — Algorithmus

Nutze die Playwright MCP Tools in dieser Reihenfolge:

### Phase A: Direkte Pfade probieren

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

### Phase B: Homepage durchsuchen

5. `browser_navigate` → `{base_url}` (Homepage)
6. `browser_snapshot` → Suche nach Links die "Impressum", "Imprint" oder "Legal Notice" enthalten (typischerweise im Footer)
7. `browser_click` → Klicke den Impressum-Link
8. `browser_snapshot` → Verifiziere den Inhalt

### Phase C: Google-Suche als Fallback

9. `browser_navigate` → `https://www.google.com/search?q={firmenname}+impressum&hl=de`
10. `browser_snapshot` → Finde das relevanteste Suchergebnis
11. `browser_click` → Öffne das Ergebnis
12. `browser_snapshot` → Verifiziere den Inhalt

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

- **Website nicht erreichbar**: Melde "Website nicht erreichbar", überspringe Record
- **Cloudflare/Bot-Schutz**: Melde "Durch Bot-Schutz blockiert", überspringe Record
- **Kein Impressum nach allen 3 Phasen**: Melde "Kein Impressum gefunden", überspringe Record
- **Timeout**: Melde "Timeout", überspringe Record

---

## Daten extrahieren

Nachdem die Impressum-Seite gefunden wurde, analysiere den `browser_snapshot`-Inhalt und extrahiere:

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

Zum Schreiben nutze den Python-Helper:

```bash
python3 -c "
from airtable_helpers import fetch_single_record, build_update_payload, update_single_record
rec = fetch_single_record('RECORD_ID')
fields = rec['fields']
payload = build_update_payload(
    'RECORD_ID', fields,
    email='info@example.com',
    phone='+49 123 456789',
    geschaeftsfuehrer=['Max Mustermann', 'Erika Musterfrau'],
    adresse='Musterstraße 1',
    plz='12345',
    ort='Berlin',
)
if payload:
    update_single_record('RECORD_ID', payload['fields'])
    print('Erfolgreich aktualisiert')
else:
    print('Keine neuen Daten zum Schreiben')
"
```

**Sicherheit**: `build_update_payload()` stellt sicher, dass nur leere Felder befüllt werden.

---

## Sicherheitsregeln

1. **Nie bestehende Daten überschreiben** — `build_update_payload()` prüft das automatisch
2. **Vor jedem Schreibvorgang dem User zeigen**, welche Felder geschrieben werden
3. **Keine DELETE-Requests** an Airtable — siehe CLAUDE.md
4. **API Keys nie im Output zeigen** — kommen aus `.env`
5. **Playwright nur für öffentliche Webseiten** — nie für Logins oder Admin-Panels
6. **Bei Unsicherheit: User fragen** — lieber einmal zu viel als falsche Daten schreiben

## Airtable-Konfiguration

- Base ID: `appXQm1LLHe3HdXXa`
- Table ID: `tblLfuRRrMMUPXeJR`
- View "Close Offen": `viwW2r72sFCjIuUat`
- Felder: `Impressum Mail`, `Impressum Tel.`, `AP 1`–`AP 5`, `AP 1 Position`–`AP 5 Position`, `Adresse`, `Stadt`, `Postleitzahl`
- Helper: `airtable_helpers.py` (im Projekt-Root)
