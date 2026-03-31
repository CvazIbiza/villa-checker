from flask import Flask, request, jsonify
import requests
from datetime import datetime

app = Flask(__name__)

villas = [
    {"name": "Villa Test 1", "ical": "https://www.calendarlabs.com/ical-calendar/ics/76/US_Holidays.ics"},
    {"name": "Villa Test 2", "ical": "https://www.calendarlabs.com/ical-calendar/ics/44/UK_Holidays.ics"},
]

def is_available(ical_url, start_date, end_date):
    try:
        data = requests.get(ical_url).text

        events = data.split("BEGIN:VEVENT")
        for event in events:
            if "DTSTART" in event and "DTEND" in event:
                start = event.split("DTSTART")[1].split("\n")[0].split(":")[1].strip()
                end = event.split("DTEND")[1].split("\n")[0].split(":")[1].strip()

                bs = datetime.strptime(start[:8], "%Y%m%d")
                be = datetime.strptime(end[:8], "%Y%m%d")

                if not (end_date <= bs or start_date >= be):
                    return False
        return True
    except:
        return False

@app.route("/check")
def check():
    start = datetime.strptime(request.args.get("start"), "%Y-%m-%d")
    end = datetime.strptime(request.args.get("end"), "%Y-%m-%d")

    results = []
    for v in villas:
        available = is_available(v["ical"], start, end)
        results.append({
            "villa": v["name"],
            "available": available
        })

    return jsonify(results)

app.run(host="0.0.0.0", port=10000)
