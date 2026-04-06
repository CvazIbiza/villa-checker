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

# =========================
# DATOS DE VILLAS
# =========================
villas = [
    {
        "name": "Villa Bayview",
        "new_name": "Villa Lucia",
        "zone": "Sant Josep",
        "bedrooms": 4,
        "villa_type": "2",
        "ical": "https://platform.hostaway.com/ical/oa1HWBI56NzbAMgClOcBidsGrQp9hYOqPXug3QXTcq7ze0wmfj0iLlH4Et9ELA5D/listings/466923.ics"
    },
    {
        "name": "Villa Nivaria",
        "new_name": "Villa Real",
        "zone": "Sant Josep",
        "bedrooms": 4,
        "villa_type": "2",
        "ical": "https://platform.hostaway.com/ical/oa1HWBI56NzbAMgClOcBidsGrQp9hYOqPXug3QXTcq7ze0wmfj0iLlH4Et9ELA5D/listings/466925.ics"
    },
    {
        "name": "Villa Bambu",
        "new_name": "Villa Carmela",
        "zone": "Eivissa",
        "bedrooms": 5,
        "villa_type": "2",
        "ical": "https://app.guesty.com/api/public/icalendar-dashboard-api/export/43f13b34-76e2-4f08-af18-06465a0fcf9f"
    },
    {
        "name": "Villa Luna",
        "new_name": "nombre nuevo",
        "zone": "Sin definir",
        "bedrooms": 5,
        "villa_type": "",
        "ical": "https://app.guesty.com/api/public/icalendar-dashboard-api/export/cb893f3c-dbe0-4cc6-af08-03620d040239"
    },
    {
        "name": "Villa Oasis",
        "new_name": "Villa Deluxe",
        "zone": "Eivissa",
        "bedrooms": 4,
        "villa_type": "2",
        "ical": "https://app.guesty.com/api/public/icalendar-dashboard-api/export/cf371f26-1981-4698-8106-3ddd39897464"
    },
    {
        "name": "Casa Juan",
        "new_name": "Villa Estrella",
        "zone": "Santa Eulalia",
        "bedrooms": 4,
        "villa_type": "2",
        "ical": "https://www.airbnb.com/calendar/ical/883987254866482801.ics?t=6dcc4692128b4ee18a6894cc28a223bf&locale=es"
    }
]

# =========================
# NORMALIZACIÓN / ALIAS DE ZONAS
# =========================
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
    "san josep de sa talaia": "Sant Josep",
    "sant josep de sa talaia": "Sant Josep",

    "santa eulalia": "Santa Eulalia",
    "santa eularia": "Santa Eulalia",
    "santa eularia des riu": "Santa Eulalia",
    "santa eulalia del rio": "Santa Eulalia",

    "sin definir": "Sin definir",
    "": "Sin definir",
}

ANY_VALUES = {"", "any", "all", "todos", "todas", "cualquiera", "no matter", "null", "none"}


def strip_accents(text):
    text = unicodedata.normalize("NFD", str(text))
    return "".join(ch for ch in text if unicodedata.category(ch) != "Mn")


def normalize_text(value):
    if value is None:
        return ""
    return strip_accents(str(value).strip().lower())


def normalize_zone(value):
    raw = normalize_text(value)
    if raw in ANY_VALUES:
        return None

    if raw in ZONE_ALIASES:
        return ZONE_ALIASES[raw]

    # coincidencia aproximada simple
    for alias, canonical in ZONE_ALIASES.items():
        if raw == alias or raw in alias or alias in raw:
            return canonical

    # si no coincide, devolvemos el texto con formato más limpio
    return str(value).strip().title() if str(value).strip() else "Sin definir"


def safe_int(value):
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def build_display_name(villa):
    original_name = villa.get("name", "").strip()
    new_name = villa.get("new_name", "").strip()

    if new_name and normalize_text(new_name) not in {"nombre nuevo", ""}:
        return f"{original_name} - {new_name}"
    return original_name


def extract_date(value):
    if not value:
        return None

    # Busca YYYYMMDD dentro del texto, incluso si vienen horas o TZ
    match = re.search(r"(\d{8})", value)
    if not match:
        return None

    try:
        return datetime.strptime(match.group(1), "%Y%m%d")
    except ValueError:
        return None


def is_available(ical_url, start_date, end_date):
    try:
        response = requests.get(ical_url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        data = response.text

        if "BEGIN:VEVENT" not in data:
            return None

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

            # Solape: si la reserva del calendario toca el rango solicitado, no está disponible
            if start_date < booking_end and end_date > booking_start:
                return False

        return True

    except requests.exceptions.RequestException as e:
        print(f"Error fetching iCal {ical_url}: {e}")
        return None
    except Exception as e:
        print(f"Error parsing iCal {ical_url}: {e}")
        return None


def parse_filter_value(value):
    normalized = normalize_text(value)
    if normalized in ANY_VALUES:
        return None
    return str(value).strip()


@app.route("/")
def home():
    return jsonify({
        "ok": True,
        "message": "Villa availability API is running"
    })


@app.route("/filters")
def filters():
    zones = sorted({
        normalize_zone(villa.get("zone", "Sin definir")) or "Sin definir"
        for villa in villas
    })

    bedroom_values = sorted({
        villa.get("bedrooms", 0)
        for villa in villas
        if isinstance(villa.get("bedrooms"), int) and villa.get("bedrooms", 0) > 0
    })

    villa_types = sorted({
        str(villa.get("villa_type")).strip()
        for villa in villas
        if str(villa.get("villa_type")).strip() in {"1", "2"}
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
    bedrooms_str = parse_filter_value(request.args.get("bedrooms"))
    zone_str = parse_filter_value(request.args.get("zone"))
    villa_type_str = parse_filter_value(request.args.get("villa_type"))

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
        villa_zone = normalize_zone(villa.get("zone", "Sin definir")) or "Sin definir"
        villa_bedrooms = safe_int(villa.get("bedrooms")) or 0
        villa_type_value = str(villa.get("villa_type", "")).strip()
        display_name = build_display_name(villa)

        # filtro bedrooms: muestra esa cantidad o más
        if min_bedrooms is not None and villa_bedrooms < min_bedrooms:
            continue

        # filtro zona
        if zone_filter is not None and villa_zone != zone_filter:
            continue

        # filtro tipo
        if villa_type is not None and villa_type_value != villa_type:
            continue

        available = is_available(villa["ical"], start, end)

        villa_payload = {
            "villa": villa["name"],
            "display_name": display_name,
            "new_name": villa.get("new_name", ""),
            "zone": villa_zone,
            "bedrooms": villa_bedrooms,
            "villa_type": villa_type_value,
        }

        if available is None:
            errors.append({
                **villa_payload,
                "status": "error",
                "message": "Calendar could not be checked"
            })
        elif available:
            results.append({
                **villa_payload,
                "available": True,
                "status": "ok",
                "message": "Available"
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
