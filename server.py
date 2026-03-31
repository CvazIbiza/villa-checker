from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from datetime import datetime
import re

app = Flask(__name__)
CORS(app)

villas = [
    {"name": "Villa Test 1", "ical": "https://www.calendarlabs.com/ical-calendar/ics/76/US_Holidays.ics"},
    {"name": "Villa Test 2", "ical": "https://www.calendarlabs.com/ical-calendar/ics/44/UK_Holidays.ics"},
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Villa Availability Checker)"
}

def extract_date(value):
    """
    Extrae fecha desde strings tipo:
    20260120
    20260120T000000Z
    ;VALUE=DATE:20260120
    """
    match = re.search(r"(\d{8})", value)
    if not match:
        return None
    return datetime.strptime(match.group(1), "%Y%m%d")

def is_available(ical_url, start_date, end_date):
    try:
        response = requests.get(ical_url, headers=HEADERS, timeout=8)
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

            # Si se cruzan fechas, no está disponible
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

    results = []

    for v in villas:
        available = is_available(v["ical"], start, end)

        if available is None:
            results.append({
                "villa": v["name"],
                "available": False,
                "status": "error",
                "message": "Calendar could not be checked"
            })
        else:
            results.append({
                "villa": v["name"],
                "available": available,
                "status": "ok",
                "message": "Available" if available else "Not Available"
            })

    return jsonify({
        "ok": True,
        "start": start_str,
        "end": end_str,
        "results": results
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)
