from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from datetime import datetime
import re
import unicodedata

app = Flask(__name__)
CORS(app)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Villa Availability Checker)"
}

ANY_VALUES = {"", "any", "all", "todos", "todas", "cualquiera", "none", "null"}

ZONE_ALIASES = {
    "eivissa": "Eivissa",
    "ibiza": "Eivissa",
    "ibiza town": "Eivissa",
    "ibiza ciudad": "Eivissa",
    "vila": "Eivissa",

    "sant josep": "Sant Josep",
    "san jose": "Sant Josep",
    "san josep": "Sant Josep",
    "sant jose": "Sant Josep",
    "sant josep de sa talaia": "Sant Josep",
    "san josep de sa talaia": "Sant Josep",

    "santa eulalia": "Santa Eulalia",
    "santa eularia": "Santa Eulalia",
    "santa eularia des riu": "Santa Eulalia",
    "santa eulalia del rio": "Santa Eulalia",

    "jesus": "Jesús",
    "jesús": "Jesús",

    "es canar": "Es Canar",
    "cala llonga": "Cala Llonga",
    "roca llisa": "Roca Llisa",
    "cap martinet": "Cap Martinet",
    "cala jondal": "Cala Jondal",
    "es cubells": "Es Cubells",

    "sin definir": "Sin definir"
}

NEARBY_ZONES = {
    "Eivissa": {"Cap Martinet", "Roca Llisa", "Talamanca", "Ibiza", "Ibiza Town", "Vila", "Jesús"},
    "Sant Josep": {"Es Cubells", "Cala Jondal", "San Jose", "Sant Josep"},
    "Santa Eulalia": {"Es Canar", "Cala Llonga", "Santa Eularia", "Santa Eulalia", "Jesús"},
    "Jesús": {"Eivissa", "Santa Eulalia", "Cap Martinet", "Roca Llisa", "Talamanca"},
    "Es Canar": {"Santa Eulalia"},
    "Cala Llonga": {"Santa Eulalia", "Roca Llisa"},
    "Roca Llisa": {"Eivissa", "Santa Eulalia", "Cala Llonga", "Jesús"},
    "Cap Martinet": {"Eivissa", "Talamanca", "Jesús"},
    "Cala Jondal": {"Sant Josep", "Es Cubells"},
    "Es Cubells": {"Sant Josep", "Cala Jondal"},
    "Sin definir": set()
}


def strip_accents(text):
    text = unicodedata.normalize("NFD", str(text))
    return "".join(ch for ch in text if unicodedata.category(ch) != "Mn")


def normalize_text(value):
    if value is None:
        return ""
    return strip_accents(str(value).strip().lower())


def parse_optional_filter(value):
    normalized = normalize_text(value)
    if normalized in ANY_VALUES:
        return None
    return str(value).strip()


def normalize_zone(value):
    normalized = normalize_text(value)

    if normalized in ANY_VALUES:
        return None

    if normalized in ZONE_ALIASES:
        return ZONE_ALIASES[normalized]

    for alias, canonical in ZONE_ALIASES.items():
        if normalized in alias or alias in normalized:
            return canonical

    raw = str(value).strip()
    return raw.title() if raw else "Sin definir"


def safe_int(value, default=None):
    try:
        if isinstance(value, str):
            value = value.replace("+", "").strip()
        return int(float(value))
    except (ValueError, TypeError):
        return default


def build_display_name(villa):
    original_name = str(villa.get("name", "")).strip()
    new_name = str(villa.get("new_name", "")).strip()

    if new_name and normalize_text(new_name) not in {"", "nombre nuevo", "pendiente"}:
        return f"{original_name} - {new_name}"
    return original_name


def get_villa_zone(villa):
    exact_zone = normalize_zone(villa.get("zone", ""))
    if exact_zone:
        return exact_zone

    approx_zone = normalize_zone(villa.get("approx_zone", ""))
    if approx_zone:
        return approx_zone

    return "Sin definir"


def zone_matches(filter_zone, villa_zone):
    if not filter_zone:
        return True

    if villa_zone == filter_zone:
        return True

    nearby = NEARBY_ZONES.get(filter_zone, set())
    if villa_zone in nearby:
        return True

    reverse_nearby = NEARBY_ZONES.get(villa_zone, set())
    if filter_zone in reverse_nearby:
        return True

    return False


def extract_date(value):
    if not value:
        return None

    match = re.search(r"(\d{8})", value)
    if not match:
        return None

    try:
        return datetime.strptime(match.group(1), "%Y%m%d")
    except ValueError:
        return None


def is_available_from_ical(ical_url, start_date, end_date):
    try:
        response = requests.get(ical_url, headers=HEADERS, timeout=20)
        response.raise_for_status()
        data = response.text

        if "BEGIN:VEVENT" not in data:
            return None, "No calendar events found"

        events = data.split("BEGIN:VEVENT")

        for event in events:
            start_match = re.search(r"DTSTART[^:]*:(.+)", event)
            end_match = re.search(r"DTEND[^:]*:(.+)", event)

            if not start_match or not end_match:
                continue

            booking_start = extract_date(start_match.group(1).strip())
            booking_end = extract_date(end_match.group(1).strip())

            if not booking_start or not booking_end:
                continue

            if start_date < booking_end and end_date > booking_start:
                return False, "Booked on selected dates"

        return True, "Available"

    except requests.exceptions.RequestException as e:
        print(f"Error fetching iCal {ical_url}: {e}")
        return None, "Calendar could not be fetched"
    except Exception as e:
        print(f"Error parsing iCal {ical_url}: {e}")
        return None, "Calendar could not be parsed"


villas = [
    {
        "name": "Villa Bayview",
        "new_name": "Villa Lucia",
        "zone": "Sant Josep",
        "approx_zone": "Sant Josep",
        "bedrooms": 4,
        "bathrooms": 4,
        "capacity": 8,
        "villa_type": "2",
        "license": "",
        "maps_url": "",
        "calendar_url": "https://platform.hostaway.com/ical/oa1HWBI56NzbAMgClOcBidsGrQp9hYOqPXug3QXTcq7ze0wmfj0iLlH4Et9ELA5D/listings/466923.ics",
        "calendar_label": "Hostaway iCal",
        "ical": "https://platform.hostaway.com/ical/oa1HWBI56NzbAMgClOcBidsGrQp9hYOqPXug3QXTcq7ze0wmfj0iLlH4Et9ELA5D/listings/466923.ics"
    },
    {
        "name": "Villa Nivaria",
        "new_name": "Villa Real",
        "zone": "Sant Josep",
        "approx_zone": "Sant Josep",
        "bedrooms": 4,
        "bathrooms": 4,
        "capacity": 8,
        "villa_type": "2",
        "license": "",
        "maps_url": "",
        "calendar_url": "https://platform.hostaway.com/ical/oa1HWBI56NzbAMgClOcBidsGrQp9hYOqPXug3QXTcq7ze0wmfj0iLlH4Et9ELA5D/listings/466925.ics",
        "calendar_label": "Hostaway iCal",
        "ical": "https://platform.hostaway.com/ical/oa1HWBI56NzbAMgClOcBidsGrQp9hYOqPXug3QXTcq7ze0wmfj0iLlH4Et9ELA5D/listings/466925.ics"
    },
    {
        "name": "Villa Bambu",
        "new_name": "Villa Carmela",
        "zone": "Eivissa",
        "approx_zone": "Eivissa",
        "bedrooms": 5,
        "bathrooms": 5,
        "capacity": 10,
        "villa_type": "2",
        "license": "",
        "maps_url": "",
        "calendar_url": "https://app.guesty.com/api/public/icalendar-dashboard-api/export/43f13b34-76e2-4f08-af18-06465a0fcf9f",
        "calendar_label": "Guesty iCal",
        "ical": "https://app.guesty.com/api/public/icalendar-dashboard-api/export/43f13b34-76e2-4f08-af18-06465a0fcf9f"
    },
    {
        "name": "Villa Luna",
        "new_name": "nombre nuevo",
        "zone": "",
        "approx_zone": "Eivissa",
        "bedrooms": 5,
        "bathrooms": 5,
        "capacity": 10,
        "villa_type": "",
        "license": "",
        "maps_url": "",
        "calendar_url": "https://app.guesty.com/api/public/icalendar-dashboard-api/export/cb893f3c-dbe0-4cc6-af08-03620d040239",
        "calendar_label": "Guesty iCal",
        "ical": "https://app.guesty.com/api/public/icalendar-dashboard-api/export/cb893f3c-dbe0-4cc6-af08-03620d040239"
    },
    {
        "name": "Villa Oasis",
        "new_name": "Villa Deluxe",
        "zone": "Eivissa",
        "approx_zone": "Eivissa",
        "bedrooms": 4,
        "bathrooms": 4,
        "capacity": 8,
        "villa_type": "2",
        "license": "",
        "maps_url": "",
        "calendar_url": "https://app.guesty.com/api/public/icalendar-dashboard-api/export/cf371f26-1981-4698-8106-3ddd39897464",
        "calendar_label": "Guesty iCal",
        "ical": "https://app.guesty.com/api/public/icalendar-dashboard-api/export/cf371f26-1981-4698-8106-3ddd39897464"
    },
    {
        "name": "Casa Juan",
        "new_name": "Villa Estrella",
        "zone": "Santa Eulalia",
        "approx_zone": "Santa Eulalia",
        "bedrooms": 4,
        "bathrooms": 4,
        "capacity": 8,
        "villa_type": "2",
        "license": "",
        "maps_url": "",
        "calendar_url": "https://www.airbnb.com/calendar/ical/883987254866482801.ics?t=6dcc4692128b4ee18a6894cc28a223bf&locale=es",
        "calendar_label": "Airbnb iCal",
        "ical": "https://www.airbnb.com/calendar/ical/883987254866482801.ics?t=6dcc4692128b4ee18a6894cc28a223bf&locale=es"
    },
    {
        "name": "Can Daniel Relax and Enjoy",
        "new_name": "Pendiente",
        "zone": "Sant Josep",
        "approx_zone": "Sant Josep",
        "bedrooms": 4,
        "bathrooms": 3,
        "capacity": 8,
        "villa_type": "1",
        "license": "ET0626E",
        "maps_url": "https://maps.app.goo.gl/Ej9fnXGnKPYBF5mE7",
        "calendar_url": "https://ical.avaibook.com/ical/ua_5390c3b2492dd2818eef8ad4d9fc6bd9-0e01938fc48a2cfb5f2217fbfb00722d-c559427c0f397839ef54fb1b60eeacec.ics",
        "calendar_label": "Avaibook iCal",
        "ical": "https://ical.avaibook.com/ical/ua_5390c3b2492dd2818eef8ad4d9fc6bd9-0e01938fc48a2cfb5f2217fbfb00722d-c559427c0f397839ef54fb1b60eeacec.ics"
    },
    {
        "name": "Coll des Cocons",
        "new_name": "Pendiente",
        "zone": "Jesús",
        "approx_zone": "Jesús",
        "bedrooms": 4,
        "bathrooms": 2.5,
        "capacity": 8,
        "villa_type": "1",
        "license": "ETV1914E",
        "maps_url": "https://maps.app.goo.gl/FR4ax54APkijvW1f8",
        "calendar_url": "https://ical.avaibook.com/ical/ua_4c18bf3d4f3f0603f6a6b86e536545c6-0e01938fc48a2cfb5f2217fbfb00722d-5cfca411a04d716c145792027fabbcee.ics",
        "calendar_label": "Avaibook iCal",
        "ical": "https://ical.avaibook.com/ical/ua_4c18bf3d4f3f0603f6a6b86e536545c6-0e01938fc48a2cfb5f2217fbfb00722d-5cfca411a04d716c145792027fabbcee.ics"
    },
    {
        "name": "Villa Julieta",
        "new_name": "Pendiente",
        "zone": "Jesús",
        "approx_zone": "Santa Eulalia",
        "bedrooms": 4,
        "bathrooms": 5,
        "capacity": 8,
        "villa_type": "1",
        "license": "ETV1221-E",
        "maps_url": "https://maps.app.goo.gl/LeAn6BvT1x2kepba9",
        "calendar_url": "https://ical.avaibook.com/ical/ua_ec28f887b70c8cc017286b8ea849f921-0e01938fc48a2cfb5f2217fbfb00722d-e887ee60949dfd22e00de7ed3222b526.ics",
        "calendar_label": "Avaibook iCal",
        "ical": "https://ical.avaibook.com/ical/ua_ec28f887b70c8cc017286b8ea849f921-0e01938fc48a2cfb5f2217fbfb00722d-e887ee60949dfd22e00de7ed3222b526.ics"
    },
    {
        "name": "Villa Romeo",
        "new_name": "Pendiente",
        "zone": "Jesús",
        "approx_zone": "Santa Eulalia",
        "bedrooms": 5,
        "bathrooms": 6,
        "capacity": 10,
        "villa_type": "1",
        "license": "ETV1222-E",
        "maps_url": "https://maps.app.goo.gl/56nBRdaYc8Gix8cdA",
        "calendar_url": "https://ical.avaibook.com/ical/ua_47a246622ab064ea8494f461852c26a3-0e01938fc48a2cfb5f2217fbfb00722d-c4cc24a7e51e03943b879f40171a7495.ics",
        "calendar_label": "Avaibook iCal",
        "ical": "https://ical.avaibook.com/ical/ua_47a246622ab064ea8494f461852c26a3-0e01938fc48a2cfb5f2217fbfb00722d-c4cc24a7e51e03943b879f40171a7495.ics"
    },
    {
        "name": "Can Emyla",
        "new_name": "Pendiente",
        "zone": "Jesús",
        "approx_zone": "Santa Eulalia",
        "bedrooms": 4,
        "bathrooms": 3,
        "capacity": 8,
        "villa_type": "1",
        "license": "ETV2487E",
        "maps_url": "https://maps.app.goo.gl/RFGQb76QcXich3u27",
        "calendar_url": "https://ical.avaibook.com/ical/ua_06f11b2f6d194953b7323b24d883bc10-0e01938fc48a2cfb5f2217fbfb00722d-77ddc50a60c37d3f55bf337d558b9182.ics",
        "calendar_label": "Avaibook iCal",
        "ical": "https://ical.avaibook.com/ical/ua_06f11b2f6d194953b7323b24d883bc10-0e01938fc48a2cfb5f2217fbfb00722d-77ddc50a60c37d3f55bf337d558b9182.ics"
    }
]


@app.route("/")
def home():
    return jsonify({
        "ok": True,
        "message": "Villa availability API is running"
    })


@app.route("/calendar-links")
def calendar_links():
    links = []

    for villa in villas:
        links.append({
            "villa": villa.get("name", ""),
            "display_name": build_display_name(villa),
            "calendar_label": villa.get("calendar_label", "Calendar"),
            "calendar_url": villa.get("calendar_url", ""),
            "zone": get_villa_zone(villa)
        })

    return jsonify({
        "ok": True,
        "links": links
    })


@app.route("/filters")
def filters():
    exact_zones = {get_villa_zone(villa) for villa in villas}

    extra_known_zones = {
        "Eivissa",
        "Sant Josep",
        "Santa Eulalia",
        "Jesús",
        "Es Canar",
        "Cala Llonga",
        "Roca Llisa",
        "Cap Martinet",
        "Cala Jondal",
        "Es Cubells"
    }

    zones = sorted(exact_zones.union(extra_known_zones))

    bedroom_values = sorted({
        safe_int(villa.get("bedrooms"), 0)
        for villa in villas
        if safe_int(villa.get("bedrooms"), 0) > 0
    })

    villa_types = sorted({
        str(villa.get("villa_type", "")).strip()
        for villa in villas
        if str(villa.get("villa_type", "")).strip() in {"1", "2"}
    })

    return jsonify({
        "ok": True,
        "filters": {
            "zones": zones,
            "bedrooms": bedroom_values,
            "villa_types": villa_types
        }
    })


@app.route("/check")
def check():
    start_str = request.args.get("start")
    end_str = request.args.get("end")
    bedrooms_str = parse_optional_filter(request.args.get("bedrooms"))
    zone_str = parse_optional_filter(request.args.get("zone"))
    villa_type_str = parse_optional_filter(request.args.get("villa_type"))

    if not start_str or not end_str:
        return jsonify({
            "ok": False,
            "error": "Missing start or end date. Use format YYYY-MM-DD"
        }), 400

    try:
        start = datetime.strptime(start_str, "%Y-%m-%d")
        end = datetime.strptime(end_str, "%Y-%m-%d")
    except ValueError:
        return jsonify({
            "ok": False,
            "error": "Invalid date format. Use YYYY-MM-DD"
        }), 400

    if start >= end:
        return jsonify({
            "ok": False,
            "error": "End date must be later than start date"
        }), 400

    min_bedrooms = None
    if bedrooms_str is not None:
        min_bedrooms = safe_int(bedrooms_str)
        if min_bedrooms is None or min_bedrooms <= 0:
            return jsonify({
                "ok": False,
                "error": "Bedrooms must be a valid number greater than 0"
            }), 400

    villa_type = None
    if villa_type_str is not None:
        villa_type = str(villa_type_str).strip()
        if villa_type not in {"1", "2"}:
            return jsonify({
                "ok": False,
                "error": "Villa type must be 1 or 2"
            }), 400

    zone_filter = normalize_zone(zone_str) if zone_str else None

    results = []
    errors = []

    for villa in villas:
        villa_zone = get_villa_zone(villa)
        villa_bedrooms = safe_int(villa.get("bedrooms"), 0)
        villa_type_value = str(villa.get("villa_type", "")).strip()
        display_name = build_display_name(villa)

        if min_bedrooms is not None and villa_bedrooms < min_bedrooms:
            continue

        if zone_filter is not None and not zone_matches(zone_filter, villa_zone):
            continue

        if villa_type is not None and villa_type_value != villa_type:
            continue

        available, source_message = is_available_from_ical(villa.get("ical", ""), start, end)

        villa_payload = {
            "villa": villa.get("name", ""),
            "display_name": display_name,
            "new_name": villa.get("new_name", ""),
            "zone": villa_zone,
            "bedrooms": villa_bedrooms,
            "bathrooms": villa.get("bathrooms", ""),
            "capacity": villa.get("capacity", ""),
            "license": villa.get("license", ""),
            "maps_url": villa.get("maps_url", ""),
            "calendar_url": villa.get("calendar_url", ""),
            "calendar_label": villa.get("calendar_label", "Calendar"),
            "villa_type": villa_type_value,
            "matched_by_nearby_zone": (
                zone_filter is not None
                and villa_zone != zone_filter
                and zone_matches(zone_filter, villa_zone)
            )
        }

        if available is None:
            errors.append({
                **villa_payload,
                "status": "error",
                "message": source_message or "Calendar could not be checked"
            })
        elif available:
            results.append({
                **villa_payload,
                "available": True,
                "status": "ok",
                "message": source_message or "Available"
            })

    return jsonify({
        "ok": True,
        "filters_applied": {
            "start": start_str,
            "end": end_str,
            "zone": zone_filter,
            "bedrooms": min_bedrooms,
            "villa_type": villa_type
        },
        "available_count": len(results),
        "message": "Available villas found" if results else "No villas available for the selected filters",
        "results": results,
        "errors": errors
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)
