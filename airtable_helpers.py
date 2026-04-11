"""
Airtable-Helpers für das Impressum-Enrichment.

Liest Records, die Impressum-Daten brauchen, und schreibt Ergebnisse zurück.
Wird vom /scrape-impressum Skill aus dem Claude Code Chat aufgerufen.
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


def _headers():
    return {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}",
        "Content-Type": "application/json",
    }


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


# ---------------------------------------------------------------------------
# Lesen
# ---------------------------------------------------------------------------

def fetch_records_needing_impressum(view_id: str = AIRTABLE_VIEW_CLOSE_OFFEN,
                                    limit: int | None = None) -> list[dict]:
    """
    Lädt Records, die eine Webseite haben, aber noch keine Impressum-Daten.

    Args:
        view_id: Airtable View ID
        limit: Maximale Anzahl Records (None = alle)
    """
    fields = _BASE_FIELDS + _ADDRESS_FIELDS

    # Erster Versuch mit Adressfeldern; bei 422 ohne Adressfelder wiederholen
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
# Update-Payload bauen
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
    Baut das PATCH-Payload für einen Record.

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
# Schreiben
# ---------------------------------------------------------------------------

def update_single_record(record_id: str, fields: dict, dry_run: bool = False) -> bool:
    """
    Aktualisiert einen einzelnen Record in Airtable.

    Args:
        record_id: Airtable Record ID (recXXXXX)
        fields: Dict mit Feldname → Wert
        dry_run: Wenn True, wird nichts geschrieben
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

    Returns:
        Anzahl erfolgreich aktualisierter Records
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
# CLI-Hilfsfunktionen (für Aufruf aus dem Chat via python3 -c "...")
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python airtable_helpers.py list [limit]    — Offene Records auflisten")
        print("  python airtable_helpers.py get <record_id> — Einzelnen Record laden")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "list":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else None
        records = fetch_records_needing_impressum(limit=limit)
        for rec in records:
            f = rec.get("fields", {})
            name = f.get("NAME DES FRANCHISE-UNTERNEHMENS", "?")
            url = f.get("Webseite (https-Standardisiert)", f.get("Webseite", "?"))
            print(f"  {rec['id']}  {name}  →  {url}")
        print(f"\nGesamt: {len(records)} Records")

    elif cmd == "get":
        if len(sys.argv) < 3:
            print("Fehler: Record-ID angeben")
            sys.exit(1)
        rec = fetch_single_record(sys.argv[2])
        print(json.dumps(rec, indent=2, ensure_ascii=False))

    else:
        print(f"Unbekannter Befehl: {cmd}")
        sys.exit(1)
