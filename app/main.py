from datetime import date, datetime

from flask import Flask, request, jsonify, render_template, session, redirect, url_for, flash
from flask_cors import CORS

from . import hijri_calendar as hc
from . import prayer_times as pt
from . import qibla as qb
from .database import get_session, init_db, seed_if_empty, HijriEvent

DEFAULT_LOCATION = {"name": "Mumbai, Maharashtra", "lat": 19.076, "lng": 72.877, "tz_offset": 5.5}


def create_app():
    app = Flask(__name__)
    app.secret_key = "dev-secret-change-this-before-any-real-deployment"
    CORS(app)

    init_db()
    seed_if_empty()

    # ---------- shared helpers ----------

    def current_location():
        return session.get("location", DEFAULT_LOCATION)

    def get_events_for_month(hijri_month):
        db = get_session()
        try:
            events = db.query(HijriEvent).filter(HijriEvent.hijri_month == hijri_month).all()
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

    # ==================== HTML PAGES ====================

    @app.get("/")
    def index():
        return redirect(url_for("calendar_view"))

    @app.get("/calendar")
    def calendar_view():
        today_g = date.today()
        ty, tm, td = hc.gregorian_to_hijri(today_g)

        hijri_year = request.args.get("y", type=int) or ty
        hijri_month = request.args.get("m", type=int) or tm
        selected_day_num = request.args.get("day", type=int)

        if hijri_month < 1:
            hijri_month = 12
            hijri_year -= 1
        elif hijri_month > 12:
            hijri_month = 1
            hijri_year += 1

        days_raw = hc.month_grid(hijri_year, hijri_month)
        events_by_day = get_events_for_month(hijri_month)

        days = []
        for d in days_raw:
            g = date.fromisoformat(d["gregorian"])
            days.append({
                "hijri_day": d["hijri_day"],
                "hijri_num": hc.to_arabic_indic_numerals(d["hijri_day"]),
                "greg_day": g.day,
                "gregorian": g,
                "is_today": (hijri_year == ty and hijri_month == tm and d["hijri_day"] == td),
                "events": events_by_day.get(d["hijri_day"], []),
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

        loc = current_location()
        prayer = pt.calculate(loc["lat"], loc["lng"], today_g, loc["tz_offset"])

        selected_day = None
        if selected_day_num:
            selected_day = next((d for d in days if d["hijri_day"] == selected_day_num), None)

        return render_template(
            "calendar.html", active="calendar",
            hijri_year=hijri_year, hijri_month=hijri_month,
            month_name=hc.hijri_month_name(hijri_month),
            prev_year=hijri_year if hijri_month > 1 else hijri_year - 1,
            prev_month=hijri_month - 1 if hijri_month > 1 else 12,
            next_year=hijri_year if hijri_month < 12 else hijri_year + 1,
            next_month=hijri_month + 1 if hijri_month < 12 else 1,
            gregorian_range=gregorian_range, weeks=weeks,
            prayer=prayer, location_name=loc["name"], selected_day=selected_day,
        )

    @app.get("/prayer-times-view")
    def prayer_view():
        loc = current_location()
        d = date.today()
        prayer = pt.calculate(loc["lat"], loc["lng"], d, loc["tz_offset"])
        return render_template("prayer.html", active="prayer", prayer=prayer,
                                location_name=loc["name"], date_str=d.strftime("%d %B %Y"))

    @app.get("/qibla-view")
    def qibla_view():
        loc = current_location()
        bearing = round(qb.bearing_to_kaaba(loc["lat"], loc["lng"]), 1)
        distance = round(qb.distance_km(loc["lat"], loc["lng"]), 1)
        return render_template("qibla.html", active="qibla", bearing=bearing,
                                distance_km=distance, location_name=loc["name"])

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
            except (KeyError, ValueError):
                flash("Please fill in all fields with valid numbers.")
                return redirect(url_for("settings_view"))
            session["location"] = new_loc
            flash("Location updated.")
            return redirect(url_for("calendar_view"))
        return render_template("settings.html", active="settings", location=current_location())

    @app.route("/events-view", methods=["GET", "POST"])
    def events_view():
        db = get_session()
        try:
            if request.method == "POST":
                e = HijriEvent(
                    hijri_month=int(request.form["hijri_month"]),
                    hijri_day=int(request.form["hijri_day"]),
                    title=request.form["title"],
                    description=request.form.get("description") or None,
                    is_holiday=bool(request.form.get("is_holiday")),
                    is_fasting_day=bool(request.form.get("is_fasting_day")),
                    color=request.form.get("color", "black"),
                )
                db.add(e)
                db.commit()
                flash(f"Added: {e.title}")
                return redirect(url_for("events_view"))

            events = db.query(HijriEvent).order_by(HijriEvent.hijri_month, HijriEvent.hijri_day).all()
            return render_template("events.html", active="events", events=events,
                                    month_names=hc.MONTH_NAMES)
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
        return redirect(url_for("events_view"))

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
        return redirect(url_for("events_view"))

    @app.post("/events-view/clear-all")
    def clear_all_events():
        db = get_session()
        try:
            count = db.query(HijriEvent).delete()
            db.commit()
        finally:
            db.close()
        flash(f"Deleted all {count} event(s).")
        return redirect(url_for("events_view"))

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
        events_by_day = get_events_for_month(hijri_month)
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
