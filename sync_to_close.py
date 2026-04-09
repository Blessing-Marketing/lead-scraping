#!/usr/bin/env python3
"""
Sync leads from Airtable to Close.com CRM.
Repliziert den bestehenden Make.com-Flow als eigenständiges Skript.

Usage:
    python sync_to_close.py --dry-run                  # Testlauf ohne Import
    python sync_to_close.py                             # Leads importieren
    python sync_to_close.py --leadherkunft "Neue_Quelle_2026"
"""

import os
import sys
import time
import logging
import argparse
import requests
from dotenv import load_dotenv

load_dotenv()

# ── API Keys ──────────────────────────────────────────────────────────────────
AIRTABLE_API_KEY = os.getenv("airtable_api_key")
CLOSE_API_KEY = os.getenv("close_api_key")

# ── Airtable Config ──────────────────────────────────────────────────────────
AIRTABLE_BASE_ID = "appXQm1LLHe3HdXXa"
AIRTABLE_TABLE_ID = "tblLfuRRrMMUPXeJR"
AIRTABLE_VIEW_ID = "viwW2r72sFCjIuUat"  # View "Close"
AIRTABLE_RECORD_URL_BASE = "https://airtable.com/appyXTRreRntxSwR3/tblBBrbnUXI9sX7cA"

# ── Close.com Custom Field IDs (aus Make-Blueprint) ─────────────────────────
CF = {
    "Branche":            "cf_iRwWZ6gyZhQL17SV3hTDbOLmTsCzpxoOfahUSOU6zGs",
    "Leadherkunft":       "cf_1PHp6ZpNi2rjg6hCkCmYKa2VvUjK7woQjRL4ahjdtIM",
    "Import ID":          "cf_HuR3fLgETfYACXPDjURS65s05kA8skWU4OzW04KGKjS",
    "Lead Datensatz ID":  "cf_igqmAUSRFbvf1lQS37Iqd3zzNgwzLPyCTYASIEVhASr",
    "Airtable Record ID": "cf_pPKgshKcy7QKFYiGK8Ow7KwOKtoZSO9GjM8tNd9qzo9",
    "Airtable Record URL":"cf_tgpoJddbH07dVQieMTKGoiOTF94KwKASSvG4Wq8mhXe",
    "Registernummer":     "cf_3sueb0tcenYn3ceCD7HnmUQo5VkSnRIiUuISNiCbonl",
    "Unternehmen":        "cf_IDCbxpBtU71D6zaMOCO9Za7bp6q4EJn3cf6RFom7ssX",
}

# ── Close.com Status IDs (aus Make-Blueprint) ───────────────────────────────
LEAD_STATUS_ID = "stat_y1JxRhELeq4M4WmlwLq45Zc4hImO8mfhPY3tRy0ChR9"  # Lead-Pool (Kaltakquise)
OPP_STATUS_ID = "stat_u3BnmUsqNj88UIDADi3C3lB2TuXqeQEyJ1ZtZ6n3is1"   # Geprüfte Leads
OPP_DEFAULT_VALUE = 1000

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)


# ── Close.com API Client ─────────────────────────────────────────────────────

class CloseClient:
    BASE_URL = "https://api.close.com/api/v1"

    def __init__(self, api_key):
        self.session = requests.Session()
        self.session.auth = (api_key, "")
        self.session.headers.update({"Content-Type": "application/json"})

    def _request(self, method, path, **kwargs):
        url = f"{self.BASE_URL}{path}"
        resp = self.session.request(method, url, **kwargs)
        if resp.status_code == 429:
            retry_after = float(resp.headers.get("retry-after", 2))
            log.warning(f"Rate limited – warte {retry_after}s ...")
            time.sleep(retry_after)
            resp = self.session.request(method, url, **kwargs)
        resp.raise_for_status()
        return resp.json() if resp.content else None

    def create_lead(self, lead_data):
        """Neuen Lead in Close anlegen."""
        return self._request("POST", "/lead/", json=lead_data)

    def create_opportunity(self, lead_id, status_id=OPP_STATUS_ID, value=OPP_DEFAULT_VALUE):
        """Opportunity zum Lead hinzufügen."""
        return self._request("POST", "/opportunity/", json={
            "lead_id": lead_id,
            "status_id": status_id,
            "value": value,
        })

    def create_note(self, lead_id, note_html):
        """Notiz zum Lead hinzufügen."""
        return self._request("POST", "/activity/note/", json={
            "lead_id": lead_id,
            "note": note_html,
        })

    def delete_lead(self, lead_id):
        """Lead löschen (für Tests)."""
        return self._request("DELETE", f"/lead/{lead_id}")


# ── Airtable API ─────────────────────────────────────────────────────────────

def fetch_airtable_records():
    """Alle Records aus der konfigurierten Airtable-View laden (mit Pagination)."""
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_ID}"
    headers = {"Authorization": f"Bearer {AIRTABLE_API_KEY}"}
    params = {"view": AIRTABLE_VIEW_ID, "pageSize": 100}

    all_records = []
    while True:
        resp = requests.get(url, headers=headers, params=params)
        resp.raise_for_status()
        data = resp.json()
        all_records.extend(data.get("records", []))

        offset = data.get("offset")
        if not offset:
            break
        params["offset"] = offset
        time.sleep(0.2)

    log.info(f"{len(all_records)} Records aus Airtable geladen")
    return all_records


def update_airtable_after_import(record_id, close_lead_id):
    """'Close Status' und 'Close Lead ID' in Airtable nach Import setzen."""
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_ID}/{record_id}"
    headers = {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {"fields": {
        "Close Status": "done",
        "Close Lead ID": close_lead_id,
    }}
    resp = requests.patch(url, headers=headers, json=payload)
    resp.raise_for_status()


# ── Contact Builder ──────────────────────────────────────────────────────────

def build_contact(name, position, email, phone, phone_type="office"):
    """Einzelnen Contact bauen. Gibt None zurück wenn kein Name vorhanden."""
    if not name or not name.strip():
        return None

    contact = {}
    clean_name = name.strip()
    clean_position = position.strip() if position else ""

    if clean_position:
        contact["name"] = f"{clean_name} ({clean_position})"
        contact["title"] = clean_position
    else:
        contact["name"] = clean_name

    if email and email.strip():
        contact["emails"] = [{"email": email.strip(), "type": "office"}]

    if phone and phone.strip():
        contact["phones"] = [{"phone": phone.strip(), "type": phone_type}]

    return contact


# ── Note Builder ─────────────────────────────────────────────────────────────

def _clean(value):
    """Feldwert bereinigen: Listen joinen, Whitespace strippen, leer → None."""
    if isinstance(value, list):
        value = ", ".join(str(v) for v in value if v)
    if not value or not str(value).strip():
        return None
    return str(value).strip()


def build_notes(fields):
    """Notiz-Texte aus Airtable-Fields generieren. Nur wenn echte Daten vorhanden."""
    notes = []

    # 1. Dealfront-Link
    dealfront = _clean(fields.get("Dealfront"))
    if dealfront:
        notes.append(f"**Dealfront Link:**\n{dealfront}")

    # 2. LinkedIn
    linkedin_url = _clean(fields.get("AP 1 LinkedIn URL"))
    linkedin_status = _clean(fields.get("LinkedIn Status"))
    if linkedin_url or linkedin_status:
        parts = ["**LinkedIn:**"]
        if linkedin_url:
            parts.append(f"\nURL:\n{linkedin_url}")
        if linkedin_status:
            parts.append(f"\nStatus: {linkedin_status}")
        notes.append("\n".join(parts))

    # 3. Stellenportal-Analyse
    url1 = _clean(fields.get("URL 1"))
    url2 = _clean(fields.get("URL 2"))
    url3 = _clean(fields.get("URL 3"))
    bewerbersoftware = _clean(fields.get("Bewerbersoftware"))
    notiz = _clean(fields.get("Notiz"))
    stellen_notizen = _clean(fields.get("Stellenausschreibungs Notizen"))
    stellen = _clean(fields.get("Stellenausschreibungen"))
    if any([url1, url2, url3, bewerbersoftware, stellen_notizen, stellen]):
        parts = ["**Stellenportal Analyse:**"]
        urls = "\n".join(u for u in [url1, url2, url3] if u)
        if urls:
            parts.append(f"\nURL:\n{urls}")
        if bewerbersoftware:
            parts.append(f"\nBewerbersoftware:\n{bewerbersoftware}")
        if notiz:
            parts.append(notiz)
        if stellen_notizen:
            parts.append(f"\nNotizen:\n{stellen_notizen}")
        if stellen:
            parts.append(f"\nArt der Stellenausschreibungen:\n{stellen}")
        notes.append("\n".join(parts))

    # 4. Werbeanzeigen-Analyse
    meta_status = _clean(fields.get("Meta Ads Status"))
    meta_notizen = _clean(fields.get("Meta Ads Notizen"))
    meta_links = _clean(fields.get("Meta Ads Links"))
    google_status = _clean(fields.get("Google Ads Status"))
    google_notizen = _clean(fields.get("Google Ads Notizen"))
    google_links = _clean(fields.get("Google Ads Links"))
    if any([meta_status, meta_notizen, meta_links, google_status, google_notizen, google_links]):
        parts = ["**Werbeanzeigen Analyse:**"]
        if any([meta_status, meta_notizen, meta_links]):
            parts.append("\nMeta Ads:")
            if meta_status:
                parts.append(meta_status)
            if meta_notizen:
                parts.append(f"Notizen: {meta_notizen}")
            if meta_links:
                parts.append(f"Links: {meta_links}")
        if any([google_status, google_notizen, google_links]):
            if any([meta_status, meta_notizen, meta_links]):
                parts.append("\n____________________")
            parts.append("\nGoogle Ads:")
            if google_status:
                parts.append(google_status)
            if google_notizen:
                parts.append(f"Notizen: {google_notizen}")
            if google_links:
                parts.append(f"Links: {google_links}")
        notes.append("\n".join(parts))

    return notes


# ── Lead Mapping ─────────────────────────────────────────────────────────────

def map_record_to_lead(record, leadherkunft, import_id):
    """Airtable Record → Close Lead Payload (mit hardcoded Custom Field IDs)."""
    f = record.get("fields", {})
    record_id = record["id"]
    firma = (f.get("NAME DES FRANCHISE-UNTERNEHMENS") or "").strip()

    # ── Contacts ──
    contacts = []

    # AP 1 (Telefon als "direct")
    c = build_contact(f.get("AP 1"), f.get("AP 1 Position"),
                      f.get("AP 1 Mail"), f.get("AP 1 Tel."), "direct")
    if c:
        contacts.append(c)

    # AP 2–5 (Telefon als "office")
    for i in range(2, 6):
        pos_key = "AP 5  Position" if i == 5 else f"AP {i} Position"
        c = build_contact(
            f.get(f"AP {i}"), f.get(pos_key),
            f.get(f"AP {i} Mail"), f.get(f"AP {i} Tel."),
        )
        if c:
            contacts.append(c)

    # Allgemeine Kontaktinfos (Impressum)
    impressum_mail = (f.get("Impressum Mail") or "").strip()
    impressum_tel = (f.get("Impressum Tel.") or "").strip()
    if impressum_mail or impressum_tel:
        impressum = {"name": "Allgemeine Kontaktinfos"}
        if impressum_mail:
            impressum["emails"] = [{"email": impressum_mail, "type": "office"}]
        if impressum_tel:
            impressum["phones"] = [{"phone": impressum_tel, "type": "office"}]
        contacts.append(impressum)

    # ── Lead Payload ──
    lead = {
        "name": firma,
        "contacts": contacts,
        "status_id": LEAD_STATUS_ID,
    }

    # Webseite
    url = (f.get("Webseite (https-Standardisiert)") or "").strip()
    if url:
        lead["url"] = url

    # Adresse – nur setzen wenn konkrete Daten vorhanden (nicht nur "Deutschland")
    address = {}
    addr_street = (f.get("Adresse") or "").strip()
    addr_city = (f.get("Stadt") or "").strip()
    addr_zip = (f.get("Postleitzahl") or "").strip()
    if addr_street:
        address["address_1"] = addr_street
    if addr_city:
        address["city"] = addr_city
    if addr_zip:
        address["zipcode"] = addr_zip
    if address:
        address["country"] = "Deutschland"
        lead["addresses"] = [address]

    # ── Custom Fields (hardcoded IDs aus Make-Blueprint) ──
    def _set(cf_key, value):
        if value and str(value).strip():
            lead[f"custom.{CF[cf_key]}"] = str(value).strip()

    branche = (f.get("BRANCHE") or "").strip()
    _set("Branche", f"Franchise - {branche}" if branche else "Franchise")
    _set("Leadherkunft", leadherkunft)
    _set("Import ID", import_id)
    _set("Lead Datensatz ID", leadherkunft)
    _set("Unternehmen", firma)
    _set("Airtable Record ID", record_id)
    _set("Airtable Record URL", f"{AIRTABLE_RECORD_URL_BASE}/{record_id}")

    return lead


# ── Kompletter Import-Durchlauf für einen Record ────────────────────────────

def import_single_record(close, record, leadherkunft, import_id):
    """
    Kompletter Import eines Airtable-Records nach Close:
    1. Lead erstellen
    2. Opportunity erstellen
    3. Notizen erstellen
    Gibt die Close Lead-ID zurück.
    """
    fields = record.get("fields", {})
    firma = (fields.get("NAME DES FRANCHISE-UNTERNEHMENS") or "Unbekannt").strip()

    # 1. Lead erstellen
    lead_data = map_record_to_lead(record, leadherkunft, import_id)
    result = close.create_lead(lead_data)
    lead_id = result["id"]
    log.info(f"  Lead erstellt: {firma} → {lead_id}")

    # 2. Opportunity erstellen
    opp = close.create_opportunity(lead_id)
    log.info(f"  Opportunity erstellt: {opp['id']} (Value: {OPP_DEFAULT_VALUE})")

    # 3. Notizen erstellen
    notes = build_notes(fields)
    for note_text in notes:
        close.create_note(lead_id, note_text)
    log.info(f"  {len(notes)} Notizen erstellt")

    return lead_id


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Leads aus Airtable nach Close.com importieren"
    )
    parser.add_argument(
        "--leadherkunft", default="Franchise_03022026",
        help="Wert für das Close-Feld 'Leadherkunft' (default: Franchise_03022026)",
    )
    parser.add_argument(
        "--import-id", default="Franchise_03022026",
        help="Wert für das Close-Feld 'Import ID' (default: Franchise_03022026)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Nur anzeigen was passieren würde, nichts importieren",
    )
    parser.add_argument(
        "--no-update-airtable", action="store_true",
        help="Airtable 'Close Status' NICHT aktualisieren",
    )
    parser.add_argument(
        "--include-imported", action="store_true",
        help="Auch bereits importierte Records nochmal importieren",
    )
    args = parser.parse_args()

    if not AIRTABLE_API_KEY or not CLOSE_API_KEY:
        log.error("API Keys fehlen! Bitte .env prüfen (close_api_key, airtable_api_key).")
        sys.exit(1)

    close = CloseClient(CLOSE_API_KEY)
    records = fetch_airtable_records()

    created = 0
    skipped = 0
    errors = 0

    for i, record in enumerate(records, 1):
        fields = record.get("fields", {})
        firma = (fields.get("NAME DES FRANCHISE-UNTERNEHMENS") or "Unbekannt").strip()
        close_status = fields.get("Close Status", "") or ""

        if not args.include_imported and close_status == "done":
            log.info(f"  [{i}/{len(records)}] Übersprungen (bereits importiert): {firma}")
            skipped += 1
            continue

        if args.dry_run:
            lead_data = map_record_to_lead(record, args.leadherkunft, args.import_id)
            n_contacts = len(lead_data.get("contacts", []))
            n_notes = len(build_notes(fields))
            log.info(f"  [{i}/{len(records)}] [DRY RUN] {firma} – {n_contacts} Kontakte, {n_notes} Notizen")
            created += 1
            continue

        try:
            lead_id = import_single_record(close, record, args.leadherkunft, args.import_id)

            if not args.no_update_airtable:
                update_airtable_after_import(record["id"], lead_id)
                log.info(f"  Airtable Status → done, Close Lead ID → {lead_id}")

            created += 1
            time.sleep(0.25)

        except requests.exceptions.HTTPError as e:
            log.error(f"  [{i}/{len(records)}] Fehler bei {firma}: {e}")
            if hasattr(e, "response") and e.response is not None:
                log.error(f"    Response: {e.response.text[:500]}")
            errors += 1

    log.info("")
    log.info(f"Fertig! Erstellt: {created} | Übersprungen: {skipped} | Fehler: {errors}")


if __name__ == "__main__":
    main()
