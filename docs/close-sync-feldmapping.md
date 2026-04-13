# Close.com Sync — Feldmapping

Vollständiges Mapping aller Daten, die von Airtable nach Close.com übertragen werden.

## Lead-Grunddaten

| Close-Feld | Airtable-Quelle | Logik |
|---|---|---|
| **Name** | `NAME DES FRANCHISE-UNTERNEHMENS` + `Unternehmensname` | Wenn Unternehmensname vorhanden und abweichend: `"Franchise-Name (Unternehmensname)"` |
| **Description** | `Zusammenfassung (kurz)` | Direkt übernommen |
| **URL** | `Webseite (https-Standardisiert)` | Direkt übernommen |
| **Status** | — | Immer `Lead-Pool (Kaltakquise)` |

## Adresse

| Close-Feld | Airtable-Quelle |
|---|---|
| Address 1 | `Adresse` |
| City | `Stadt` |
| Zipcode | `Postleitzahl` |
| Country | Immer `"Deutschland"` (nur wenn mind. ein Adressfeld gesetzt) |

## Custom Fields

| Close Custom Field | Airtable-Quelle | Logik |
|---|---|---|
| **Branche** | `BRANCHE` | `"Franchise - {Branche}"` oder `"Franchise"` wenn leer |
| **Leadherkunft** | CLI-Argument `--leadherkunft` | Default: `Franchise_03022026` |
| **Import ID** | CLI-Argument `--import-id` | Default: `Franchise_03022026` |
| **Lead Datensatz ID** | CLI-Argument `--leadherkunft` | Gleicher Wert wie Leadherkunft |
| **Unternehmen** | `Unternehmensname` | Verifizierter Firmenname aus Schritt 1, Fallback auf Franchise-Name |
| **Airtable Record ID** | `record["id"]` | Airtable Record-ID (z.B. `recXXXXXXXXXXXXXX`) |
| **Airtable Record URL** | Generiert | `https://airtable.com/.../recXXX` |

## Kontakte

Kontakte werden in folgender Reihenfolge angelegt:

### 1. AP 1 (Hauptansprechpartner)

| Close-Feld | Airtable-Quelle |
|---|---|
| Name | `AP 1` + `AP 1 Position` → `"Name (Position)"` |
| Title | `AP 1 Position` |
| Email | `AP 1 Mail` (type: office) |
| Phone | `AP 1 Tel.` (type: **direct**) |

### 2. AP 2–5

Gleiche Struktur wie AP 1, aber Phone-Type ist `office` statt `direct`.

### 3. Weitere Ansprechpartner (aus JSON)

Das Airtable-Feld `Weitere Ansprechpartner` enthält ein JSON-Array mit Kontakten, die nicht in die 5 AP-Slots gepasst haben:

```json
[
  {"name": "Anna Braun", "position": "Head of Recruiting", "email": "a.braun@firma.de", "telefon": "+49 123 456789", "quelle": "linkedin.com"}
]
```

Jeder Eintrag wird als eigener Close-Kontakt angelegt.

### 4. Weitere Telefonnummern (aus JSON)

Das Airtable-Feld `Weitere Telefonnummern` enthält ein JSON-Array mit Abteilungs-/Durchwahl-Nummern:

```json
[
  {"nummer": "+49 30 123456-10", "typ": "abteilung", "bezeichnung": "Franchise-Abteilung", "email": "franchise@firma.de"}
]
```

Jeder Eintrag wird als Close-Kontakt angelegt mit `bezeichnung` als Name.

### 5. Allgemeine Kontaktinfos (Impressum)

| Close-Feld | Airtable-Quelle |
|---|---|
| Name | Immer `"Allgemeine Kontaktinfos"` |
| Email | `Impressum Mail` (type: office) |
| Phone | `Impressum Tel.` (type: office) |

## Opportunity

Zu jedem Lead wird automatisch eine Opportunity erstellt:

| Feld | Wert |
|---|---|
| Status | `Geprüfte Leads` |
| Value | `1000` |

## Notizen

Notizen werden in dieser Reihenfolge erstellt. Da Close die zuletzt erstellte Notiz oben anzeigt, erscheint **Relevante Infos** ganz oben.

### Reihenfolge in Close (von oben nach unten)

| # | Notiz | Airtable-Felder |
|---|---|---|
| 1 | **Relevante Infos** | `Relevante Infos` |
| 2 | **Franchise Analyse** | `Anzahl Standorte`, `Anzahl Mitarbeiter`, `Gründungsdatum`, `Ist es ein Franchise-System?` (Score + Begründung), `Zusammenfassung (lang)`, `Franchise-Portal URLs`, `Schritt 3: Kommentar` |
| 3 | **Werbeanzeigen Analyse** | `Meta Ads Status/Notizen/Links`, `Google Ads Status/Notizen/Links` |
| 4 | **Stellenportal Analyse** | `URL 1–3`, `Bewerbersoftware`, `Notiz`, `Stellenausschreibungs Notizen`, `Stellenausschreibungen` |
| 5 | **LinkedIn** | `AP 1 LinkedIn URL`, `LinkedIn Status` |
| 6 | **Dealfront Link** | `Dealfront` |

Jede Notiz wird nur erstellt, wenn mindestens ein Feld dafür Daten enthält.

## Rückschreibung nach Airtable

Nach erfolgreichem Import werden in Airtable gesetzt:

| Airtable-Feld | Wert |
|---|---|
| `Close Status` | `"done"` |
| `Close Lead ID` | Close Lead-ID (z.B. `lead_XXXX`) |
