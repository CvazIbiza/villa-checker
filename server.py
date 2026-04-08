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
    "jesus": "Jesús",
    "santa eulalia": "Santa Eulalia"
}

def normalize_text(v):
    if not v:
        return ""
    return unicodedata.normalize("NFD", str(v).lower()).encode("ascii", "ignore").decode("utf-8")

def normalize_zone(v):
    v = normalize_text(v)
    return ZONE_ALIASES.get(v, v.title() if v else "Sin definir")

def extract_date(value):
    match = re.search(r"(\d{8})", value)
    if match:
        return datetime.strptime(match.group(1), "%Y%m%d")
    return None

def is_available_from_ical(url, start, end):
    try:
        data = requests.get(url, headers=HEADERS).text
        events = data.split("BEGIN:VEVENT")

        for e in events:
            s = re.search(r"DTSTART.*:(.+)", e)
            e2 = re.search(r"DTEND.*:(.+)", e)

            if not s or not e2:
                continue

            bs = extract_date(s.group(1))
            be = extract_date(e2.group(1))

            if bs and be and start < be and end > bs:
                return False

        return True
    except:
        return None

# 🔥 VILLAS (ICAL ONLY)
villas = [
    {
        "name": "Villa Bayview",
        "zone": "Sant Josep",
        "bedrooms": 4,
        "ical": "https://platform.hostaway.com/ical/oa1HWBI56NzbAMgClOcBidsGrQp9hYOqPXug3QXTcq7ze0wmfj0iLlH4Et9ELA5D/listings/466923.ics"
    },
    {
        "name": "Villa Nivaria",
        "zone": "Sant Josep",
        "bedrooms": 4,
        "ical": "https://platform.hostaway.com/ical/oa1HWBI56NzbAMgClOcBidsGrQp9hYOqPXug3QXTcq7ze0wmfj0iLlH4Et9ELA5D/listings/466925.ics"
    },
    {
        "name": "Villa Bambu",
        "zone": "Eivissa",
        "bedrooms": 5,
        "ical": "https://app.guesty.com/api/public/icalendar-dashboard-api/export/43f13b34-76e2-4f08-af18-06465a0fcf9f"
    },
    {
        "name": "Casa Juan",
        "zone": "Santa Eulalia",
        "bedrooms": 4,
        "ical": "https://www.airbnb.com/calendar/ical/883987254866482801.ics"
    }
]

# 🔗 LINKS EXTERNOS
@app.route("/calendar-links")
def calendar_links():
    return jsonify({
        "ok": True,
        "links": [
            "https://agents.ibizamyvilla.com",
            "https://www.tombenzon.com/villas-in-ibiza"
        ]
    })

@app.route("/check")
def check():
    start = request.args.get("start")
    end = request.args.get("end")

    if not start or not end:
        return jsonify({"ok": False})

    start = datetime.strptime(start, "%Y-%m-%d")
    end = datetime.strptime(end, "%Y-%m-%d")

    results = []

    for v in villas:
        available = is_available_from_ical(v["ical"], start, end)

        if available:
            results.append({
                "name": v["name"],
                "zone": v["zone"],
                "bedrooms": v["bedrooms"]
            })

    return jsonify({
        "ok": True,
        "results": results
    })

if __name__ == "__main__":
    app.run()
