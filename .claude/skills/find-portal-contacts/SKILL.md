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

## Relevante Portale (nach Ertrag priorisiert)

Aus ~170 verarbeiteten Records im April 2026 hat sich folgende Rangfolge ergeben — **immer in dieser Reihenfolge prüfen**:

1. **franchiseverband.com** — **beste Quelle**. Bei ~60–70 % der Detailseiten steht ein strukturierter `ANSPRECHPARTNER`-Block mit **Name + Telefon/Mobile + direkter E-Mail**. Slug-Konvention: `https://www.franchiseverband.com/systeme-finden/franchisesystem-detail-ansicht/{slug}`. Slugs nicht raten — immer per WebSearch `"{Firma}" site:franchiseverband.com` bestätigen, viele geratene Slugs 404en.
2. **franchiseportal.de** / **franchise-portal.de** — bei **Premium-Listings** steht oben ein Begleitungs-Block: *"Guten Tag, mein Name ist {Name} und ich vertrete {Firma}. Als dein Ansprechpartner..."*. Nur Name (keine Tel/E-Mail) — das ist trotzdem wertvoll. Bei Standard-Listings fehlt der Block komplett. Nicht überspringen!
3. **franchisedirekt.com** — sehr selten echte Namen, oft "Profil nicht mehr aktiv" (404). Kurzer Blick reicht.
4. **FranchiseCHECK.de** — meist nur "{Firma} Team" ohne Personenname, gelegentlich echte Kontakte.
5. **franchiseERFOLGE.de** — selten brauchbar.
6. **fuer-gruender.de/franchiseboerse** — selten brauchbar.

**unternehmer-gesucht.com** ist eine FranchisePORTAL-Untermarke und zeigt dieselben Daten wie franchiseportal.de — kein separater Check nötig.

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

**Zwei-Stufen-Ansatz**:

- **Stufe 1 (Standard, schnell)**: `browser_navigate` → `browser_evaluate` mit gezielter Regex. Das ist der Default, weil es wenig Kontext verbraucht und auf den hier beschriebenen Seitenmustern verlässlich funktioniert.
- **Stufe 2 (Fallback)**: Wenn Stufe 1 **keinen Treffer** findet, **aber die Seite geladen wurde und nicht als "inaktiv" markiert ist**, ODER wenn Stufe 1 Daten liefert, die offensichtlich unsinnig wirken (z.B. Namen, die klar Sektions-Labels oder Firmennamen statt Personen sind, zerhackte Umlaute, Mehrfach-Whitespace-Müll, abgeschnittene Telefonnummern), dann `browser_snapshot` machen und die Seite normal visuell analysieren — so wie der Skill das vor der Regex-Optimierung gemacht hat. Der Snapshot zeigt Aufklapper, Tabs und Personen-Kacheln, die im reinen `innerText` manchmal nicht strukturiert ankommen.

Cookie-Banner stören die Textsuche meist nicht — nur wegklicken wenn die Seite sonst leer bleibt.

**Wann Stufe 2 eskalieren, wann nicht:**
- "Sucht aktuell nicht nach neuen Gründer:innen" erkannt → **kein** Fallback, das System rekrutiert schlicht nicht.
- 404 / "Profil nicht mehr aktiv" → **kein** Fallback, Seite existiert nicht.
- Regex liefert `none` auf einer geladenen, aktiven Seite → **Fallback snapshot**.
- Regex liefert einen Namen, der aber verdächtig aussieht (Firma, Label, offensichtlicher Parse-Fehler) → **Fallback snapshot zur Verifikation**.

#### B1: franchiseverband.com (Priorität 1)

1. `browser_navigate` → `https://www.franchiseverband.com/systeme-finden/franchisesystem-detail-ansicht/{slug}` (Slug aus WebSearch-Treffer, nicht raten).
2. Wenn Page-Title `Fehler404` → Seite ist offline, überspringen.
3. `browser_evaluate` mit dem Standard-Extractor:
   ```javascript
   () => {
     const text = document.body.innerText;
     const re = /ANSPRECHPARTNER/g;
     let m, positions = [];
     while ((m = re.exec(text)) !== null) positions.push(m.index);
     if (positions.length === 0) return 'none';
     // Letzter Treffer ist der echte Kontakt-Block (erster Treffer ist oft nur ein Abschnitts-Label im Fließtext)
     const last = positions[positions.length - 1];
     return text.substring(last, last + 800);
   }
   ```
4. Der Block hat das Format (stabil über alle franchiseverband.com-Seiten):
   ```
   ANSPRECHPARTNER
   Vollständiger Name
   Telefon +49 ...
   Mobile +49 ...          (optional)
   email@domain.de
   KONTAKT                 (Ende des Blocks)
   ```
5. Extrahiere **alle** Personen vor `KONTAKT` — manche Systeme haben 2 (z.B. Club Pilates, FITYES, PIRTEK).

#### B2: franchiseportal.de (Priorität 2)

1. `browser_navigate` → Portal-URL (Feld `Franchise-Portal URLs` im Record).
2. `browser_evaluate`:
   ```javascript
   () => {
     const text = document.body.innerText;
     // Muster für Premium-Listings: "Guten Tag, mein Name ist {Vor- und Nachname} und ich vertrete {Firma}."
     const m = text.match(/mein Name ist\s+([A-ZÄÖÜ][\wäöüß.\-]+(?:\s+[A-ZÄÖÜ][\wäöüß.\-]+)+)\s+und ich vertrete/);
     if (m) return {name: m[1]};
     // Fallback: "sucht (aktuell|über uns) nicht nach neuen" → kein aktiver Ansprechpartner
     if (/sucht (über uns|aktuell).*nicht nach neuen/i.test(text)) return 'inactive';
     return 'none';
   }
   ```
3. Wenn Treffer: als Kontakt mit `telefon: null`, `email: null`, `portal: "franchiseportal.de"` eintragen. **Namen-Only ist Normalfall** bei diesem Portal — Kontaktaufnahme läuft über das portaleigene Lead-Formular.
4. Bei `inactive` → Portal überspringen, aber weiter zu franchiseverband.com.

#### B3: Andere Portale (FranchiseCHECK, franchisedirekt, franchiseERFOLGE, fuer-gruender)

1. `browser_navigate` → URL.
2. Wenn Title `404` / `Profil nicht mehr aktiv` → überspringen.
3. `browser_evaluate` mit breiterem Muster:
   ```javascript
   () => {
     const text = document.body.innerText;
     for (const kw of ['Ansprechpartner', 'Franchise-Manager', 'Expansionsleit', 'Ihr Kontakt']) {
       const idx = text.indexOf(kw);
       if (idx >= 0) return text.substring(Math.max(0, idx-50), idx+500);
     }
     return 'none';
   }
   ```
4. Wenn generische Labels wie "{Firma} Team" ohne Personenname → kein Eintrag, weiter.

#### Generelle Regeln

- Falls Playwright blockiert wird (`ERR_TUNNEL_CONNECTION_FAILED`, HTTP 403, Cloudflare-Challenge, leerer Snapshot) → **Apify Website Content Crawler** (siehe Phase D).
- `browser_snapshot` ist der **Fallback** (Stufe 2), nicht der Standard — er produziert viel Kontext. Nutze ihn, wenn der Regex-Extractor nichts findet oder die Ergebnisse verdächtig aussehen (siehe Zwei-Stufen-Ansatz oben).
- Namen sind oft mit Umlauten (ß, ä, ö, ü) — im JSON nicht escapen, `json.dumps(ensure_ascii=False, ...)` kümmert sich darum.

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
