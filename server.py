from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from datetime import datetime
import re

app = Flask(__name__)
CORS(app)

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
        "zone": "Sant Josep,
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
        "zone": "",
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

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Villa Availability Checker)"
}


def extract_date(value):
    match = re.search(r"(\d{8})", value)
    if not match:
        return None
    return datetime.strptime(match.group(1), "%Y%m%d")


def is_available(ical_url, start_date, end_date):
    try:
        response = requests.get(ical_url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        data = response.text

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

            if not (end_date <= booking_start or start_date >= booking_end):
                return False

        return True

    except requests.exceptions.RequestException as e:
        print(f"Error fetching iCal {ical_url}: {e}")
        return None
    except Exception as e:
        print(f"Error parsing iCal {ical_url}: {e}")
        return None


def normalize_text(value):
    return str(value).strip().lower()


@app.route("/")
def home():
    return jsonify({
        "ok": True,
        "message": "Villa availability API is running"
    })


@app.route("/check")
def check():
    start_str = request.args.get("start")
    end_str = request.args.get("end")
    bedrooms_str = request.args.get("bedrooms")
    zone_str = request.args.get("zone")
    villa_type_str = request.args.get("villa_type")

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
    if bedrooms_str:
        try:
            min_bedrooms = int(bedrooms_str)
            if min_bedrooms <= 0:
                return jsonify({
                    "ok": False,
                    "error": "Bedrooms must be greater than 0"
                }), 400
        except ValueError:
            return jsonify({
                "ok": False,
                "error": "Bedrooms must be a valid number"
            }), 400

    villa_type = None
    if villa_type_str:
        try:
            villa_type = int(villa_type_str)
            if villa_type not in [1, 2]:
                return jsonify({
                    "ok": False,
                    "error": "Villa type must be 1 or 2"
                }), 400
        except ValueError:
            return jsonify({
                "ok": False,
                "error": "Villa type must be a valid number: 1 or 2"
            }), 400

    zone_filter = normalize_text(zone_str) if zone_str else None

    results = []
    errors = []

    for villa in villas:
        villa_bedrooms = villa.get("bedrooms", 0)
        villa_zone = normalize_text(villa.get("zone", ""))
        villa_type_value = villa.get("villa_type", "")
        display_name = f'{villa["name"]} - {villa.get("new_name", "nombre nuevo")}'

        if min_bedrooms is not None and villa_bedrooms < min_bedrooms:
            continue

        if zone_filter and villa_zone != zone_filter:
            continue

        if villa_type is not None:
            try:
                if int(villa_type_value) != villa_type:
                    continue
            except (ValueError, TypeError):
                continue

        available = is_available(villa["ical"], start, end)

        if available is None:
            errors.append({
                "villa": villa["name"],
                "display_name": display_name,
                "zone": villa.get("zone", ""),
                "bedrooms": villa_bedrooms,
                "villa_type": villa.get("villa_type", ""),
                "status": "error",
                "message": "Calendar could not be checked"
            })
        elif available:
            results.append({
                "villa": villa["name"],
                "display_name": display_name,
                "new_name": villa.get("new_name", "nombre nuevo"),
                "zone": villa.get("zone", ""),
                "bedrooms": villa_bedrooms,
                "villa_type": villa.get("villa_type", ""),
                "available": True,
                "status": "ok",
                "message": "Available"
            })

    return jsonify({
        "ok": True,
        "start": start_str,
        "end": end_str,
        "zone_filter": zone_str if zone_str else None,
        "bedrooms_filter": min_bedrooms,
        "villa_type_filter": villa_type,
        "available_count": len(results),
        "message": "Available villas found" if results else "No villas available for the selected filters",
        "results": results,
        "errors": errors
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)
