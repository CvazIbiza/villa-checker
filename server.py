from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from datetime import datetime
import re
import unicodedata

app = Flask(__name__)
CORS(app)

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

ANY_VALUES = {"", "any", "all", "todos", "todas", "cualquiera", "none", "null"}

ZONE_ALIASES = {
    "ibiza": "Eivissa",
    "eivissa": "Eivissa",
    "sant josep": "Sant Josep",
    "san jose": "Sant Josep",
    "jesus": "Jesús",
    "santa eulalia": "Santa Eulalia",
    "santa eularia": "Santa Eulalia"
}


def normalize_text(value):
    if not value:
        return ""
    return unicodedata.normalize("NFD", str(value).strip().lower()).encode("ascii", "ignore").decode("utf-8")


def normalize_zone(value):
    v = normalize_text(value)
    if not v:
        return ""
    return ZONE_ALIASES.get(v, value.strip().title())


def extract_date(value):
    match = re.search(r"(\d{8})", value)
    if match:
        return datetime.strptime(match.group(1), "%Y%m%d")
    return None


def is_available_from_ical(url, start, end):
    try:
        response = requests.get(url, headers=HEADERS, timeout=20)
        response.raise_for_status()
        data = response.text
        events = data.split("BEGIN:VEVENT")

        for event in events:
            start_match = re.search(r"DTSTART.*:(.+)", event)
            end_match = re.search(r"DTEND.*:(.+)", event)

            if not start_match or not end_match:
                continue

            booking_start = extract_date(start_match.group(1))
            booking_end = extract_date(end_match.group(1))

            if booking_start and booking_end and start < booking_end and end > booking_start:
                return False

        return True
    except Exception as e:
        print(f"Error reading iCal {url}: {e}")
        return None


def zone_matches(villa_zone, selected_zone):
    if not selected_zone or normalize_text(selected_zone) in ANY_VALUES:
        return True

    villa_zone_normalized = normalize_text(normalize_zone(villa_zone))
    selected_zone_normalized = normalize_text(normalize_zone(selected_zone))

    return (
        selected_zone_normalized in villa_zone_normalized
        or villa_zone_normalized in selected_zone_normalized
    )


villas = [
    {
        "name": "Villa Bayview",
        "display_name": "Villa Bayview",
        "zone": "Sant Josep",
        "bedrooms": 4,
        "bathrooms": 4,
        "capacity": 8,
        "villa_type": 2,
        "ical": "https://platform.hostaway.com/ical/oa1HWBI56NzbAMgClOcBidsGrQp9hYOqPXug3QXTcq7ze0wmfj0iLlH4Et9ELA5D/listings/466923.ics"
    },
    {
        "name": "Villa Nivaria",
        "display_name": "Villa Nivaria",
        "zone": "Sant Josep",
        "bedrooms": 4,
        "bathrooms": 4,
        "capacity": 8,
        "villa_type": 2,
        "ical": "https://platform.hostaway.com/ical/oa1HWBI56NzbAMgClOcBidsGrQp9hYOqPXug3QXTcq7ze0wmfj0iLlH4Et9ELA5D/listings/466925.ics"
    },
    {
        "name": "Villa Bambu",
        "display_name": "Villa Bambu",
        "zone": "Eivissa",
        "bedrooms": 5,
        "bathrooms": 5,
        "capacity": 10,
        "villa_type": 2,
        "ical": "https://app.guesty.com/api/public/icalendar-dashboard-api/export/43f13b34-76e2-4f08-af18-06465a0fcf9f"
    },
    {
        "name": "Casa Juan",
        "display_name": "Casa Juan - Villa Estrella",
        "zone": "Santa Eulalia",
        "bedrooms": 4,
        "bathrooms": 4,
        "capacity": 8,
        "villa_type": 2,
        "ical": "https://www.airbnb.com/calendar/ical/883987254866482801.ics"
    }
]


@app.route("/")
def home():
    return jsonify({
        "ok": True,
        "message": "Villa availability API is running"
    })


@app.route("/filters")
def filters():
    zones = sorted({normalize_zone(v["zone"]) for v in villas if v.get("zone")})
    bedrooms = sorted({int(v["bedrooms"]) for v in villas if v.get("bedrooms") is not None})
    villa_types = sorted({int(v["villa_type"]) for v in villas if v.get("villa_type") is not None})

    return jsonify({
        "ok": True,
        "filters": {
            "zones": zones,
            "bedrooms": bedrooms,
            "villa_types": villa_types
        }
    })


@app.route("/calendar-links")
def calendar_links():
    return jsonify({
        "ok": True,
        "links": [
            {
                "display_name": "Ivilling",
                "calendar_url": "https://www.ivilling.es/",
                "zone": "External",
                "calendar_label": "Open site"
            },
            {
                "display_name": "Tom Benzon Bookings",
                "calendar_url": "https://www.tombenzon.com/bookings/",
                "zone": "External",
                "calendar_label": "Open site"
            },
            {
                "display_name": "NC Agent Kross Travel",
                "calendar_url": "https://nc-agent.kross.travel/en/villas",
                "zone": "External",
                "calendar_label": "Open site"
            },
            {
                "display_name": "Ibiza My Villa Agents",
                "calendar_url": "https://agents.ibizamyvilla.com/book/step1",
                "zone": "External",
                "calendar_label": "Open site"
            }
        ]
    })


@app.route("/check")
def check():
    start_str = request.args.get("start", "").strip()
    end_str = request.args.get("end", "").strip()
    zone = request.args.get("zone", "").strip()
    bedrooms_str = request.args.get("bedrooms", "").strip()
    villa_type_str = request.args.get("villa_type", "").strip()

    if not start_str or not end_str:
        return jsonify({
            "ok": False,
            "error": "Missing start or end date"
        }), 400

    try:
        start = datetime.strptime(start_str, "%Y-%m-%d")
        end = datetime.strptime(end_str, "%Y-%m-%d")
    except ValueError:
        return jsonify({
            "ok": False,
            "error": "Invalid date format. Use YYYY-MM-DD"
        }), 400

    if end <= start:
        return jsonify({
            "ok": False,
            "error": "Check-out must be later than check-in"
        }), 400

    bedrooms = None
    if bedrooms_str and normalize_text(bedrooms_str) not in ANY_VALUES:
        try:
            bedrooms = int(bedrooms_str)
        except ValueError:
            return jsonify({
                "ok": False,
                "error": "Invalid bedrooms value"
            }), 400

    villa_type = None
    if villa_type_str and normalize_text(villa_type_str) not in ANY_VALUES:
        try:
            villa_type = int(villa_type_str)
        except ValueError:
            return jsonify({
                "ok": False,
                "error": "Invalid villa_type value"
            }), 400

    results = []

    for villa in villas:
        if zone and not zone_matches(villa.get("zone", ""), zone):
            continue

        if bedrooms is not None and int(villa.get("bedrooms", 0)) < bedrooms:
            continue

        if villa_type is not None and int(villa.get("villa_type", 0)) != villa_type:
            continue

        available = is_available_from_ical(villa["ical"], start, end)

        if available is True:
            results.append({
                "villa": villa.get("name", ""),
                "display_name": villa.get("display_name", villa.get("name", "")),
                "zone": villa.get("zone", "-"),
                "bedrooms": villa.get("bedrooms", "-"),
                "bathrooms": villa.get("bathrooms", "-"),
                "capacity": villa.get("capacity", "-"),
                "villa_type": villa.get("villa_type", "-")
            })

    return jsonify({
        "ok": True,
        "message": f"{len(results)} available villa(s) found",
        "results": results
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
