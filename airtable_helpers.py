"""
Airtable-Helpers für die Lead-Enrichment-Pipeline.

Generische Infrastruktur für Multi-Step-Workflows:
- Felder anlegen (Meta API)
- Records pro Schritt laden
- Status-Tracking pro Schritt
- Sichere Updates (nie bestehende Daten überschreiben)
"""

import os
import json
import time
import logging
import requests
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)

AIRTABLE_API_KEY = os.getenv("airtable_api_key")
AIRTABLE_BASE_ID = "appXQm1LLHe3HdXXa"
AIRTABLE_TABLE_ID = "tblLfuRRrMMUPXeJR"
AIRTABLE_VIEW_CLOSE_OFFEN = "viwW2r72sFCjIuUat"

AIRTABLE_BASE_URL = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_ID}"
AIRTABLE_META_BASE_URL = f"https://api.airtable.com/v0/meta/bases/{AIRTABLE_BASE_ID}/tables"
AIRTABLE_META_FIELDS_URL = f"{AIRTABLE_META_BASE_URL}/{AIRTABLE_TABLE_ID}/fields"

STEP_STATUSES = {"In Bearbeitung", "Erfolgreich", "Mit Problemen"}


def _headers():
    return {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}",
        "Content-Type": "application/json",
    }


# ---------------------------------------------------------------------------
# Feld-Definitionen
# ---------------------------------------------------------------------------

_BASE_FIELDS = [
    "NAME DES FRANCHISE-UNTERNEHMENS",
    "Webseite",
    "Webseite (https-Standardisiert)",
    "Impressum Mail",
    "Impressum Tel.",
    "AP 1", "AP 1 Position",
    "AP 2", "AP 2 Position",
    "AP 3", "AP 3 Position",
    "AP 4", "AP 4 Position",
    "AP 5", "AP 5  Position",
]

_ADDRESS_FIELDS = ["Adresse", "Stadt", "Postleitzahl"]

_STEP_FIELDS = [
    "Schritt 1: Validierung",
    "Schritt 2: Impressum",
    "Unternehmensname",
    "Ist es ein Franchise-System?",
    "Ist es ein Franchise-System? Begründung",
    "Schritt 1: Datum",
    "Schritt 2: Datum",
]

# Felder, die per setup-fields angelegt werden sollen
FIELD_DEFINITIONS = [
    {
        "name": "Schritt 1: Validierung",
        "type": "singleSelect",
        "options": {
            "choices": [
                {"name": "In Bearbeitung", "color": "yellowBright"},
                {"name": "Erfolgreich", "color": "greenBright"},
                {"name": "Mit Problemen", "color": "redBright"},
            ]
        },
    },
    {
        "name": "Schritt 2: Impressum",
        "type": "singleSelect",
        "options": {
            "choices": [
                {"name": "In Bearbeitung", "color": "yellowBright"},
                {"name": "Erfolgreich", "color": "greenBright"},
                {"name": "Mit Problemen", "color": "redBright"},
            ]
        },
    },
    {
        "name": "Unternehmensname",
        "type": "singleLineText",
    },
    {
        "name": "Ist es ein Franchise-System?",
        "type": "percent",
        "options": {"precision": 0},
    },
    {
        "name": "Ist es ein Franchise-System? Begründung",
        "type": "multilineText",
    },
    {
        "name": "Schritt 1: Datum",
        "type": "date",
        "options": {"dateFormat": {"name": "european", "format": "D/M/YYYY"}},
    },
    {
        "name": "Schritt 2: Datum",
        "type": "date",
        "options": {"dateFormat": {"name": "european", "format": "D/M/YYYY"}},
    },
]


# ---------------------------------------------------------------------------
# Meta API: Felder anlegen
# ---------------------------------------------------------------------------

def ensure_fields_exist(field_definitions: list[dict] | None = None,
                        dry_run: bool = False) -> list[str]:
    """
    Erstellt fehlende Felder in Airtable via Meta API.

    Returns:
        Liste der neu erstellten Feldnamen
    """
    if field_definitions is None:
        field_definitions = FIELD_DEFINITIONS

    # Bestehende Felder laden (über /meta/bases/{id}/tables, dann richtige Tabelle finden)
    resp = requests.get(AIRTABLE_META_BASE_URL, headers=_headers())
    resp.raise_for_status()
    tables = resp.json().get("tables", [])
    table = next((t for t in tables if t["id"] == AIRTABLE_TABLE_ID), None)
    if not table:
        raise RuntimeError(f"Tabelle {AIRTABLE_TABLE_ID} nicht gefunden")
    existing_names = {f["name"] for f in table.get("fields", [])}

    created = []
    for field_def in field_definitions:
        name = field_def["name"]
        if name in existing_names:
            log.info(f"  Feld '{name}' existiert bereits — übersprungen")
            continue

        if dry_run:
            log.info(f"  [DRY RUN] Würde Feld '{name}' anlegen ({field_def['type']})")
            created.append(name)
            continue

        resp = requests.post(AIRTABLE_META_FIELDS_URL, headers=_headers(), json=field_def)
        resp.raise_for_status()
        created.append(name)
        log.info(f"  Feld '{name}' angelegt ({field_def['type']})")
        time.sleep(0.25)

    return created


# ---------------------------------------------------------------------------
# Lesen: Generisch pro Schritt
# ---------------------------------------------------------------------------

def fetch_records_for_step(step_field: str,
                           fields: list[str] | None = None,
                           view_id: str = AIRTABLE_VIEW_CLOSE_OFFEN,
                           limit: int | None = None) -> list[dict]:
    """
    Lädt Records, bei denen ein bestimmtes Schritt-Statusfeld leer ist.

    Args:
        step_field: Name des Status-Felds (z.B. "Schritt 1: Validierung")
        fields: Welche Felder laden (None = alle Standard-Felder)
        view_id: Airtable View ID
        limit: Maximale Anzahl Records
    """
    if fields is None:
        fields = _BASE_FIELDS + _ADDRESS_FIELDS + _STEP_FIELDS

    params = {
        "view": view_id,
        "pageSize": 100,
        "filterByFormula": f"{{{step_field}}} = ''",
        "fields[]": fields,
    }

    all_records = []
    while True:
        resp = requests.get(AIRTABLE_BASE_URL, headers=_headers(), params=params)
        if resp.status_code == 422:
            log.warning(f"Einige Felder nicht vorhanden — bitte 'setup-fields' ausführen")
            # Fallback: nur Basis-Felder
            params["fields[]"] = _BASE_FIELDS
            resp = requests.get(AIRTABLE_BASE_URL, headers=_headers(), params=params)
        resp.raise_for_status()
        data = resp.json()
        all_records.extend(data.get("records", []))

        if limit and len(all_records) >= limit:
            all_records = all_records[:limit]
            break

        offset = data.get("offset")
        if not offset:
            break
        params["offset"] = offset
        time.sleep(0.2)

    return all_records


# ---------------------------------------------------------------------------
# Lesen: Legacy + Einzelrecord
# ---------------------------------------------------------------------------

def fetch_records_needing_impressum(view_id: str = AIRTABLE_VIEW_CLOSE_OFFEN,
                                    limit: int | None = None) -> list[dict]:
    """
    Lädt Records, die eine Webseite haben, aber noch keine Impressum-Daten.
    (Legacy-Funktion für Rückwärtskompatibilität)
    """
    fields = _BASE_FIELDS + _ADDRESS_FIELDS

    resp = requests.get(AIRTABLE_BASE_URL, headers=_headers(), params={
        "view": view_id, "pageSize": 1,
        "filterByFormula": "AND({Webseite} != '', {Impressum Mail} = '', {Impressum Tel.} = '')",
        "fields[]": fields,
    })
    if resp.status_code == 422:
        log.warning("Adressfelder noch nicht in Airtable vorhanden — werden übersprungen")
        fields = _BASE_FIELDS

    params = {
        "view": view_id,
        "pageSize": 100,
        "filterByFormula": "AND({Webseite} != '', {Impressum Mail} = '', {Impressum Tel.} = '')",
        "fields[]": fields,
    }

    all_records = []
    while True:
        resp = requests.get(AIRTABLE_BASE_URL, headers=_headers(), params=params)
        resp.raise_for_status()
        data = resp.json()
        all_records.extend(data.get("records", []))

        if limit and len(all_records) >= limit:
            all_records = all_records[:limit]
            break

        offset = data.get("offset")
        if not offset:
            break
        params["offset"] = offset
        time.sleep(0.2)

    log.info(f"{len(all_records)} Records ohne Impressum-Daten geladen")
    return all_records


def fetch_single_record(record_id: str) -> dict:
    """Lädt einen einzelnen Record anhand seiner ID."""
    resp = requests.get(f"{AIRTABLE_BASE_URL}/{record_id}", headers=_headers())
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Update-Payload bauen (Impressum-spezifisch, Legacy)
# ---------------------------------------------------------------------------

def _find_free_ap_slots(fields: dict) -> list[int]:
    """Findet freie AP-Slots (1-5)."""
    free = []
    for i in range(1, 6):
        ap_key = f"AP {i}"
        if not fields.get(ap_key, "").strip():
            free.append(i)
    return free


def build_update_payload(record_id: str, fields: dict,
                         email: str | None, phone: str | None,
                         geschaeftsfuehrer: list[str],
                         adresse: str | None = None,
                         plz: str | None = None,
                         ort: str | None = None) -> dict | None:
    """
    Baut das PATCH-Payload für einen Record (Impressum-spezifisch).

    Setzt nur Felder, die aktuell leer sind — überschreibt nie bestehende Daten.
    """
    update_fields = {}

    if email and not fields.get("Impressum Mail", "").strip():
        update_fields["Impressum Mail"] = email

    if phone and not fields.get("Impressum Tel.", "").strip():
        update_fields["Impressum Tel."] = phone

    if geschaeftsfuehrer:
        free_slots = _find_free_ap_slots(fields)
        for name, slot in zip(geschaeftsfuehrer, free_slots):
            update_fields[f"AP {slot}"] = name
            # Quirk: AP 5 hat doppeltes Leerzeichen im Feldnamen
            pos_key = "AP 5  Position" if slot == 5 else f"AP {slot} Position"
            update_fields[pos_key] = "Geschäftsführer"

    if adresse and not fields.get("Adresse", "").strip():
        update_fields["Adresse"] = adresse

    if plz and not fields.get("Postleitzahl", "").strip():
        update_fields["Postleitzahl"] = plz

    if ort and not fields.get("Stadt", "").strip():
        update_fields["Stadt"] = ort

    if not update_fields:
        return None

    return {"id": record_id, "fields": update_fields}


# ---------------------------------------------------------------------------
# Schreiben: Generisch
# ---------------------------------------------------------------------------

def update_record_fields(record_id: str, fields: dict,
                         protect_existing: bool = True,
                         dry_run: bool = False) -> dict:
    """
    Generisches Update für beliebige Felder.

    Args:
        record_id: Airtable Record ID
        fields: Dict mit Feldname → Wert
        protect_existing: Wenn True, werden bereits befüllte Felder übersprungen
        dry_run: Wenn True, wird nichts geschrieben

    Returns:
        Dict der tatsächlich geschriebenen Felder
    """
    write_fields = dict(fields)

    if protect_existing:
        rec = fetch_single_record(record_id)
        existing = rec.get("fields", {})
        skipped = []
        for key in list(write_fields.keys()):
            val = existing.get(key)
            if val is not None and str(val).strip():
                skipped.append(key)
                del write_fields[key]
        if skipped:
            log.info(f"  Übersprungen (bereits befüllt): {', '.join(skipped)}")

    if not write_fields:
        log.info("  Keine neuen Daten zum Schreiben")
        return {}

    if dry_run:
        print(f"[DRY RUN] Würde {record_id} updaten:")
        print(json.dumps(write_fields, indent=2, ensure_ascii=False))
        return write_fields

    resp = requests.patch(
        f"{AIRTABLE_BASE_URL}/{record_id}",
        headers=_headers(),
        json={"fields": write_fields},
    )
    resp.raise_for_status()
    return write_fields


STEP_DATE_FIELDS = {
    "Schritt 1: Validierung": "Schritt 1: Datum",
    "Schritt 2: Impressum": "Schritt 2: Datum",
}


def set_step_status(record_id: str, step_field: str, status: str,
                    dry_run: bool = False) -> bool:
    """
    Setzt den Status eines Schritts für einen Record.
    Bei "Erfolgreich" oder "Mit Problemen" wird automatisch das Datum gesetzt.

    Args:
        record_id: Airtable Record ID
        step_field: Name des Status-Felds (z.B. "Schritt 1: Validierung")
        status: "In Bearbeitung", "Erfolgreich", oder "Mit Problemen"
        dry_run: Wenn True, wird nichts geschrieben
    """
    from datetime import date

    if status not in STEP_STATUSES:
        raise ValueError(f"Ungültiger Status '{status}'. Erlaubt: {STEP_STATUSES}")

    fields = {step_field: status}

    # Bei Abschluss (Erfolgreich/Mit Problemen) automatisch Datum setzen
    if status in ("Erfolgreich", "Mit Problemen"):
        date_field = STEP_DATE_FIELDS.get(step_field)
        if date_field:
            fields[date_field] = date.today().isoformat()

    if dry_run:
        print(f"[DRY RUN] {record_id}: {fields}")
        return False

    resp = requests.patch(
        f"{AIRTABLE_BASE_URL}/{record_id}",
        headers=_headers(),
        json={"fields": fields},
    )
    resp.raise_for_status()
    return True


def update_single_record(record_id: str, fields: dict, dry_run: bool = False) -> bool:
    """
    Aktualisiert einen einzelnen Record in Airtable (Legacy-Funktion).
    """
    if dry_run:
        print(f"[DRY RUN] Würde {record_id} updaten:")
        print(json.dumps(fields, indent=2, ensure_ascii=False))
        return False

    resp = requests.patch(
        f"{AIRTABLE_BASE_URL}/{record_id}",
        headers=_headers(),
        json={"fields": fields},
    )
    resp.raise_for_status()
    return True


def batch_update_records(updates: list[dict], dry_run: bool = False) -> int:
    """
    Schreibt Updates in Batches nach Airtable (max 10 pro Request).
    """
    if dry_run:
        log.info(f"[DRY RUN] {len(updates)} Records würden aktualisiert")
        return 0

    updated = 0
    for i in range(0, len(updates), 10):
        batch = updates[i:i + 10]
        payload = {"records": batch}
        resp = requests.patch(AIRTABLE_BASE_URL, headers=_headers(), json=payload)
        resp.raise_for_status()
        updated += len(batch)
        log.info(f"  Batch aktualisiert: {updated}/{len(updates)}")
        time.sleep(0.25)

    return updated


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _print_records(records: list[dict]):
    """Gibt Records formatiert aus."""
    for rec in records:
        f = rec.get("fields", {})
        name = f.get("NAME DES FRANCHISE-UNTERNEHMENS", "?")
        url = f.get("Webseite (https-Standardisiert)", f.get("Webseite", "?"))
        print(f"  {rec['id']}  {name}  →  {url}")
    print(f"\nGesamt: {len(records)} Records")


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python airtable_helpers.py list [limit]         — Offene Impressum-Records")
        print("  python airtable_helpers.py get <record_id>      — Einzelnen Record laden")
        print("  python airtable_helpers.py setup-fields         — Neue Felder anlegen")
        print("  python airtable_helpers.py step1 [limit]        — Records für Schritt 1")
        print("  python airtable_helpers.py step2 [limit]        — Records für Schritt 2")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "list":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else None
        records = fetch_records_needing_impressum(limit=limit)
        _print_records(records)

    elif cmd == "get":
        if len(sys.argv) < 3:
            print("Fehler: Record-ID angeben")
            sys.exit(1)
        rec = fetch_single_record(sys.argv[2])
        print(json.dumps(rec, indent=2, ensure_ascii=False))

    elif cmd == "setup-fields":
        dry_run = "--dry-run" in sys.argv
        print("Prüfe und erstelle fehlende Felder...")
        created = ensure_fields_exist(dry_run=dry_run)
        if created:
            print(f"\n{len(created)} Feld(er) {'würden angelegt' if dry_run else 'angelegt'}:")
            for name in created:
                print(f"  + {name}")
        else:
            print("\nAlle Felder existieren bereits.")

    elif cmd == "step1":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else None
        records = fetch_records_for_step("Schritt 1: Validierung", limit=limit)
        print(f"{len(records)} Records brauchen Schritt 1 (Validierung):")
        _print_records(records)

    elif cmd == "step2":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else None
        records = fetch_records_for_step("Schritt 2: Impressum", limit=limit)
        print(f"{len(records)} Records brauchen Schritt 2 (Impressum):")
        _print_records(records)

    else:
        print(f"Unbekannter Befehl: {cmd}")
        sys.exit(1)
