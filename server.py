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
        "bedrooms": 5,
        "ical": "https://platform.hostaway.com/ical/oa1HWBI56NzbAMgClOcBidsGrQp9hYOqPXug3QXTcq7ze0wmfj0iLlH4Et9ELA5D/listings/466923.ics"
    },
    {
        "name": "Villa Nivaria",
        "bedrooms": 4,
        "ical": "https://platform.hostaway.com/ical/oa1HWBI56NzbAMgClOcBidsGrQp9hYOqPXug3QXTcq7ze0wmfj0iLlH4Et9ELA5D/listings/466925.ics"
    },
    {
        "name": "Villa Bambu",
        "bedrooms": 6,
        "ical": "https://app.guesty.com/api/public/icalendar-dashboard-api/export/43f13b34-76e2-4f08-af18-06465a0fcf9f"
    },
    {
        "name": "Villa Luna",
        "bedrooms": 5,
        "ical": "https://app.guesty.com/api/public/icalendar-dashboard-api/export/cb893f3c-dbe0-4cc6-af08-03620d040239"
    },
    {
        "name": "Villa Oasis",
        "bedrooms": 4,
        "ical": "https://app.guesty.com/api/public/icalendar-dashboard-api/export/cf371f26-1981-4698-8106-3ddd39897464"
    },
    {
        "name": "Casa Juan",
        "bedrooms": 3,
        "ical": "https://www.airbnb.com/calendar/ical/883987254866482801.ics?t=6dcc4692128b4ee18a6894cc28a223bf&locale=es"
    },
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

            # Si las fechas se cruzan, no está disponible
            if not (end_date <= booking_start or start_date >= booking_end):
                return False

        return True

    except requests.exceptions.RequestException as e:
        print(f"Error fetching iCal {ical_url}: {e}")
        return None
    except Exception as e:
        print(f"Error parsing iCal {ical_url}: {e}")
        return None


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

    results = []
    errors = []

    for villa in villas:
        villa_bedrooms = villa.get("bedrooms", 0)

        # Filtra por habitaciones mínimas
        if min_bedrooms is not None and villa_bedrooms < min_bedrooms:
            continue

        available = is_available(villa["ical"], start, end)

        if available is None:
            errors.append({
                "villa": villa["name"],
                "bedrooms": villa_bedrooms,
                "status": "error",
                "message": "Calendar could not be checked"
            })
        elif available:
            results.append({
                "villa": villa["name"],
                "bedrooms": villa_bedrooms,
                "available": True,
                "status": "ok",
                "message": "Available"
            })

    return jsonify({
        "ok": True,
        "start": start_str,
        "end": end_str,
        "bedrooms_filter": min_bedrooms,
        "available_count": len(results),
        "message": "Available villas found" if results else "No villas available for the selected filters",
        "results": results,
        "errors": errors
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)
