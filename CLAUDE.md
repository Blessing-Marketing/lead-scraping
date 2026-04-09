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

## API-Konfiguration

- Close.com API Key: `close_api_key` in `.env`
- Airtable API Key: `airtable_api_key` in `.env`
- Beide Keys haben **Admin-Zugriff** – entsprechend vorsichtig behandeln
