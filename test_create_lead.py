#!/usr/bin/env python3
"""
Erstellt einen einzelnen Test-Lead in Close.com mit Demo-Daten.
Dient zum Testen des Imports, bevor der komplette Sync läuft.

Usage:
    python test_create_lead.py              # Demo-Lead erstellen
    python test_create_lead.py --delete     # Demo-Lead erstellen und direkt wieder löschen
"""

import json
import argparse
from sync_to_close import (
    CloseClient,
    CLOSE_API_KEY,
    LEAD_STATUS_ID,
    OPP_STATUS_ID,
    OPP_DEFAULT_VALUE,
    CF,
    build_contact,
    build_notes,
    log,
)


# ── Demo-Daten (simuliert einen Airtable-Record) ────────────────────────────

DEMO_RECORD = {
    "id": "rec_TEST_DEMO_12345",
    "fields": {
        "NAME DES FRANCHISE-UNTERNEHMENS": "DEMO Testfirma GmbH (BITTE LÖSCHEN)",
        "BRANCHE": "Gastronomie",
        "Webseite (https-Standardisiert)": "https://www.example.com",

        # AP 1 - Hauptansprechpartner
        "AP 1": "Max Mustermann",
        "AP 1 Position": "Geschäftsführer",
        "AP 1 Mail": "max@example.com",
        "AP 1 Tel.": "+49 123 456789",
        "AP 1 LinkedIn URL": "https://linkedin.com/in/maxmustermann",

        # AP 2
        "AP 2": "Erika Musterfrau",
        "AP 2 Position": "Head of HR",
        "AP 2 Mail": "erika@example.com",
        "AP 2 Tel.": "+49 123 456790",

        # AP 3 (leer – wird übersprungen)
        "AP 3": "",
        "AP 3 Position": "",
        "AP 3 Mail": "",
        "AP 3 Tel.": "",

        # Impressum
        "Impressum Tel.": "+49 123 000000",
        "Impressum Mail": "info@example.com",

        # Analyse-Daten für Notizen
        "Dealfront": "https://dealfront.com/demo-link",
        "LinkedIn Status": "Vernetzt",
        "URL 1": "https://www.example.com/karriere",
        "Bewerbersoftware": "Personio",
        "Stellenausschreibungs Notizen": "Aktiv auf Indeed und Stepstone",
        "Stellenausschreibungen": ["Indeed pro Standort", "Webseite Franchiseübergreifend"],
        "Meta Ads Status": ["Recruiting Ads (Regional)"],
        "Meta Ads Notizen": "Schaltet regionale Recruiting-Anzeigen",
        "Meta Ads Links": "https://facebook.com/ads/demo",
        "Google Ads Status": [],
        "Google Ads Notizen": "Keine Google Ads gefunden",
        "Google Ads Links": "",
    },
}


def create_demo_lead(close, delete_after=False):
    """
    Erstellt einen kompletten Demo-Lead in Close (Lead + Opportunity + Notizen).
    Gibt die Lead-ID zurück.
    """
    fields = DEMO_RECORD["fields"]
    firma = fields["NAME DES FRANCHISE-UNTERNEHMENS"]

    print(f"\n{'='*60}")
    print(f"  Demo-Lead erstellen: {firma}")
    print(f"{'='*60}\n")

    # ── 1. Lead-Payload bauen ──
    contacts = []

    c1 = build_contact(
        fields["AP 1"], fields["AP 1 Position"],
        fields["AP 1 Mail"], fields["AP 1 Tel."], "direct",
    )
    if c1:
        contacts.append(c1)

    c2 = build_contact(
        fields["AP 2"], fields["AP 2 Position"],
        fields["AP 2 Mail"], fields["AP 2 Tel."],
    )
    if c2:
        contacts.append(c2)

    # Impressum
    contacts.append({
        "name": "Allgemeine Kontaktinfos",
        "emails": [{"email": fields["Impressum Mail"], "type": "office"}],
        "phones": [{"phone": fields["Impressum Tel."], "type": "office"}],
    })

    lead_data = {
        "name": firma,
        "url": fields["Webseite (https-Standardisiert)"],
        "status_id": LEAD_STATUS_ID,
        "contacts": contacts,
        f"custom.{CF['Branche']}": f"Franchise - {fields['BRANCHE']}",
        f"custom.{CF['Leadherkunft']}": "TEST_DEMO",
        f"custom.{CF['Import ID']}": "TEST_DEMO",
        f"custom.{CF['Lead Datensatz ID']}": "TEST_DEMO",
        f"custom.{CF['Unternehmen']}": firma,
        f"custom.{CF['Airtable Record ID']}": DEMO_RECORD["id"],
        f"custom.{CF['Airtable Record URL']}": f"https://airtable.com/demo/{DEMO_RECORD['id']}",
    }

    print("1. Lead erstellen ...")
    print(f"   Payload:\n{json.dumps(lead_data, indent=2, ensure_ascii=False)}\n")

    result = close.create_lead(lead_data)
    lead_id = result["id"]
    print(f"   ✓ Lead erstellt: {lead_id}")
    print(f"   URL: https://app.close.com/lead/{lead_id}/\n")

    # ── 2. Opportunity ──
    print("2. Opportunity erstellen ...")
    opp = close.create_opportunity(lead_id)
    print(f"   ✓ Opportunity erstellt: {opp['id']} (Value: {OPP_DEFAULT_VALUE}, Status: Geprüfte Leads)\n")

    # ── 3. Notizen ──
    notes = build_notes(fields)
    print(f"3. {len(notes)} Notizen erstellen ...")
    for i, note_text in enumerate(notes, 1):
        title = note_text.split("\n")[0][:50]
        note_result = close.create_note(lead_id, note_text)
        print(f"   ✓ Notiz {i}: {title}...")

    print(f"\n{'='*60}")
    print(f"  FERTIG! Lead-ID: {lead_id}")
    print(f"  Bitte in Close prüfen: https://app.close.com/lead/{lead_id}/")
    print(f"{'='*60}\n")

    # ── Optional: wieder löschen ──
    if delete_after:
        input("Enter drücken um den Test-Lead wieder zu löschen...")
        close.delete_lead(lead_id)
        print(f"   ✓ Lead {lead_id} gelöscht.\n")

    return lead_id


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Einzelnen Demo-Lead in Close erstellen")
    parser.add_argument(
        "--delete", action="store_true",
        help="Lead nach Prüfung wieder löschen",
    )
    args = parser.parse_args()

    if not CLOSE_API_KEY:
        log.error("close_api_key fehlt in .env!")
        exit(1)

    close = CloseClient(CLOSE_API_KEY)
    create_demo_lead(close, delete_after=args.delete)
