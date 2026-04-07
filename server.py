from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from datetime import datetime, date
import re
import unicodedata
import calendar
from html.parser import HTMLParser
from urllib.parse import urlparse, parse_qs

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

MONTHS = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,

    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12
}


# =========================================================
# BASIC HELPERS
# =========================================================
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


def month_name_to_number(text):
    normalized = normalize_text(text)
    return MONTHS.get(normalized)


def parse_gid_from_url(url):
    try:
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        gid_list = qs.get("gid")
        if gid_list:
            return gid_list[0]
        if "#gid=" in url:
            return url.split("#gid=")[-1]
    except Exception:
        pass
    return None


def normalize_google_sheet_url(url):
    if not url:
        return url

    gid = parse_gid_from_url(url)
    base = url.split("#")[0]

    if "/edit" in base:
        base = base.split("/edit")[0]

    if gid:
        return f"{base}/htmlview?gid={gid}"
    return f"{base}/htmlview"


def daterange(start_date, end_date):
    current = start_date
    while current < end_date:
        yield current
        current = current.replace(day=current.day) + (datetime.combine(current, datetime.min.time()) - datetime.combine(current, datetime.min.time()))
        # overwritten below in a safe way


def day_range(start_date, end_date):
    current = start_date
    while current < end_date:
        yield current
        current = date.fromordinal(current.toordinal() + 1)


# =========================================================
# HTML PARSERS
# =========================================================
class GoogleSheetHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_style = False
        self.style_chunks = []

        self.tables = []
        self.current_table = None
        self.current_row = None
        self.current_cell = None

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)

        if tag == "style":
            self.in_style = True
            return

        if tag == "table":
            self.current_table = []
            return

        if tag == "tr" and self.current_table is not None:
            self.current_row = []
            return

        if tag in ("td", "th") and self.current_row is not None:
            self.current_cell = {
                "text": "",
                "attrs": attrs_dict
            }
            return

        if tag == "br" and self.current_cell is not None:
            self.current_cell["text"] += "\n"

    def handle_data(self, data):
        if self.in_style:
            self.style_chunks.append(data)
        elif self.current_cell is not None:
            self.current_cell["text"] += data

    def handle_endtag(self, tag):
        if tag == "style":
            self.in_style = False
            return

        if tag in ("td", "th") and self.current_row is not None and self.current_cell is not None:
            self.current_cell["text"] = self.current_cell["text"].strip()
            self.current_row.append(self.current_cell)
            self.current_cell = None
            return

        if tag == "tr" and self.current_table is not None and self.current_row is not None:
            self.current_table.append(self.current_row)
            self.current_row = None
            return

        if tag == "table" and self.current_table is not None:
            self.tables.append(self.current_table)
            self.current_table = None
            return

    @property
    def styles_text(self):
        return "\n".join(self.style_chunks)


def fetch_sheet_parser(sheet_url):
    url = normalize_google_sheet_url(sheet_url)
    response = requests.get(url, headers=HEADERS, timeout=25)
    response.raise_for_status()

    parser = GoogleSheetHTMLParser()
    parser.feed(response.text)
    return parser


def parse_css_class_colors(styles_text):
    class_colors = {}

    # .s0 {background-color:#00ff00;}
    for match in re.finditer(r"\.([A-Za-z0-9_-]+)\s*\{([^}]*)\}", styles_text, re.DOTALL):
        class_name = match.group(1)
        css_body = match.group(2)

        bg_match = re.search(r"background-color\s*:\s*([^;]+)", css_body, re.IGNORECASE)
        if bg_match:
            class_colors[class_name] = bg_match.group(1).strip()

    return class_colors


def extract_background_from_cell(cell, class_colors):
    attrs = cell.get("attrs", {})
    style = attrs.get("style", "") or ""
    class_attr = attrs.get("class", "") or ""

    style_match = re.search(r"background-color\s*:\s*([^;]+)", style, re.IGNORECASE)
    if style_match:
        return style_match.group(1).strip()

    classes = []
    if isinstance(class_attr, str):
        classes = class_attr.split()

    for cls in classes:
        if cls in class_colors:
            return class_colors[cls]

    bgcolor = attrs.get("bgcolor")
    if bgcolor:
        return bgcolor.strip()

    return ""


def parse_color_to_rgb(color_value):
    if not color_value:
        return None

    color_value = color_value.strip().lower()

    named = {
        "green": (0, 128, 0),
        "yellow": (255, 255, 0),
        "orange": (255, 165, 0),
        "red": (255, 0, 0),
        "white": (255, 255, 255),
        "black": (0, 0, 0)
    }
    if color_value in named:
        return named[color_value]

    hex_match = re.match(r"#([0-9a-f]{3}|[0-9a-f]{6})$", color_value)
    if hex_match:
        h = hex_match.group(1)
        if len(h) == 3:
            h = "".join(ch * 2 for ch in h)
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

    rgb_match = re.match(r"rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)", color_value)
    if rgb_match:
        return tuple(int(rgb_match.group(i)) for i in range(1, 4))

    return None


def color_to_status(color_value):
    rgb = parse_color_to_rgb(color_value)
    if not rgb:
        return None

    r, g, b = rgb

    # green = available
    if g >= 150 and r <= 180 and b <= 180:
        return "available"

    # yellow = on hold
    if r >= 180 and g >= 180 and b <= 140:
        return "on_hold"

    # orange/red = booked
    if r >= 170 and g <= 190:
        return "booked"

    return None


def cell_status(cell, class_colors):
    bg = extract_background_from_cell(cell, class_colors)
    status = color_to_status(bg)
    if status:
        return status

    txt = normalize_text(cell.get("text", ""))

    if "available" in txt:
        return "available"
    if "booked" in txt or "rented" in txt or "payment received" in txt:
        return "booked"
    if "on hold" in txt or "pending" in txt:
        return "on_hold"

    return None


def detect_year_from_tables(tables):
    for table in tables:
        for row in table:
            for cell in row:
                text = cell.get("text", "")
                match = re.search(r"\b(20\d{2})\b", text)
                if match:
                    return int(match.group(1))
    return datetime.now().year


def is_numeric_day(text):
    txt = str(text).strip()
    return re.fullmatch(r"\d{1,2}", txt) is not None


# =========================================================
# DOC PARSERS
# =========================================================
def parse_timeline_sheet_dates(sheet_url):
    parser = fetch_sheet_parser(sheet_url)
    tables = parser.tables
    class_colors = parse_css_class_colors(parser.styles_text)
    year = detect_year_from_tables(tables)

    parsed_dates = {}

    for table in tables:
        for row in table:
            if not row:
                continue

            month_num = None
            month_index = None

            for idx, cell in enumerate(row):
                month_num = month_name_to_number(cell.get("text", ""))
                if month_num:
                    month_index = idx
                    break

            if not month_num:
                continue

            for cell in row[month_index + 1:]:
                text = cell.get("text", "").strip()
                if not is_numeric_day(text):
                    continue

                status = cell_status(cell, class_colors)
                if not status:
                    continue

                day_num = int(text)
                try:
                    parsed_dates[date(year, month_num, day_num)] = status
                except ValueError:
                    continue

    return parsed_dates


def parse_monthly_sheet_dates(sheet_url):
    parser = fetch_sheet_parser(sheet_url)
    tables = parser.tables
    class_colors = parse_css_class_colors(parser.styles_text)
    year = detect_year_from_tables(tables)

    parsed_dates = {}
    cal = calendar.Calendar(firstweekday=6)  # Sunday first

    for table in tables:
        current_month = None
        week_rows = []
        collecting = False

        for row in table:
            row_texts = [normalize_text(c.get("text", "")) for c in row]
            joined = " ".join(row_texts)

            found_month = None
            for text in row_texts:
                month_num = month_name_to_number(text)
                if month_num:
                    found_month = month_num
                    break

            if found_month:
                if current_month and week_rows:
                    month_matrix = cal.monthdayscalendar(year, current_month)
                    for week_index, week_row in enumerate(week_rows):
                        if week_index >= len(month_matrix):
                            break

                        expected_week = month_matrix[week_index]
                        numeric_cells = []
                        for cell in week_row:
                            if is_numeric_day(cell.get("text", "").strip()):
                                numeric_cells.append(cell)

                        if len(numeric_cells) < 7:
                            continue

                        for col in range(7):
                            expected_day = expected_week[col]
                            cell = numeric_cells[col]
                            text = cell.get("text", "").strip()

                            if not is_numeric_day(text):
                                continue

                            shown_day = int(text)
                            if expected_day == 0 or shown_day != expected_day:
                                continue

                            status = cell_status(cell, class_colors)
                            if not status:
                                continue

                            try:
                                parsed_dates[date(year, current_month, shown_day)] = status
                            except ValueError:
                                pass

                current_month = found_month
                week_rows = []
                collecting = False
                continue

            if not current_month:
                continue

            # weekday header
            weekday_tokens = {"sun", "mon", "tue", "wed", "thu", "fri", "sat"}
            if any(token in weekday_tokens for token in row_texts):
                collecting = True
                continue

            if collecting:
                numeric_count = sum(1 for c in row if is_numeric_day(c.get("text", "").strip()))
                if numeric_count >= 7:
                    week_rows.append(row)

        # flush last month in this table
        if current_month and week_rows:
            month_matrix = cal.monthdayscalendar(year, current_month)
            for week_index, week_row in enumerate(week_rows):
                if week_index >= len(month_matrix):
                    break

                expected_week = month_matrix[week_index]
                numeric_cells = []
                for cell in week_row:
                    if is_numeric_day(cell.get("text", "").strip()):
                        numeric_cells.append(cell)

                if len(numeric_cells) < 7:
                    continue

                for col in range(7):
                    expected_day = expected_week[col]
                    cell = numeric_cells[col]
                    text = cell.get("text", "").strip()

                    if not is_numeric_day(text):
                        continue

                    shown_day = int(text)
                    if expected_day == 0 or shown_day != expected_day:
                        continue

                    status = cell_status(cell, class_colors)
                    if not status:
                        continue

                    try:
                        parsed_dates[date(year, current_month, shown_day)] = status
                    except ValueError:
                        pass

    return parsed_dates


def is_available_from_sheet_timeline(sheet_url, start_date, end_date):
    try:
        parsed_dates = parse_timeline_sheet_dates(sheet_url)
        if not parsed_dates:
            return None, "Timeline sheet could not be parsed"

        for d in day_range(start_date.date(), end_date.date()):
            status = parsed_dates.get(d)

            if status in {"booked", "on_hold"}:
                return False, f"Unavailable in doc ({status})"

        # if dates exist and none blocked, assume available
        date_hits = sum(1 for d in day_range(start_date.date(), end_date.date()) if d in parsed_dates)
        if date_hits > 0:
            return True, "Available from doc"

        return None, "Requested dates not found in timeline doc"

    except requests.exceptions.RequestException as e:
        print(f"Error fetching timeline sheet {sheet_url}: {e}")
        return None, "Timeline sheet could not be fetched"
    except Exception as e:
        print(f"Error parsing timeline sheet {sheet_url}: {e}")
        return None, "Timeline sheet could not be parsed"


def is_available_from_sheet_monthly(sheet_url, start_date, end_date):
    try:
        parsed_dates = parse_monthly_sheet_dates(sheet_url)
        if not parsed_dates:
            return None, "Monthly sheet could not be parsed"

        for d in day_range(start_date.date(), end_date.date()):
            status = parsed_dates.get(d)

            if status in {"booked", "on_hold"}:
                return False, f"Unavailable in doc ({status})"

        date_hits = sum(1 for d in day_range(start_date.date(), end_date.date()) if d in parsed_dates)
        if date_hits > 0:
            return True, "Available from doc"

        return None, "Requested dates not found in monthly doc"

    except requests.exceptions.RequestException as e:
        print(f"Error fetching monthly sheet {sheet_url}: {e}")
        return None, "Monthly sheet could not be fetched"
    except Exception as e:
        print(f"Error parsing monthly sheet {sheet_url}: {e}")
        return None, "Monthly sheet could not be parsed"


# =========================================================
# ICAL
# =========================================================
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


def check_villa_availability(villa, start_date, end_date):
    source_type = str(villa.get("source_type", "ical")).strip()

    if source_type == "ical":
        return is_available_from_ical(villa.get("ical", ""), start_date, end_date)

    if source_type == "sheet_timeline":
        return is_available_from_sheet_timeline(villa.get("sheet_url", ""), start_date, end_date)

    if source_type == "sheet_monthly":
        return is_available_from_sheet_monthly(villa.get("sheet_url", ""), start_date, end_date)

    return None, "Unknown calendar source"


# =========================================================
# VILLAS
# =========================================================
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
        "source_type": "ical",
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
        "source_type": "ical",
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
        "source_type": "ical",
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
        "source_type": "ical",
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
        "source_type": "ical",
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
        "source_type": "ical",
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
        "source_type": "ical",
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
        "source_type": "ical",
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
        "source_type": "ical",
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
        "source_type": "ical",
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
        "source_type": "ical",
        "ical": "https://ical.avaibook.com/ical/ua_06f11b2f6d194953b7323b24d883bc10-0e01938fc48a2cfb5f2217fbfb00722d-77ddc50a60c37d3f55bf337d558b9182.ics"
    },

    # DOC TYPE 1: timeline / bands
    {
        "name": "Talamanca Heights",
        "new_name": "Pendiente",
        "zone": "Jesús",
        "approx_zone": "Eivissa",
        "bedrooms": 4,
        "bathrooms": 0,
        "capacity": 8,
        "villa_type": "1",
        "license": "",
        "maps_url": "",
        "source_type": "sheet_timeline",
        "sheet_url": "https://docs.google.com/spreadsheets/d/1WcvBrQHgE_L8DuM9hRzEW9cid3ghpHGGYoI1BsTHQYc/edit?gid=2024190730#gid=2024190730"
    }

    # Si luego me pasas el nombre exacto de la villa de La Reposada o del otro doc,
    # te la meto como sheet_monthly con su sheet_url.
]


@app.route("/")
def home():
    return jsonify({
        "ok": True,
        "message": "Villa availability API is running"
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

        available, source_message = check_villa_availability(villa, start, end)

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
            "villa_type": villa_type_value,
            "source_type": villa.get("source_type", "ical"),
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
