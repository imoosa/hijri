from datetime import date, datetime, timedelta

from flask import Flask, request, jsonify, render_template, session, redirect, url_for, flash
from flask_cors import CORS

from . import hijri_calendar as hc
from . import hebrew_calendar as heb
from . import parsi_calendar as pc
from . import hindu_calendar as hindu
from . import prayer_times as pt
from . import prayer_times_accurate as pt
from . import qibla as qb
from . import interfaith_calendar as ic
from . import tz_lookup as tzl
from . import personal_events as pe
from . import sunni_calendar as sc
from . import shia_calendar as shc
from .database import (
    get_session, init_db, seed_if_empty, seed_missing_sources, HijriEvent,
    InterfaithEvent, PersonalEvent, Note, get_or_create_note, refresh_interfaith_events,
)

import calendar as _pycal
from html.parser import HTMLParser
from html import escape as _escape

# Tags the sticky-note toolbar can actually produce (bold + bullet lists,
# plus the div/br/p wrapper tags contenteditable inserts on its own).
# Anything else -- script, style, img, on*-handler-bearing tags, all
# attributes on every tag -- gets stripped, not escaped-and-kept.
_NOTE_ALLOWED_TAGS = {"b", "strong", "i", "em", "u", "ul", "ol", "li", "br", "div", "p", "span"}
_NOTE_MAX_CHARS = 20000  # hard cap so a paste storm can't blow up the row


class _NoteSanitizer(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []

    def handle_starttag(self, tag, attrs):
        if tag in _NOTE_ALLOWED_TAGS:
            self.out.append(f"<{tag}>")

    def handle_startendtag(self, tag, attrs):
        if tag in _NOTE_ALLOWED_TAGS:
            self.out.append(f"<{tag}/>")

    def handle_endtag(self, tag):
        if tag in _NOTE_ALLOWED_TAGS:
            self.out.append(f"</{tag}>")

    def handle_data(self, data):
        self.out.append(_escape(data))


def sanitize_note_html(raw: str) -> str:
    """Whitelist-based cleanup for whatever the sticky-note contenteditable
    box sent back. [likely-sufficient, not audited] -- a stripped-tag
    allowlist with every attribute dropped closes the obvious script/
    onerror/href-javascript: holes, but this hasn't been pen-tested. Since
    this app has no login and the note is shared app-wide, the realistic
    risk is "whoever can already reach this Flask instance", not a
    stranger on the internet -- treat that as a real caveat, not a
    guarantee, if this ever gets deployed somewhere less trusted."""
    if not raw:
        return ""
    parser = _NoteSanitizer()
    parser.feed(raw[:_NOTE_MAX_CHARS])
    parser.close()
    return "".join(parser.out)

DEFAULT_LOCATION = {"name": "Mumbai, Maharashtra", "lat": 19.076, "lng": 72.877, "tz_offset": 5.5}
ALL_TRADITIONS = set(ic.TRADITIONS.keys())  # {'christian','french','jewish','hindu','parsi'}

# Which calendar the main /calendar grid is currently paging through. Every
# entry needs: grid(year, month) -> [(gregorian_date, ordinal, native_label_input), ...],
# month_name(year, month) -> str, native_of(gregorian_date) -> (year, month, day),
# next/prev(year, month) -> (year, month), and native_label(native_label_input) -> str
# (for display -- e.g. Arabic-Indic numerals for Hijri, plain digits elsewhere).
#
# `ordinal` is a plain sequential integer used as the day's URL/query key and
# for "is this day selected" comparisons -- it must always be a bare int that
# survives a round trip through a querystring. `native_label_input` is
# whatever native_label() itself needs to produce the on-screen label; for
# most calendars that's the same int as `ordinal`, but for Hindu it's a
# (tithi, paksha) tuple, since a lunar month has no native sequential day
# number and the tithi is not a stable/reversible key on its own.


def _grid_hijri(year, month):
    return [(date.fromisoformat(d["gregorian"]), d["hijri_day"], d["hijri_day"])
            for d in hc.month_grid(year, month)]

def _grid_sunni(year, month):
    return [(date.fromisoformat(d["gregorian"]), d["hijri_day"], d["hijri_day"])
            for d in sc.sunni_month_grid(year, month)]

def _grid_shia(year, month):
    return [(date.fromisoformat(d["gregorian"]), d["hijri_day"], d["hijri_day"])
            for d in shc.shia_month_grid(year, month)]

def _grid_gregorian(year, month):
    n = _pycal.monthrange(year, month)[1]
    return [(date(year, month, d), d, d) for d in range(1, n + 1)]


def _grid_hebrew(year, month):
    return [(date.fromisoformat(d["gregorian"]), d["day"], d["day"])
            for d in heb.month_grid(year, month)]


def _grid_parsi(year, month):
    return [(date.fromisoformat(d["gregorian"]), d["day"], d["day"])
            for d in pc.month_grid(year, month)]


def _grid_hindu(year, month):
    # ordinal (int, URL-safe) is separate from the (tithi, paksha) tuple that
    # native_label() needs to render the on-screen "S5"/"K12"-style label.
    return [(date.fromisoformat(d["gregorian"]), d["ordinal"], (d["tithi"], d["paksha"]))
            for d in hindu.month_grid(year, month)]


CALENDARS = {
    "hijri": {
        "label": "Bohra (Fatimid)",
        "grid": _grid_hijri,
        "month_name": lambda y, m: hc.hijri_month_name(m),
        "native_of": lambda g: hc.gregorian_to_hijri(g),
        "next": lambda y, m: (y, m + 1) if m < 12 else (y + 1, 1),
        "prev": lambda y, m: (y, m - 1) if m > 1 else (y - 1, 12),
        "native_label": hc.to_arabic_indic_numerals,
        "is_islamic": True,
        "tradition": "bohra",
    },
    "sunni": {
        "label": "Sunni (Umm al-Qura)",
        "grid": _grid_sunni,
        "month_name": lambda y, m: sc.sunni_month_name(m),
        "native_of": lambda g: sc.sunni_gregorian_to_hijri(g),
        "next": lambda y, m: (y, m + 1) if m < 12 else (y + 1, 1),
        "prev": lambda y, m: (y, m - 1) if m > 1 else (y - 1, 12),
        "native_label": hc.to_arabic_indic_numerals,
        "is_islamic": True,
        "tradition": "sunni",
    },
    "shia": {
        "label": "Shia (Jafari)",
        "grid": _grid_shia,
        "month_name": lambda y, m: shc.shia_month_name(m),
        "native_of": lambda g: shc.shia_gregorian_to_hijri(g),
        "next": lambda y, m: (y, m + 1) if m < 12 else (y + 1, 1),
        "prev": lambda y, m: (y, m - 1) if m > 1 else (y - 1, 12),
        "native_label": hc.to_arabic_indic_numerals,
        "is_islamic": True,
        "tradition": "shia",
    },
    "gregorian": {
        "label": "Gregorian",
        "grid": _grid_gregorian,
        "month_name": lambda y, m: date(y, m, 1).strftime("%B"),
        "native_of": lambda g: (g.year, g.month, g.day),
        "next": lambda y, m: (y, m + 1) if m < 12 else (y + 1, 1),
        "prev": lambda y, m: (y, m - 1) if m > 1 else (y - 1, 12),
        "native_label": str,
        "is_islamic": False,
        "tradition": None,
    },
    "hebrew": {
        "label": "Hebrew",
        "grid": _grid_hebrew,
        "month_name": lambda y, m: heb.month_name(m),
        "native_of": lambda g: heb.gregorian_to_hebrew(g),
        "next": heb.next_month,
        "prev": heb.prev_month,
        "native_label": str,
        "is_islamic": False,
        "tradition": None,
    },
    "parsi": {
        "label": "Parsi (Shahenshahi)",
        "grid": _grid_parsi,
        "month_name": lambda y, m: pc.month_name(m),
        "native_of": lambda g: pc.gregorian_to_parsi(g),
        "next": pc.next_month,
        "prev": pc.prev_month,
        "native_label": str,
        "is_islamic": False,
        "tradition": None,
    },
    "hindu": {
        "label": "Hindu (lunar)",
        "grid": _grid_hindu,
        "month_name": hindu.month_name,
        "native_of": hindu.gregorian_to_hindu,
        "next": hindu.next_month,
        "prev": hindu.prev_month,
        "native_label": hindu.native_label,
        "is_islamic": False,
        "tradition": None,
    },
}


def create_app():
    app = Flask(__name__)
    app.secret_key = "dev-secret-change-this-before-any-real-deployment"
    CORS(app)

    init_db()
    seed_if_empty()
    seed_missing_sources()
    # Rolling window so the calendar always has interfaith dates a couple
    # years out. Regenerates on every restart -- cheap (a few hundred rows).
    this_year = date.today().year
    refresh_interfaith_events(this_year - 1, this_year + 3)

    # ---------- sidebar sticky note (shown on every page) ----------
    @app.context_processor
    def inject_sidebar_note():
        """Runs before every render_template() call, so base.html can
        always show the note without each view function remembering to
        fetch it. content is already sanitized at save time (see
        sanitize_note_html above), so it's safe to render with |safe."""
        db = get_session()
        try:
            note = get_or_create_note(db)
            content = note.content
        finally:
            db.close()
        return dict(sidebar_note_content=content)

    @app.post("/notes/save")
    def save_note():
        """AJAX target for the sticky note -- called on a debounce timer and
        on blur, not on page submit, so typing doesn't reload the page."""
        clean = sanitize_note_html(request.form.get("content", ""))
        db = get_session()
        try:
            note = get_or_create_note(db)
            note.content = clean
            db.commit()
        finally:
            db.close()
        return jsonify({"status": "saved"})

    @app.get("/api/alerts/today")
    def api_alerts_today():
        """What the sidebar's client-side reminder script should ring for
        today: azaan times at the user's saved (or default) location,
        personal events (birthdays/anniversaries) landing today, and any
        visible interfaith tradition's holiday/event landing today. Reuses
        the exact same helpers the calendar page itself uses for personal/
        interfaith lookups, rather than a second copy of that logic --
        see get_personal_by_date / get_interfaith_by_date below."""
        today = date.today()
        prefs = get_user_prefs()
        traditions = get_visible_traditions(prefs)
        loc = current_location()
        prayer = pt.calculate(loc["lat"], loc["lng"], today, loc["tz_offset"])
        personal_today = get_personal_by_date(today, today).get(today, [])
        interfaith_today = get_interfaith_by_date(today, today, traditions).get(today, [])
        return jsonify({
            "date": today.isoformat(),
            "prayer_times": prayer,
            "personal_events": personal_today,
            "interfaith_events": interfaith_today,
        })

    # ---------- shared helpers ----------
    DEFAULT_PREFS = {
        "default_calendar": "hijri",
        "secondary_calendar": "",
        "show_bohra": True,
        "show_sunni": True,
        "show_shia": True,
        "show_christian": True,
        "show_jewish": True,
        "show_hindu": True,
        "show_parsi": True,
        "show_french": True,
        "show_personal": True,
    }

    def get_user_prefs():
        """Get user preferences from session, with defaults."""
        prefs = session.get("preferences", {})
        result = DEFAULT_PREFS.copy()
        result.update(prefs)
        return result

    def get_visible_traditions(prefs):
        """Return set of traditions the user wants to see."""
        visible = set()
        mapping = {
            "show_bohra": "bohra",
            "show_sunni": "sunni",
            "show_shia": "shia",
            "show_christian": "christian",
            "show_jewish": "jewish",
            "show_hindu": "hindu",
            "show_parsi": "parsi",
            "show_french": "french",
        }
        for pref_key, trad_key in mapping.items():
            if prefs.get(pref_key, True):
                visible.add(trad_key)
        return visible

    def current_location():
        return session.get("location", DEFAULT_LOCATION)

    def location_is_default():
        return "location" not in session

    def selected_traditions():
        # Checkboxes with name="show" submit as repeated ?show=a&show=b params,
        # NOT a single comma-joined value -- must use getlist, not get().
        # Returns None when no filter form was submitted this request, so
        # callers can tell "not filtered yet -> fall back to prefs" apart
        # from "user explicitly submitted zero checked boxes".
        if "filtered" not in request.args:
            return None
        chosen = set(request.args.getlist("show"))
        return chosen & ALL_TRADITIONS

    def get_interfaith_by_date(start_g, end_g, traditions):
        if not traditions:
            return {}
        db = get_session()
        try:
            rows = db.query(InterfaithEvent).filter(
                InterfaithEvent.event_date >= start_g,
                InterfaithEvent.event_date <= end_g,
                InterfaithEvent.tradition.in_(traditions),
            ).all()
            by_date = {}
            for r in rows:
                by_date.setdefault(r.event_date, []).append({
                    "title": r.title, "tradition": r.tradition,
                    "is_holiday": r.is_holiday, "color": r.color,
                })
            return by_date
        finally:
            db.close()

    def get_personal_by_date(start_g, end_g):
        db = get_session()
        try:
            rows = db.query(PersonalEvent).all()
            by_date = {}
            for r in rows:
                for occ in pe.event_occurrences_in_range(r, start_g, end_g):
                    by_date.setdefault(occ, []).append({
                        "id": r.id, "title": r.title, "category": r.category,
                        "description": r.description, "color": r.color,
                    })
            return by_date
        finally:
            db.close()

    def get_personal_events_list():
        db = get_session()
        try:
            return (
                db.query(PersonalEvent)
                .order_by(PersonalEvent.anchor_date)
                .all()
            )
        finally:
            db.close()

    def get_hijri_events_for_gregorian_range(start_g, end_g, show_sources=None):
        """Same as before but with source filtering.

        IMPORTANT: Bohra uses the tabular Fatimid calendar (hijri_calendar.py);
        Sunni and Shia both use the Umm al-Qura-based civil calendar
        (sunni_calendar.py -- Shia delegates to it directly, see
        shia_calendar.py). These are DIFFERENT calendar systems with
        different epochs/leap-year rules that can land on different
        Gregorian dates for "the same" Hijri day. Every source's events
        must be matched using ITS OWN conversion of the Gregorian date, not
        one shared conversion -- using Bohra's conversion for Shia/Sunni
        events (the previous bug here) meant those events almost never
        matched the right Gregorian day."""
        if show_sources is None:
            show_sources = {'bohra', 'sunni', 'shia'}

        # Which Gregorian->Hijri function applies to each event_source.
        source_converters = {
            "bohra": hc.gregorian_to_hijri,
            "sunni": sc.sunni_gregorian_to_hijri,
            "shia": sc.sunni_gregorian_to_hijri,  # Shia dates run on the same Umm al-Qura calendar as Sunni
        }

        db = get_session()
        try:
            all_events = db.query(HijriEvent).filter(
                HijriEvent.event_source.in_(show_sources)
            ).all()
        finally:
            db.close()

        yearly, once = {}, {}
        for e in all_events:
            key = (e.event_source, e.hijri_month, e.hijri_day)
            if e.repeat == "once":
                once.setdefault(key + (e.hijri_year,), []).append(e)
            else:
                yearly.setdefault(key, []).append(e)

        by_greg = {}
        d = start_g
        while d <= end_g:
            matches = []
            for source in show_sources:
                converter = source_converters.get(source)
                if converter is None:
                    continue
                hy, hm, hd = converter(d)
                key = (source, hm, hd)
                matches += yearly.get(key, [])
                matches += once.get(key + (hy,), [])
            if matches:
                by_greg[d] = [{
                    "title": e.title, "description": e.description,
                    "is_fasting_day": e.is_fasting_day, "is_holiday": e.is_holiday,
                    "color": e.color,
                } for e in matches]
            d += timedelta(days=1)
        return by_greg

    def get_events_for_month(hijri_month, hijri_year=None):
        db = get_session()
        try:
            events = (
                db.query(HijriEvent)
                .filter(HijriEvent.hijri_month == hijri_month)
                .filter(
                    (HijriEvent.repeat != "once")
                    | (HijriEvent.hijri_year == hijri_year)
                )
                .all()
            )
            by_day = {}
            for e in events:
                by_day.setdefault(e.hijri_day, []).append({
                    "title": e.title, "description": e.description,
                    "is_fasting_day": e.is_fasting_day, "is_holiday": e.is_holiday,
                    "color": e.color,
                })
            return by_day
        finally:
            db.close()

    def get_community_lists(traditions_on=None, show_sources=None):
        """Full event list per community, for the inline sidebar accordion."""
        if traditions_on is None:
            traditions_on = ALL_TRADITIONS
        if show_sources is None:
            show_sources = {'bohra', 'sunni', 'shia'}
        
        db = get_session()
        try:
            # Get Bohra, Sunni, and Shia events
            bohra_rows = (
                db.query(HijriEvent)
                .filter(HijriEvent.event_source.in_(show_sources))
                .order_by(HijriEvent.hijri_month, HijriEvent.hijri_day)
                .all()
            )
            lists = {}
            
            # Group by source
            for source in show_sources:
                source_events = [e for e in bohra_rows if e.event_source == source]
                if source_events:
                    lists[source] = [
                        {"title": e.title, "when": f"{hc.hijri_month_name(e.hijri_month)} {e.hijri_day}"}
                        for e in source_events
                    ]
            
            today_g = date.today()
            for key in traditions_on:
                rows = (
                    db.query(InterfaithEvent)
                    .filter(InterfaithEvent.tradition == key, InterfaithEvent.event_date >= today_g)
                    .order_by(InterfaithEvent.event_date)
                    .all()
                )
                lists[key] = [
                    {"title": e.title, "when": e.event_date.strftime("%d %b %Y")}
                    for e in rows
                ]
            return lists
        finally:
            db.close()

    # ==================== HTML PAGES ====================

    @app.get("/")
    def index():
        return redirect(url_for("calendar_view"))

    @app.get("/calendar")
    def calendar_view():
        today_g = date.today()
        prefs = get_user_prefs()
        
        # Use the user's default calendar, or fallback to hijri
        cal_key = request.args.get("cal")
        if not cal_key or cal_key not in CALENDARS:
            cal_key = prefs.get("default_calendar", "hijri")
        if cal_key not in CALENDARS:
            cal_key = "hijri"
        cal = CALENDARS[cal_key]

        ty, tm, td = cal["native_of"](today_g)

        cal_year = request.args.get("y", type=int) or ty
        cal_month = request.args.get("m", type=int) or tm
        selected_day_num = request.args.get("day", type=int)

        # "Goto date" -- explicit navigation, takes priority over y/m if both
        # are somehow present. Always given as a Gregorian date (the <input
        # type="date"> the browser renders), converted to whatever calendar
        # is currently primary so the grid lands on the right native month.
        goto_str = request.args.get("goto")
        if goto_str:
            try:
                goto_date = date.fromisoformat(goto_str)
                cal_year, cal_month, _ = cal["native_of"](goto_date)
            except ValueError:
                flash("Could not understand that date -- try again.")

        grid = cal["grid"](cal_year, cal_month)  # [(gregorian_date, ordinal, native_label_input), ...]

        greg_days = [g for g, _, _ in grid]
        
        # Get visible traditions from user preferences or URL filters
        traditions_on = selected_traditions()
        if traditions_on is None:
            traditions_on = get_visible_traditions(prefs)
        
        # Get event sources to show (Bohra, Sunni, Shia)
        show_sources = set()
        if prefs.get("show_bohra", True):
            show_sources.add("bohra")
        if prefs.get("show_sunni", True):
            show_sources.add("sunni")
        if prefs.get("show_shia", True):
            show_sources.add("shia")
        
        # Get Bohra/Sunni/Shia events for the visible range
        hijri_events_by_day = get_hijri_events_for_gregorian_range(
            min(greg_days), max(greg_days), show_sources
        )
        
        # Get interfaith events (Christian, Jewish, Hindu, Parsi, French)
        interfaith_by_date = get_interfaith_by_date(
            min(greg_days), max(greg_days), traditions_on
        )
        
        # Get personal events
        personal_by_date = get_personal_by_date(
            min(greg_days), max(greg_days)
        )

        # Get secondary calendar info -- computed before the days loop below
        # so each day can carry its secondary-calendar native label.
        secondary_cal = prefs.get("secondary_calendar", "")
        show_secondary = bool(secondary_cal and secondary_cal in CALENDARS and secondary_cal != cal_key)
        secondary_cal_obj = CALENDARS[secondary_cal] if show_secondary else None

        days = []
        for g, ordinal, label_input in grid:
            # Filter personal events based on user preference
            personal_events = personal_by_date.get(g, [])
            if not prefs.get("show_personal", True):
                personal_events = []

            secondary_num = None
            if secondary_cal_obj:
                _, _, sec_label_input = secondary_cal_obj["native_of"](g)
                secondary_num = secondary_cal_obj["native_label"](sec_label_input)

            is_ekadashi = is_purnima = False
            if cal_key == "hindu":
                # label_input here is the (tithi, paksha) tuple _grid_hindu
                # builds -- reuse it rather than recomputing tithi_on(g) again.
                tithi_n, paksha_n = label_input
                is_ekadashi = tithi_n == 11
                is_purnima = tithi_n == 15 and paksha_n == hindu.PAKSHA_SHUKLA

            days.append({
                "hijri_day": ordinal,
                "hijri_num": cal["native_label"](label_input),
                "greg_day": g.day,
                "gregorian": g,
                "is_today": (g == today_g),
                "events": hijri_events_by_day.get(g, []),
                "interfaith": interfaith_by_date.get(g, []),
                "personal": personal_events,
                "secondary_num": secondary_num,
                "is_ekadashi": is_ekadashi,
                "is_purnima": is_purnima,
            })

        # build Sunday-first week grid
        first_weekday = (days[0]["gregorian"].weekday() + 1) % 7  # Python Mon=0 -> Sun=0
        weeks = []
        week = [None] * first_weekday
        for d in days:
            week.append(d)
            if len(week) == 7:
                weeks.append(week)
                week = []
        if week:
            week += [None] * (7 - len(week))
            weeks.append(week)

        greg_start, greg_end = days[0]["gregorian"], days[-1]["gregorian"]
        if greg_start.month == greg_end.month:
            gregorian_range = greg_start.strftime("%B %Y")
        else:
            gregorian_range = f"{greg_start.strftime('%B')}/{greg_end.strftime('%B %Y')}"

        selected_day = None
        if selected_day_num:
            selected_day = next((d for d in days if d["hijri_day"] == selected_day_num), None)

        loc = current_location()
        prayer_date = selected_day["gregorian"] if selected_day else today_g
        prayer = pt.calculate(loc["lat"], loc["lng"], prayer_date, loc["tz_offset"])

        hindu_daily = None
        if cal_key == "hindu":
            hd_tithi, hd_paksha = hindu.tithi_on(today_g, loc["lat"], loc["lng"])
            hd_muhurats = hindu.daily_muhurats(loc["lat"], loc["lng"], today_g, loc["tz_offset"])

            def _mins(hhmm):
                h, m = hhmm.split(":")
                return int(h) * 60 + int(m)

            span_start = _mins(hd_muhurats["sunrise"])
            span = max(_mins(hd_muhurats["sunset"]) - span_start, 1)

            def _pct(hhmm):
                return round((_mins(hhmm) - span_start) / span * 100, 2)

            hindu_daily = {
                "tithi": hd_tithi,
                "paksha": hd_paksha,
                "nakshatra": hindu.nakshatra_on(today_g, loc["lat"], loc["lng"]),
                "sunrise": hd_muhurats["sunrise"],
                "sunset": hd_muhurats["sunset"],
                "rahu_kalam": hd_muhurats["rahu_kalam"],
                "abhijit": hd_muhurats["abhijit"],
                "timeline": {
                    "rahu_kalam_left": _pct(hd_muhurats["rahu_kalam"]["start"]),
                    "rahu_kalam_width": round((_mins(hd_muhurats["rahu_kalam"]["end"]) - _mins(hd_muhurats["rahu_kalam"]["start"])) / span * 100, 2),
                    "abhijit_left": _pct(hd_muhurats["abhijit"]["start"]),
                    "abhijit_width": round((_mins(hd_muhurats["abhijit"]["end"]) - _mins(hd_muhurats["abhijit"]["start"])) / span * 100, 2),
                },
            }

        # Get user's custom events (only Bohra events for now, can extend)
        db = get_session()
        try:
            user_events = (
                db.query(HijriEvent)
                .filter(HijriEvent.is_custom == True)  # noqa: E712
                .filter(HijriEvent.event_source == "bohra")  # Only Bohra custom events
                .order_by(HijriEvent.hijri_month, HijriEvent.hijri_day)
                .all()
            )
        finally:
            db.close()

        prev_year, prev_month = cal["prev"](cal_year, cal_month)
        next_year, next_month = cal["next"](cal_year, cal_month)

        return render_template(
            "calendar.html", 
            active="calendar",
            cal=cal_key, 
            calendars=CALENDARS,
            hijri_year=cal_year, 
            hijri_month=cal_month,
            month_name=cal["month_name"](cal_year, cal_month),
            month_names=hc.MONTH_NAMES,
            prev_year=prev_year, 
            prev_month=prev_month,
            next_year=next_year, 
            next_month=next_month,
            gregorian_range=gregorian_range, 
            weeks=weeks,
            prayer=prayer, 
            location_name=loc["name"], 
            selected_day=selected_day,
            traditions=ic.TRADITIONS, 
            traditions_on=traditions_on,
            filter_active=("filtered" in request.args),
            user_events=user_events,
            personal_events=get_personal_events_list(),
            community_lists=get_community_lists(traditions_on, show_sources),
            location_is_default=location_is_default(),
            secondary_calendar=secondary_cal,
            show_secondary=show_secondary,
            user_prefs=prefs,
            hindu_daily=hindu_daily,
        )

    @app.get("/prayer-times-view")
    def prayer_view():
        loc = current_location()
        d = date.today()
        prayer = pt.calculate(loc["lat"], loc["lng"], d, loc["tz_offset"])
        return render_template("prayer.html", active="prayer", prayer=prayer,
                                location_name=loc["name"], date_str=d.strftime("%d %B %Y"),
                                location_is_default=location_is_default())

    @app.get("/qibla-view")
    def qibla_view():
        loc = current_location()
        bearing = round(qb.bearing_to_kaaba(loc["lat"], loc["lng"]), 1)
        distance = round(qb.distance_km(loc["lat"], loc["lng"]), 1)
        return render_template("qibla.html", active="qibla", bearing=bearing,
                                distance_km=distance, location_name=loc["name"],
                                location_is_default=location_is_default())

    @app.route("/settings", methods=["GET", "POST"])
    def settings_view():
        if request.method == "POST":
            try:
                new_loc = {
                    "name": request.form["location_name"],
                    "lat": float(request.form["lat"]),
                    "lng": float(request.form["lng"]),
                    "tz_offset": float(request.form["tz_offset"]),
                }
                session["location"] = new_loc
                
                # Save preferences
                prefs = {
                    "default_calendar": request.form.get("default_calendar", "hijri"),
                    "secondary_calendar": request.form.get("secondary_calendar", ""),
                    "show_bohra": "show_bohra" in request.form,
                    "show_sunni": "show_sunni" in request.form,
                    "show_shia": "show_shia" in request.form,
                    "show_christian": "show_christian" in request.form,
                    "show_jewish": "show_jewish" in request.form,
                    "show_hindu": "show_hindu" in request.form,
                    "show_parsi": "show_parsi" in request.form,
                    "show_french": "show_french" in request.form,
                    "show_personal": "show_personal" in request.form,
                }
                session["preferences"] = prefs
                flash("Settings updated.")
                return redirect(url_for("calendar_view"))
            except (KeyError, ValueError):
                flash("Please fill in all fields with valid numbers.")
                return redirect(url_for("settings_view"))

        prefs = get_user_prefs()
        return render_template("settings.html", active="settings", location=current_location(), prefs=prefs)

    @app.route("/events-view", methods=["GET", "POST"])
    def events_view():
        tab = request.args.get("tab", "bohra")
        if tab not in ({"bohra", "personal"} | ALL_TRADITIONS):
            tab = "bohra"

        db = get_session()
        try:
            if request.method == "POST":
                if tab == "personal":
                    raw_date = request.form.get("anchor_date")
                    if not raw_date:
                        raise ValueError("Please pick a date.")
                    repeat = request.form.get("repeat", "yearly")
                    if repeat not in pe.VALID_REPEATS:
                        raise ValueError("repeat must be one of: never, weekly, monthly, yearly")

                    # Optional companion Hijri date (both fields must be present
                    # together, or neither -- a lone month or lone day is
                    # treated as "not provided" rather than guessed at).
                    raw_hm = request.form.get("hijri_month")
                    raw_hd = request.form.get("hijri_day")
                    hijri_month = int(raw_hm) if raw_hm else None
                    hijri_day = int(raw_hd) if raw_hd else None
                    if (hijri_month is None) != (hijri_day is None):
                        raise ValueError("Provide both a Hijri month and day, or leave both blank.")
                    if hijri_month is not None and not (1 <= hijri_month <= 12):
                        raise ValueError("Hijri month must be between 1 and 12.")
                    if hijri_day is not None and not (1 <= hijri_day <= 30):
                        raise ValueError("Hijri day must be between 1 and 30.")

                    recur_calendar = request.form.get("recur_calendar", "gregorian")
                    if recur_calendar not in pe.VALID_RECUR_CALENDARS:
                        raise ValueError("recur_calendar must be 'gregorian' or 'hijri'")
                    if recur_calendar == "hijri" and hijri_month is None:
                        raise ValueError("Add a Hijri date before choosing to recur by it.")

                    p = PersonalEvent(
                        title=request.form["title"],
                        description=request.form.get("description") or None,
                        category=request.form.get("category", "other"),
                        anchor_date=date.fromisoformat(raw_date),
                        repeat=repeat,
                        color=request.form.get("color", "personal"),
                        hijri_month=hijri_month,
                        hijri_day=hijri_day,
                        recur_calendar=recur_calendar,
                    )
                    db.add(p)
                    db.commit()
                    flash(f"Added: {p.title}")
                    if request.form.get("redirect_to") == "calendar":
                        return redirect(url_for("calendar_view"))
                    return redirect(url_for("events_view", tab="personal"))

                repeat = request.form.get("repeat", "yearly")
                if repeat not in {"yearly", "once"}:
                    raise ValueError("repeat must be 'yearly' or 'once'")

                raw_hm = request.form.get("hijri_month")
                raw_hd = request.form.get("hijri_day")
                raw_gd = request.form.get("gregorian_date")

                g = date.fromisoformat(raw_gd) if raw_gd else None
                derived = hc.gregorian_to_hijri(g) if g else None  # (year, month, day)

                hijri_month = int(raw_hm) if raw_hm else (derived[1] if derived else None)
                hijri_day = int(raw_hd) if raw_hd else (derived[2] if derived else None)
                if hijri_month is None or hijri_day is None:
                    raise ValueError("Enter a Hijri month/day, a Gregorian date, or both.")
                if not (1 <= hijri_month <= 12):
                    raise ValueError("hijri_month must be 1-12")
                if not (1 <= hijri_day <= 30):
                    raise ValueError("hijri_day must be 1-30")

                hijri_year = None
                if repeat == "once":
                    raw_hy = request.form.get("hijri_year")
                    if raw_hy:
                        hijri_year = int(raw_hy)
                    elif derived:
                        hijri_year = derived[0]
                    else:
                        raise ValueError("A one-time event needs a Gregorian date or a Hijri year.")

                e = HijriEvent(
                    hijri_month=hijri_month,
                    hijri_day=hijri_day,
                    title=request.form["title"],
                    description=request.form.get("description") or None,
                    is_holiday=request.form.get("is_holiday") == "yes",
                    is_fasting_day=request.form.get("is_fasting_day") == "yes",
                    color=request.form.get("color", "black"),
                    is_custom=True,
                    repeat=repeat,
                    hijri_year=hijri_year,
                    gregorian_date=g,
                )
                db.add(e)
                db.commit()
                flash(f"Added: {e.title}")
                if request.form.get("redirect_to") == "calendar":
                    return redirect(url_for("calendar_view"))
                return redirect(url_for("events_view", tab="bohra"))

            events = db.query(HijriEvent).order_by(HijriEvent.hijri_month, HijriEvent.hijri_day).all()
            # Seeded/global events (is_custom == False) are shared, default data everyone
            # sees on the calendar and in the full Bohra list above -- they are NOT "your"
            # events. Only ones added through the Add Event form belong in that panel.
            custom_events = [e for e in events if e.is_custom]

            interfaith_events = []
            if tab != "bohra" and tab != "personal":
                interfaith_events = (
                    db.query(InterfaithEvent)
                    .filter(InterfaithEvent.tradition == tab)
                    .order_by(InterfaithEvent.event_date)
                    .all()
                )

            personal_events = []
            if tab == "personal":
                personal_events = (
                    db.query(PersonalEvent)
                    .order_by(PersonalEvent.anchor_date)
                    .all()
                )
                # Age/years-since only means something for events that recur
                # yearly on a fixed anniversary -- a 'weekly'/'monthly'/'never'
                # entry (e.g. a recurring reminder) has no meaningful "age".
                for pev in personal_events:
                    pev.age = pe.age_on(pev.anchor_date) if pev.repeat == "yearly" else None

            return render_template(
                "events.html", active="events", events=events, custom_events=custom_events,
                month_names=hc.MONTH_NAMES, tab=tab, traditions=ic.TRADITIONS,
                interfaith_events=interfaith_events,
                personal_events=personal_events,
                repeat_options=sorted(pe.VALID_REPEATS, key=["never", "weekly", "monthly", "yearly"].index),
            )
        finally:
            db.close()

    @app.post("/events-view/<int:event_id>/delete")
    def delete_event(event_id):
        db = get_session()
        try:
            e = db.query(HijriEvent).filter(HijriEvent.id == event_id).first()
            if e:
                db.delete(e)
                db.commit()
                flash(f"Deleted: {e.title}")
        finally:
            db.close()
        return redirect(url_for("events_view", tab="bohra"))

    @app.post("/personal-events/<int:event_id>/delete")
    def delete_personal_event(event_id):
        db = get_session()
        try:
            e = db.query(PersonalEvent).filter(PersonalEvent.id == event_id).first()
            if e:
                db.delete(e)
                db.commit()
                flash(f"Deleted: {e.title}")
        finally:
            db.close()
        return redirect(url_for("events_view", tab="personal"))

    @app.post("/events-view/bulk-import")
    def bulk_import_events():
        raw = request.form.get("bulk_text", "")
        lines = [ln.strip() for ln in raw.splitlines() if ln.strip() and not ln.strip().startswith("#")]
        added, errors = 0, []

        db = get_session()
        try:
            for i, line in enumerate(lines, start=1):
                parts = [p.strip() for p in line.split(",")]
                if len(parts) < 3:
                    errors.append(f"line {i}: need at least month,day,title")
                    continue
                try:
                    month = int(parts[0])
                    day = int(parts[1])
                    title = parts[2]
                    is_holiday = len(parts) > 3 and parts[3].lower() in ("yes", "true", "1")
                    is_fasting = len(parts) > 4 and parts[4].lower() in ("yes", "true", "1")
                    color = parts[5] if len(parts) > 5 and parts[5] else "black"
                    if not (1 <= month <= 12):
                        raise ValueError("month out of range 1-12")
                    if not (1 <= day <= 30):
                        raise ValueError("day out of range 1-30")
                except ValueError as ve:
                    errors.append(f"line {i}: {ve}")
                    continue
                db.add(HijriEvent(hijri_month=month, hijri_day=day, title=title,
                                   is_holiday=is_holiday, is_fasting_day=is_fasting, color=color))
                added += 1
            db.commit()
        finally:
            db.close()

        if added:
            flash(f"Imported {added} event(s).")
        if errors:
            flash("Skipped: " + "; ".join(errors[:5]) + ("..." if len(errors) > 5 else ""))
        return redirect(url_for("events_view", tab="bohra"))

    @app.post("/events-view/clear-all")
    def clear_all_events():
        db = get_session()
        try:
            count = db.query(HijriEvent).delete()
            db.commit()
        finally:
            db.close()
        flash(f"Deleted all {count} event(s).")
        return redirect(url_for("events_view", tab="bohra"))

    # ==================== JSON API (unchanged, under /api) ====================

    def parse_float(name, required=True, default=None):
        raw = request.args.get(name)
        if raw is None:
            if required:
                raise ValueError(f"missing required query param: {name}")
            return default
        try:
            return float(raw)
        except ValueError:
            raise ValueError(f"{name} must be a number, got: {raw!r}")

    @app.errorhandler(ValueError)
    def handle_value_error(e):
        if request.path.startswith("/api"):
            return jsonify({"error": str(e)}), 400
        flash(str(e))
        return redirect(request.referrer or url_for("calendar_view"))

    @app.get("/api/calendar/today")
    def api_today():
        g = date.today()
        y, m, d = hc.gregorian_to_hijri(g)
        return jsonify({"gregorian": g.isoformat(), "hijri_year": y, "hijri_month": m,
                         "hijri_month_name": hc.hijri_month_name(m), "hijri_day": d})

    @app.get("/api/calendar/month/<int:hijri_year>/<int:hijri_month>")
    def api_month(hijri_year, hijri_month):
        if not (1 <= hijri_month <= 12):
            raise ValueError("hijri_month must be 1-12")
        days = hc.month_grid(hijri_year, hijri_month)
        events_by_day = get_events_for_month(hijri_month, hijri_year)
        for d in days:
            d["events"] = events_by_day.get(d["hijri_day"], [])
        return jsonify({"hijri_year": hijri_year, "hijri_month": hijri_month,
                         "hijri_month_name": hc.hijri_month_name(hijri_month), "days": days})

    @app.get("/api/prayer-times")
    def api_prayer_times():
        lat = parse_float("lat")
        lng = parse_float("lng")
        tz_offset = parse_float("tz_offset")
        for_date = request.args.get("for_date")
        d = date.fromisoformat(for_date) if for_date else date.today()
        return jsonify(pt.calculate(lat, lng, d, tz_offset))

    @app.get("/api/tz-offset")
    def api_tz_offset():
        """Real UTC offset for a lat/lng, via IANA timezone lookup -- not a
        longitude estimate. Fixes locations like India where the political
        offset (+5:30) doesn't match the meridian math (+6:00 for eastern
        India, +5:00 for western India)."""
        lat = parse_float("lat")
        lng = parse_float("lng")
        for_date_str = request.args.get("for_date")
        for_date = date.fromisoformat(for_date_str) if for_date_str else None

        offset = tzl.utc_offset_hours(lat, lng, for_date)
        if offset is None:
            return jsonify({
                "offset": None,
                "tz_name": None,
                "error": "timezone lookup unavailable -- is timezonefinder installed?",
            }), 200
        return jsonify({"offset": offset, "tz_name": tzl.tz_name_at(lat, lng)})

    @app.get("/api/qibla")
    def api_qibla():
        lat = parse_float("lat")
        lng = parse_float("lng")
        return jsonify({"bearing_degrees": round(qb.bearing_to_kaaba(lat, lng), 2),
                         "distance_km": round(qb.distance_km(lat, lng), 1)})

    @app.get("/api/events")
    def api_list_events():
        hijri_month = request.args.get("hijri_month", type=int)
        db = get_session()
        try:
            q = db.query(HijriEvent)
            if hijri_month:
                q = q.filter(HijriEvent.hijri_month == hijri_month)
            result = [{"id": e.id, "hijri_month": e.hijri_month, "hijri_day": e.hijri_day,
                       "title": e.title, "description": e.description,
                       "is_fasting_day": e.is_fasting_day, "is_holiday": e.is_holiday,
                       "color": e.color} for e in q.all()]
        finally:
            db.close()
        return jsonify(result)

    @app.post("/api/events")
    def api_add_event():
        body = request.get_json(force=True, silent=True) or {}
        missing = [k for k in ["hijri_month", "hijri_day", "title"] if k not in body]
        if missing:
            raise ValueError(f"missing fields: {', '.join(missing)}")
        db = get_session()
        try:
            e = HijriEvent(hijri_month=body["hijri_month"], hijri_day=body["hijri_day"],
                            title=body["title"], description=body.get("description"),
                            is_fasting_day=bool(body.get("is_fasting_day", False)),
                            is_holiday=bool(body.get("is_holiday", False)),
                            color=body.get("color", "black"))
            db.add(e)
            db.commit()
            db.refresh(e)
            new_id = e.id
        finally:
            db.close()
        return jsonify({"id": new_id, "status": "created"}), 201

    return app
