"""SQLite storage for Bohra calendar events (misaqs, urs, eids, etc.)."""

from sqlalchemy import create_engine, Column, Integer, String, Boolean, Date, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

DATABASE_URL = "sqlite:///./bohra_calendar.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


# In the HijriEvent class, add this field:
class HijriEvent(Base):
    __tablename__ = "hijri_events"
    
    id = Column(Integer, primary_key=True, index=True)
    hijri_month = Column(Integer, index=True)
    hijri_day = Column(Integer, index=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    is_fasting_day = Column(Boolean, default=False)
    is_holiday = Column(Boolean, default=False)
    color = Column(String, default="black")
    is_custom = Column(Boolean, default=False)
    repeat = Column(String, default="yearly")
    hijri_year = Column(Integer, nullable=True)
    gregorian_date = Column(Date, nullable=True)
    
    # NEW: Which tradition this event belongs to
    event_source = Column(String, default="bohra")  # 'bohra', 'sunni', 'shia'


class InterfaithEvent(Base):
    """Auto-generated festival dates for non-Bohra traditions (Christian, French
    civil, Jewish, Hindu). Regenerated on startup for a rolling year window --
    do not hand-edit rows here, edit interfaith_calendar.py instead.
    See that module's docstring for accuracy caveats per tradition."""
    __tablename__ = "interfaith_events"

    id = Column(Integer, primary_key=True, index=True)
    event_date = Column(Date, index=True)
    title = Column(String, nullable=False)
    tradition = Column(String, index=True)   # 'christian' | 'french' | 'jewish' | 'hindu'
    is_holiday = Column(Boolean, default=False)
    color = Column(String, default="black")


class PersonalEvent(Base):
    """User's own recurring personal dates -- birthdays, anniversaries, and
    anything else that isn't a Bohra or interfaith date. Stored as a single
    Gregorian anchor date plus a repeat rule; individual occurrences are
    computed on the fly by personal_events.py rather than one row per year,
    so "repeat every year forever" doesn't need pre-generated rows."""
    __tablename__ = "personal_events"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    category = Column(String, default="other")     # 'birthday' | 'anniversary' | 'other'
    anchor_date = Column(Date, nullable=False)      # the Gregorian first/reference occurrence
    repeat = Column(String, default="yearly")       # 'never' | 'weekly' | 'monthly' | 'yearly'
    color = Column(String, default="personal")

    # Optional companion Hijri date for the same event (e.g. an anniversary
    # you want to track on both calendars). Independent of anchor_date --
    # neither is derived from the other, both are entered by the user.
    hijri_month = Column(Integer, nullable=True)    # 1-12
    hijri_day = Column(Integer, nullable=True)      # 1-30

    # Which calendar actually drives "repeat" when repeat == 'yearly' and a
    # Hijri date is present. Gregorian and Hijri years are different lengths
    # (~11 days apart per year), so a yearly-recurring anniversary can only
    # correctly track ONE of them -- this field says which. Ignored for
    # 'never'/'weekly'/'monthly' repeat, and irrelevant if hijri_month/day
    # aren't set (there's nothing to choose between).
    recur_calendar = Column(String, default="gregorian")  # 'gregorian' | 'hijri'

    # Optional "complete info of the person" fields -- all nullable, so
    # existing rows (and anyone who leaves these blank) are unaffected.
    # These are about the PERSON the event is for, not the event itself --
    # keep that distinction if you add more fields here later.
    person_name = Column(String, nullable=True)   # e.g. "Fatima Bhen" -- separate from `title` (e.g. "Fatima's Birthday")
    relation = Column(String, nullable=True)       # e.g. "Sister", "Colleague"
    phone = Column(String, nullable=True)          # free-text, no validation -- add a format check before trusting this for anything automated

    # Per-event ringtone override -- key into main.py's RINGTONE_OPTIONS.
    # None/blank means "use the category default from Settings"
    # (birthday_ringtone / anniversary_ringtone), not "no sound".
    ringtone = Column(String, nullable=True)


class Note(Base):
    """The single shared sticky-note shown in the sidebar (base.html). Not
    per-user -- there's no auth in this app, so this is just one global
    scratch pad, same as the rest of the app's session-based 'preferences'
    being effectively single-tenant. Only row id=1 is ever used."""
    __tablename__ = "sidebar_note"

    id = Column(Integer, primary_key=True, index=True)
    content = Column(String, default="")


def get_or_create_note(db):
    """Fetch the single shared Note row, creating it (empty) on first use.
    Callers (main.py's inject_sidebar_note / save_note) always go through
    this rather than querying Note directly, so there's exactly one place
    that creates row id=1."""
    note = db.query(Note).first()
    if note is None:
        note = Note(content="")
        db.add(note)
        db.commit()
        db.refresh(note)
    return note


class CustomRingtone(Base):
    """A ringtone the user uploaded themselves (Settings -> Sound reminders),
    on top of the built-in RINGTONE_OPTIONS in main.py. `key` is what gets
    stored in prefs.birthday_ringtone/anniversary_ringtone/event.ringtone --
    same role the built-in dict keys play, just DB-backed so uploads persist.
    `filename` is the on-disk name under static/sounds/uploads/, not the
    original upload name (that's kept only in `label`) -- avoids collisions
    and path-traversal footguns from trusting a browser-supplied filename."""
    __tablename__ = "custom_ringtones"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, nullable=False, index=True)
    label = Column(String, nullable=False)
    filename = Column(String, nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow)


def init_db():
    Base.metadata.create_all(bind=engine)
    _migrate_missing_columns()


def _migrate_missing_columns():
    """SQLAlchemy's create_all() only creates tables that don't exist yet --
    it never alters an existing table to add a newly-defined column. Since
    this app is under active development and columns get added to the
    models over time (e.g. is_custom on HijriEvent), check for and add any
    columns that are missing from the actual on-disk schema so a pre-existing
    bohra_calendar.db doesn't crash with 'no such column' on the next run."""
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    for table in Base.metadata.tables.values():
        if table.name not in inspector.get_table_names():
            continue  # brand new table, create_all already handled it
        existing_cols = {c["name"] for c in inspector.get_columns(table.name)}
        for col in table.columns:
            if col.name in existing_cols:
                continue
            col_type = col.type.compile(engine.dialect)
            default_clause = ""
            if col.default is not None and col.default.is_scalar:
                default_val = col.default.arg
                if isinstance(default_val, bool):
                    default_val = int(default_val)
                if isinstance(default_val, (int, float)):
                    default_clause = f" DEFAULT {default_val}"
                elif isinstance(default_val, str):
                    default_clause = f" DEFAULT '{default_val}'"
            with engine.begin() as conn:
                conn.execute(text(
                    f"ALTER TABLE {table.name} ADD COLUMN {col.name} {col_type}{default_clause}"
                ))


def get_db():
    """FastAPI-style dependency generator (kept for reference / if you go back to FastAPI)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_session():
    """Plain session factory for Flask routes - caller is responsible for closing it."""
    return SessionLocal()


# Major Eid/fasting days - these are widely-observed dates, kept as-is.
EID_AND_FASTING_EVENTS = [
    {"hijri_month": 1, "hijri_day": 1, "title": "Eid-e-Milad / New Year", "is_holiday": True, "color": "red"},
    {"hijri_month": 9, "hijri_day": 1, "title": "Ramadan begins", "is_fasting_day": True, "color": "red"},
    {"hijri_month": 10, "hijri_day": 1, "title": "Eid al-Fitr", "is_holiday": True, "color": "red"},
    {"hijri_month": 12, "hijri_day": 10, "title": "Eid al-Adha", "is_holiday": True, "color": "red"},
    {"hijri_month": 12, "hijri_day": 18, "title": "Eid al-Ghadeer", "is_holiday": True, "color": "red"},
]

# Miladeen, shahadats, and other named observances -- transcribed from a
# user-supplied list. Four dates from that list are DELIBERATELY EXCLUDED
# here because they'd duplicate rows already in EID_AND_FASTING_EVENTS:
# 1/1 (New Year), 10/1 (Eid al-Fitr), 12/10 (Eid al-Adha), 12/18 (Eid
# al-Ghadeer). The "1st-30th Ramadan daily fasting" line from that list is
# also excluded -- it's not a per-day event, it's covered by the existing
# 9/1 "Ramadan begins" fasting-day row.
# Multi-day ranges (Ashara Mubaraka, Ayyam-ul-Beez) are expanded into one
# row per day since HijriEvent has no date-range field.
MAJOR_OBSERVANCES = [
    # --- Moharram al-Haraam (1) ---
    {"hijri_month": 1, "hijri_day": 2, "title": "Ashara Mubaraka - Day 2 (sermons and majalis)"},
    {"hijri_month": 1, "hijri_day": 3, "title": "Ashara Mubaraka - Day 3 (sermons and majalis)"},
    {"hijri_month": 1, "hijri_day": 4, "title": "Ashara Mubaraka - Day 4 (sermons and majalis)"},
    {"hijri_month": 1, "hijri_day": 5, "title": "Ashara Mubaraka - Day 5 (sermons and majalis)"},
    {"hijri_month": 1, "hijri_day": 6, "title": "Ashara Mubaraka - Day 6 (sermons and majalis)"},
    {"hijri_month": 1, "hijri_day": 7, "title": "Ashara Mubaraka - Day 7 (sermons and majalis)"},
    {"hijri_month": 1, "hijri_day": 8, "title": "Ashara Mubaraka - Day 8 (sermons and majalis)"},
    {"hijri_month": 1, "hijri_day": 9, "title": "Ashara Mubaraka - Day 9 (sermons and majalis)"},
    {"hijri_month": 1, "hijri_day": 10, "title": "Yaum-e-Aashura - Martyrdom of Imam Husain AS"},
    {"hijri_month": 1, "hijri_day": 13, "title": "Milad of Imam Aamir AS"},
    {"hijri_month": 1, "hijri_day": 15, "title": "Milad of Imam Nizar al-Aziz AS"},

    # --- Safar al-Muzaffar (2) ---
    {"hijri_month": 2, "hijri_day": 16, "title": "Commemoration of Syedna Mohammed Burhanuddin RA"},
    {"hijri_month": 2, "hijri_day": 20, "title": "Chehlum of Imam Husain AS"},
    {"hijri_month": 2, "hijri_day": 28, "title": "Wafat of Prophet Muhammad SAW and Shahadat of Imam Hasan AS"},

    # --- Rabi al-Awwal (3) ---
    {"hijri_month": 3, "hijri_day": 12, "title": "Eid-e-Milad-un-Nabi - Milad of Prophet Mohammed SAW", "is_holiday": True, "color": "red"},
    {"hijri_month": 3, "hijri_day": 12, "title": "Milad of Syedna Ismail bin Jafar"},
    {"hijri_month": 3, "hijri_day": 17, "title": "Milad of Imam Jafar al-Sadiq AS"},

    # --- Jumada al-Ukhra (6) ---
    {"hijri_month": 6, "hijri_day": 20, "title": "Milad of Maulatena Fatema Zahra AS"},

    # --- Rajab al-Asab (7) ---
    {"hijri_month": 7, "hijri_day": 1, "title": "Milad of Imam Mohammed al-Baqir AS"},
    {"hijri_month": 7, "hijri_day": 13, "title": "Milad of Maulana Ali ibn Abi Talib AS"},
    {"hijri_month": 7, "hijri_day": 13, "title": "Ayyam-ul-Beez fast - Day 1", "is_fasting_day": True},
    {"hijri_month": 7, "hijri_day": 14, "title": "Ayyam-ul-Beez fast - Day 2", "is_fasting_day": True},
    {"hijri_month": 7, "hijri_day": 15, "title": "Ayyam-ul-Beez fast - Day 3", "is_fasting_day": True},
    {"hijri_month": 7, "hijri_day": 27, "title": "Laylat al-Mab'ath"},

    # --- Shabaan al-Karim (8) ---
    {"hijri_month": 8, "hijri_day": 3, "title": "Milad of Imam Husain AS"},
    {"hijri_month": 8, "hijri_day": 4, "title": "Milad of Abul Fadl al-Abbas AS"},
    {"hijri_month": 8, "hijri_day": 5, "title": "Milad of Imam Ali Zain al-Abidin AS"},
    {"hijri_month": 8, "hijri_day": 15, "title": "Shab-e-Bara'at"},

    # --- Ramadaan al-Moazzam (9) ---
    {"hijri_month": 9, "hijri_day": 16, "title": "Washek Raat"},
    {"hijri_month": 9, "hijri_day": 17, "title": "Anniversary of the Battle of Badr"},
    {"hijri_month": 9, "hijri_day": 18, "title": "Washek Raat"},
    {"hijri_month": 9, "hijri_day": 19, "title": "Attack on Maulana Ali AS"},
    {"hijri_month": 9, "hijri_day": 20, "title": "Washek Raat"},
    {"hijri_month": 9, "hijri_day": 21, "title": "Shahadat of Maulana Ali AS"},
    {"hijri_month": 9, "hijri_day": 22, "title": "Lailat al-Qadr"},

    # --- Zilhaj al-Haraam (12) ---
    {"hijri_month": 12, "hijri_day": 1, "title": "Nikah of Maulana Ali AS and Maulatena Fatema az-Zahra AS"},
    {"hijri_month": 12, "hijri_day": 7, "title": "Shahadat of Imam Muhammad al-Baqir AS"},
    {"hijri_month": 12, "hijri_day": 8, "title": "Commencement of the Hajj pilgrimage"},
    {"hijri_month": 12, "hijri_day": 9, "title": "Day of Arafah", "is_fasting_day": True},
]

# Urs/wafat (misaq) events, transcribed directly from the user-supplied
# reference app screenshots (month-by-month "LIST" view), covering all
# 12 Hijri months. Source: user's own reference calendar, not fabricated.
URS_EVENTS = [
    # --- Moharram al-Haraam (1) ---
    {"hijri_month": 1, "hijri_day": 1, "title": "Maulai Abdullah RA - Khambat"},
    {"hijri_month": 1, "hijri_day": 2, "title": "Maulai Raj bin Maulai Hasan AQ - Ahmedabad"},
    {"hijri_month": 1, "hijri_day": 2, "title": "Syedi Khanji Fir Saheb AQ - Udaipur"},
    {"hijri_month": 1, "hijri_day": 7, "title": "Syedna Ismail Badruddin RA (38) - Jamnagar"},
    {"hijri_month": 1, "hijri_day": 10, "title": "Maulai Ahmed RA (obs. on 16th) - Khambat"},
    {"hijri_month": 1, "hijri_day": 10, "title": "Syedna Zoeb bin Moosa RA (1) - Huas (Yemen)"},
    {"hijri_month": 1, "hijri_day": 14, "title": "Maulai Lookmanji Mulla Alibhai AQ - Wankaner"},
    {"hijri_month": 1, "hijri_day": 15, "title": "Maulai Nooruddin AQ (obs. on 11 Jamdil-ula) - Dongaon"},
    {"hijri_month": 1, "hijri_day": 16, "title": "Syedna Hatim Mohiuddin RA (3) - Hutaib"},
    {"hijri_month": 1, "hijri_day": 17, "title": "Maulai Masood bin Maulai Suleman AQ - Dhrangdhra"},
    {"hijri_month": 1, "hijri_day": 17, "title": "Syedna Ibrahim Vajihuddin RA (39) - Ujjain"},
    {"hijri_month": 1, "hijri_day": 18, "title": "Syedi Gani Pir bin Dawoodji Shaheed AQ - Kalavad"},
    {"hijri_month": 1, "hijri_day": 23, "title": "Fatema Bibi ukhte Syedna Yusuf Najmuddin (24) AQ - Dandigam (Maisaheba)"},
    {"hijri_month": 1, "hijri_day": 23, "title": "Noor Bibi umme Syedna Yusuf Najmuddin (24) AQ - Dandigam (Maisaheba)"},
    {"hijri_month": 1, "hijri_day": 23, "title": "Syedi Hasan Fir Shaheed AQ - Denmal"},
    {"hijri_month": 1, "hijri_day": 27, "title": "Syedi Fakhruddin Shaheed AQ - Galiakot"},
    {"hijri_month": 1, "hijri_day": 28, "title": "Syedi Moosanji bin Taj AQ - Baroda"},
    {"hijri_month": 1, "hijri_day": 29, "title": "Maulai Hasan bin Maulai Adam AQ - Ahmedabad"},

    # --- Saffar al-Muzaffar (2) ---
    {"hijri_month": 2, "hijri_day": 1, "title": "Syedna Ali bin Syedna Hussain RA (10) - Sanaa, Yemen"},
    {"hijri_month": 2, "hijri_day": 3, "title": "Syedna Ali Shamsuddin RA (18) - Shariqa, Yemen"},
    {"hijri_month": 2, "hijri_day": 4, "title": "Syedna Abdultaiyeb Zakiyuddin RA (41) - Burhanpur"},
    {"hijri_month": 2, "hijri_day": 6, "title": "Syedi Abdeali Imaduddin bin Shk Jivabhai AQ - Surat"},
    {"hijri_month": 2, "hijri_day": 8, "title": "Syedna Khattab bin Hasan al-Hamadani RA - Yemen"},
    {"hijri_month": 2, "hijri_day": 9, "title": "Syedi Taiyeb Bhaisaheb Zainuddin AQ - Surat"},
    {"hijri_month": 2, "hijri_day": 12, "title": "Syedi Ahmed Hamiduddin AQ - Cairo"},
    {"hijri_month": 2, "hijri_day": 13, "title": "Maulai Adam bin Sulaiman AQ - Ahmedabad"},
    {"hijri_month": 2, "hijri_day": 14, "title": "Kaka Akela and Kaki Akela AQ - Khambat"},
    {"hijri_month": 2, "hijri_day": 14, "title": "Maulai Nooh Saheb AQ - Selavi"},
    {"hijri_month": 2, "hijri_day": 15, "title": "Syedi Maulai Hamza Bhaisaheb AQ - Surat"},
    {"hijri_month": 2, "hijri_day": 17, "title": "Shk. Ibrahim, Shk. Abdullah Saheb Shaheed AQ - Chechat"},
    {"hijri_month": 2, "hijri_day": 17, "title": "Shk. Saheb bin Sulemanji AQ - Chechat"},
    {"hijri_month": 2, "hijri_day": 22, "title": "Syedna Hussain bin Syedna Ali RA (8) - Yemen"},
    {"hijri_month": 2, "hijri_day": 27, "title": "Syedna Mohammad Izzuddin RA (23) - Yemen"},

    # --- Rabi al-Awwal (3) ---
    {"hijri_month": 3, "hijri_day": 1, "title": "Syedi Shaikhadam Safiyuddin AQ - Jamnagar"},
    {"hijri_month": 3, "hijri_day": 2, "title": "Syedna Abdultaiyeb Zakiyuddin RA (29) - Ahmedabad"},
    {"hijri_month": 3, "hijri_day": 4, "title": "Syedi Habibullah bin M Adamjee bin Syedi Bawa Mulla Khan AQ - Ujjain"},
    {"hijri_month": 3, "hijri_day": 7, "title": "Syedi Abdeali Bhaisaheb Mohyuddin AQ - Surat"},
    {"hijri_month": 3, "hijri_day": 7, "title": "Syedi Shaikh Dawoodbhai AQ - Udaipur"},
    {"hijri_month": 3, "hijri_day": 10, "title": "Syedna Abdullah Badruddin RA (50) - Surat"},
    {"hijri_month": 3, "hijri_day": 12, "title": "Amtullah Aaisaheba Akilat Syedna Mohammad Burhanuddin AQ - London"},
    {"hijri_month": 3, "hijri_day": 12, "title": "Syedna Ali bin Hanzalah RA (6) - Yemen"},
    {"hijri_month": 3, "hijri_day": 14, "title": "Syedi Miyajee Mulla Taj Saheb AQ - Umreth"},
    {"hijri_month": 3, "hijri_day": 16, "title": "Syedna Mohammad Burhanuddin RA (52) - Mumbai"},
    {"hijri_month": 3, "hijri_day": 22, "title": "Maulai Dawood bin Raj AQ - Morbi"},
    {"hijri_month": 3, "hijri_day": 23, "title": "Maulai Raj Saheb AQ - Morbi"},
    {"hijri_month": 3, "hijri_day": 23, "title": "Syedi Kazikhan bin Ameenshah AQ - Halwad"},
    {"hijri_month": 3, "hijri_day": 25, "title": "Syedna Ali Shamsuddin bin Maulai Hasan RA (30) - Hisne Afida, Yemen"},
    {"hijri_month": 3, "hijri_day": 28, "title": "Mohammad bin Hasan AQ - Dhinoj"},

    # --- Rabi al-Aakhar (4) ---
    {"hijri_month": 4, "hijri_day": 5, "title": "Miyasaheb Motabhai bin Mulla Noorbhai AQ - Balasinor"},
    {"hijri_month": 4, "hijri_day": 5, "title": "Miyasaheb Taiyebji bin Shaikh Shamaskhan AQ - Balasinor"},
    {"hijri_month": 4, "hijri_day": 8, "title": "Syedi Maulai Raj bin Maulai Adam AQ - Jamnagar"},
    {"hijri_month": 4, "hijri_day": 10, "title": "Syedi Abdurrasool Shaheed AQ - Banswara"},
    {"hijri_month": 4, "hijri_day": 14, "title": "Syedi Ismailjee Shaheed AQ - Godhra"},
    {"hijri_month": 4, "hijri_day": 16, "title": "Syedna Jalal Shamsuddin RA (25) - Ahmedabad"},
    {"hijri_month": 4, "hijri_day": 22, "title": "Syedi Mulla Habibullah bin Shaikh Sultanali AQ - Bharooch"},
    {"hijri_month": 4, "hijri_day": 22, "title": "Syedna Abdemoosa Kalimuddin RA (36) - Jamnagar"},
    {"hijri_month": 4, "hijri_day": 27, "title": "Syedna Dawood bin Ajabshah Burhanuddin RA (26) - Ahmedabad"},
    {"hijri_month": 4, "hijri_day": 28, "title": "Kakaji Mulla Essabhai AQ - Pratabgarh"},

    # --- Jumada al-Ula (5) ---
    {"hijri_month": 5, "hijri_day": 1, "title": "Syedna Ahmed almukarram al-Sulahi RA - Yemen"},
    {"hijri_month": 5, "hijri_day": 3, "title": "Syedi Kazikhan bin Ali AQ - Sidhpur"},
    {"hijri_month": 5, "hijri_day": 8, "title": "Syedi Mulla Wahedbhai Saheb AQ - Surat"},
    {"hijri_month": 5, "hijri_day": 11, "title": "Maulai Nooruddin Saheb AQ (wafat 15 Moharram) - Dongam"},
    {"hijri_month": 5, "hijri_day": 15, "title": "Maulai Dawood bin Qazi Ahmed AQ - Ahmedabad"},
    {"hijri_month": 5, "hijri_day": 17, "title": "Syedi Dawood Bhaisaheb Shihabuddin AQ - Surat"},
    {"hijri_month": 5, "hijri_day": 21, "title": "Seth Chandabhai ibne Karimbhai AQ - Bombay"},
    {"hijri_month": 5, "hijri_day": 23, "title": "Mulla Jafferjee Jeevajee AQ - Amreli"},

    # --- Jumada al-Ukhra (6) ---
    {"hijri_month": 6, "hijri_day": 8, "title": "Syedi Luqmanji bin Mulla Habibullah AQ - Surat"},
    {"hijri_month": 6, "hijri_day": 12, "title": "Mulla Tayyeb Bawa bin Mulla Ibrahimji AQ - Renala"},
    {"hijri_month": 6, "hijri_day": 14, "title": "Ganj Shahoda AQ - Ahmedabad"},
    {"hijri_month": 6, "hijri_day": 15, "title": "Maulai Ali Bhai Shaheed AQ - Indor"},
    {"hijri_month": 6, "hijri_day": 15, "title": "Syedna Dawood Burhanuddin RA (27) - Ahmedabad"},
    {"hijri_month": 6, "hijri_day": 18, "title": "Maulai Burhanuddin bin Khoj AQ - Pesawara"},
    {"hijri_month": 6, "hijri_day": 18, "title": "Syedna Yusuf Najmuddin RA (42) - Surat"},
    {"hijri_month": 6, "hijri_day": 23, "title": "Syedna Ismail Badruddin RA (34) - Jamnagar"},
    {"hijri_month": 6, "hijri_day": 27, "title": "Syedna Lamak bin Malik Al Hamadi - Lahaab, Yemen"},
    {"hijri_month": 6, "hijri_day": 27, "title": "Syedna Qutub Khan Qutbuddin Shaheed RA (32) - Ahmedabad"},
    {"hijri_month": 6, "hijri_day": 28, "title": "Syedna Ahmed bin Mubarak RA (7) - Yemen"},
    {"hijri_month": 6, "hijri_day": 28, "title": "Syedna Yahya bin Lamak RA - Lahaab, Yemen"},
    {"hijri_month": 6, "hijri_day": 29, "title": "Bahen Saheb Ajab Boo binte Syedna Qutbuddin Shaheed RA - Ahmedabad"},
    {"hijri_month": 6, "hijri_day": 29, "title": "Syedna Kazi Nauman bin Mohammad RA - Egypt"},
    {"hijri_month": 6, "hijri_day": 29, "title": "Syedna Mohammad Badruddin RA (46) - Surat"},

    # --- Rajab al-Asab (7) ---
    {"hijri_month": 7, "hijri_day": 2, "title": "Bhaiji Bhai bin Qadibhai AQ - Karachi"},
    {"hijri_month": 7, "hijri_day": 4, "title": "Syedi Hasanji Badshah AQ - Ujjain"},
    {"hijri_month": 7, "hijri_day": 4, "title": "Syedna Nur Mohammad Nuruddin RA (37) - Mandvi"},
    {"hijri_month": 7, "hijri_day": 7, "title": "Syedna Shaikh Adam Safiuddin RA (28) - Ahmedabad"},
    {"hijri_month": 7, "hijri_day": 11, "title": "Maulai Raj bin Dawood Saheb AQ - Ahmedabad"},
    {"hijri_month": 7, "hijri_day": 12, "title": "Syedi Najamkhan bin Syedna Firkhan Shujauddin AQ - Aurangabad"},
    {"hijri_month": 7, "hijri_day": 14, "title": "Maulai Yaqoob Saheb AQ - Patan"},
    {"hijri_month": 7, "hijri_day": 14, "title": "Syedna Abdul Muttalib Najmuddin RA (14) - Zamaramar, Yemen"},
    {"hijri_month": 7, "hijri_day": 18, "title": "Syedna Ali Shamsuddin RA (13) - Zamarmar, Yemen"},
    {"hijri_month": 7, "hijri_day": 19, "title": "Syedna Abu Mohammad Taher Saifuddin RA (51) - Mumbai"},
    {"hijri_month": 7, "hijri_day": 24, "title": "Syedi Qamruddin Bhaisaheb AQ - Ujjain"},
    {"hijri_month": 7, "hijri_day": 26, "title": "Syedna Abdulqadir Najmuddin RA (47) - Ujjain"},
    {"hijri_month": 7, "hijri_day": 27, "title": "Aminji Shaheed AQ - Pardhari, Kalawar"},
    {"hijri_month": 7, "hijri_day": 29, "title": "Syedi Luqmanji bin Syedi Dawoodsaheb AQ - Udaipur"},

    # --- Shabaan al-Karim (8) ---
    {"hijri_month": 8, "hijri_day": 1, "title": "Syedna Hebatullah al Moayyed Fiddin RA (40) - Ujjain"},
    {"hijri_month": 8, "hijri_day": 15, "title": "Syedna Hasan Badruddin RA (20) - Masaar, Yemen"},
    {"hijri_month": 8, "hijri_day": 16, "title": "Syedna Ibrahim bin Hussain RA (2) - Ghail Bani Hamid, Yemen"},
    {"hijri_month": 8, "hijri_day": 19, "title": "Syedi Saleh Bhaisaheb Safiuddin AQ - Bombay"},
    {"hijri_month": 8, "hijri_day": 22, "title": "Maulatuna Hurratul Maleka Arva binte Ahmed AQ - Zi Jibla, Yemen"},
    {"hijri_month": 8, "hijri_day": 22, "title": "Syedi Shk. Fir bin Dawood Shaheed AQ - Ranpur"},
    {"hijri_month": 8, "hijri_day": 22, "title": "Syedi Shk. Valibhai AQ (wafat 2 Ramazan) - Malva, Parda"},
    {"hijri_month": 8, "hijri_day": 25, "title": "Syedi Shamaskhan bin Syedi Yusufji AQ - Surat"},
    {"hijri_month": 8, "hijri_day": 27, "title": "Syedna Ali bin Mohammad bin Valeed RA (5) - Haraaz, Yemen"},
    {"hijri_month": 8, "hijri_day": 29, "title": "Syedi Jeevanji bin Shaikh Dawoodbhai AQ - Burhanpur"},

    # --- Ramadaan al-Moazzam (9) ---
    {"hijri_month": 9, "hijri_day": 2, "title": "Syedi Shk. Valibhai bin Shk. Habibullah AQ - Malva, Parda"},
    {"hijri_month": 9, "hijri_day": 3, "title": "Syedi Taiyeb Bhaisaheb Zainuddin AQ - Surat"},
    {"hijri_month": 9, "hijri_day": 8, "title": "Syedi Fazel Bhaisaheb Qutbuddin AQ - Surat"},
    {"hijri_month": 9, "hijri_day": 9, "title": "Syedna Abdullah Fakhruddin RA (16) - Zamarmar, Yemen"},
    {"hijri_month": 9, "hijri_day": 16, "title": "Syedi Hebatullah Jamaluddin AQ - Jamnagar"},
    {"hijri_month": 9, "hijri_day": 19, "title": "Syedna Mohammad Izzuddin RA (44) - Surat"},

    # --- Shawwal al-Mukarram (10) ---
    {"hijri_month": 10, "hijri_day": 4, "title": "Shehzadi Sakina Bahensaheba AQ binte Syedna Taher Saifuddin RA - Bombay"},
    {"hijri_month": 10, "hijri_day": 4, "title": "Syedi Yusufji wa Syedi Taiyebji Shaheed AQ - Ahmedabad"},
    {"hijri_month": 10, "hijri_day": 5, "title": "Syedi Abdulqader Hakimuddin AQ (urs on 27th) - Burhanpur"},
    {"hijri_month": 10, "hijri_day": 6, "title": "Syedna Hasan Badruddin RA (17) - Zamarmar, Yemen"},
    {"hijri_month": 10, "hijri_day": 7, "title": "Syedna Mohammad bin Taher RA - Yemen"},
    {"hijri_month": 10, "hijri_day": 8, "title": "Syedna Abbas bin Syedna Mohammad RA (15) - Yemen"},
    {"hijri_month": 10, "hijri_day": 9, "title": "Syedna Qasimkhan Zainuddin RA (31) - Ahmedabad"},
    {"hijri_month": 10, "hijri_day": 10, "title": "Syedna Hebatullah Moayyed Fiddin al-Shirazi RA - Qahira"},
    {"hijri_month": 10, "hijri_day": 10, "title": "Syedna Hussain Husamuddin RA (21) - Masaar, Yemen"},
    {"hijri_month": 10, "hijri_day": 10, "title": "Syedna Ibrahim RA (11) - Hisne Afeda, Yemen"},
    {"hijri_month": 10, "hijri_day": 13, "title": "Syedi Aminji bin Jalal AQ - Ahmedabad"},
    {"hijri_month": 10, "hijri_day": 24, "title": "Shk. Qutub Bhai Sulaimanji AQ - Pune"},
    {"hijri_month": 10, "hijri_day": 25, "title": "Syedi Abdemoosa bin Syedna Badruddin AQ - Jamnagar"},
    {"hijri_month": 10, "hijri_day": 27, "title": "Miyasaheb Abdulali Shk. Abdulqadir AQ - Javrah"},
    {"hijri_month": 10, "hijri_day": 27, "title": "Syedi Abdulqadir Hakimuddin AQ - Burhanpur"},
    {"hijri_month": 10, "hijri_day": 29, "title": "Mulla Salehbhai ibne Najamkhan AQ - Ahmedabad"},
    {"hijri_month": 10, "hijri_day": 29, "title": "Syedi Bawa Mulla Khan Saheb AQ - Rampura"},
    {"hijri_month": 10, "hijri_day": 29, "title": "Syedi Qasimkhan b. Syedi Hamzabahai AQ - Surat"},

    # --- Zilqadah al-Haraam (11) ---
    {"hijri_month": 11, "hijri_day": 4, "title": "Aaisaheba Amatullah AQ, Aqilate Syedna Mohammad Burhanuddin AQ"},
    {"hijri_month": 11, "hijri_day": 7, "title": "Syedi Abdulqadir Hakimuddin AQ - Surat"},
    {"hijri_month": 11, "hijri_day": 8, "title": "Syedi Shaikhadam Safiuddin AQ - Kachh Mandvi"},
    {"hijri_month": 11, "hijri_day": 9, "title": "Syedna Feerkhan Shujauddin RA (33) - Ahmedabad"},
    {"hijri_month": 11, "hijri_day": 11, "title": "Syedi Hasanji bin Nooh Bharuchi AQ - Masaar, Yemen"},
    {"hijri_month": 11, "hijri_day": 11, "title": "Syedna Ali bin Mohammad Sulehi RA - Yemen"},
    {"hijri_month": 11, "hijri_day": 12, "title": "Syedna Abdeali Saifuddin RA (43) - Surat"},
    {"hijri_month": 11, "hijri_day": 12, "title": "Syedna Abdul Taiyeb Zakiyuddin RA (35) - Jamnagar"},
    {"hijri_month": 11, "hijri_day": 13, "title": "Syedna Ali bin Syedna Hussain RA (9) - Sanaa, Yemen"},
    {"hijri_month": 11, "hijri_day": 15, "title": "Rani Baisaheba binte Syedna Badruddin AQ - Mundra"},
    {"hijri_month": 11, "hijri_day": 15, "title": "Syedna Taiyeb Zainuddin RA (45) - Surat"},
    {"hijri_month": 11, "hijri_day": 19, "title": "Syedna Idris Imaduddin RA (19) - Shibam, Yemen"},
    {"hijri_month": 11, "hijri_day": 20, "title": "Syedi Mulla Valibhai Shaheed bin Syedi Jivanji AQ - Aurangabad"},
    {"hijri_month": 11, "hijri_day": 21, "title": "Syedna Ali Shamsuddin RA (22) - Masaar, Yemen"},
    {"hijri_month": 11, "hijri_day": 22, "title": "Syedi Shaikh Sadiqali AQ - Surat"},
    {"hijri_month": 11, "hijri_day": 25, "title": "Syedna Ali bin Syedna Hatim RA (4) - Yemen"},
    {"hijri_month": 11, "hijri_day": 27, "title": "Syedi Yusufkhan bin Syedi Shamskhan AQ - Shahjapur"},

    # --- Zilhaj al-Haraam (12) ---
    {"hijri_month": 12, "hijri_day": 1, "title": "Syedna Mohammad bin Hatim RA (12) - Hisne Afeda, Yemen"},
    {"hijri_month": 12, "hijri_day": 6, "title": "Syedi Khoj bin Malakshah AQ - Kapadvanj"},
    {"hijri_month": 12, "hijri_day": 13, "title": "Maulai Firoze bin Ismailji AQ - Ahmedabad"},
    {"hijri_month": 12, "hijri_day": 16, "title": "Syedi Ishaq Bhaisaheb Jamaluddin AQ - Mumbai"},
    {"hijri_month": 12, "hijri_day": 16, "title": "Syedna Yusuf Najmuddin bin Sulaiman RA (24) - Taiba, Yemen"},
    {"hijri_month": 12, "hijri_day": 27, "title": "Ganje Shohda AQ - Ahmednagar"},
    {"hijri_month": 12, "hijri_day": 27, "title": "Syedna Abdulhusain Husamuddin RA (48) - Ahmedabad"},
    {"hijri_month": 12, "hijri_day": 27, "title": "Syedna Mohammad Burhanuddin RA (49) - Surat"},
]

# Sunni events data
# NOTE: Shawwal's "any 6 voluntary fasting days" and Dhul-Qa'dah's "Hajj
# travel begins" are intentionally NOT included -- neither has a fixed
# hijri_day, same limitation as Al-Quds Day above (see note further down).
SUNNI_EVENTS = [
    # Muharram (1)
    {"hijri_month": 1, "hijri_day": 1, "title": "Islamic New Year", "is_holiday": True, "color": "green", "event_source": "sunni"},
    {"hijri_month": 1, "hijri_day": 9, "title": "Fasting of Ashura (9th)", "is_fasting_day": True, "color": "green", "event_source": "sunni"},
    {"hijri_month": 1, "hijri_day": 10, "title": "Day of Ashura", "is_fasting_day": True, "color": "green", "event_source": "sunni"},

    # Safar (2) -- no canonical festivals

    # Rabi al-Awwal (3)
    {"hijri_month": 3, "hijri_day": 12, "title": "Mawlid an-Nabi (Birth of the Prophet)", "is_holiday": False, "color": "green", "event_source": "sunni"},

    # Rabi al-Thani (4)
    {"hijri_month": 4, "hijri_day": 11, "title": "Giyarween Shareef (Sufi-Qadri observance, not standard Sunni practice)", "is_holiday": False, "color": "green", "event_source": "sunni"},

    # Jumada al-Awwal (5) -- no specific festivals
    # Jumada al-Thani (6) -- no specific festivals

    # Rajab (7)
    {"hijri_month": 7, "hijri_day": 27, "title": "Isra and Mi'raj (Night Journey and Ascension)", "is_holiday": False, "color": "green", "event_source": "sunni"},

    # Sha'ban (8)
    {"hijri_month": 8, "hijri_day": 15, "title": "Laylat al-Bara'ah (Night of Forgiveness)", "is_holiday": False, "color": "green", "event_source": "sunni"},

    # Ramadan (9)
    {"hijri_month": 9, "hijri_day": 1, "title": "Ramadan begins", "is_fasting_day": True, "color": "green", "event_source": "sunni"},
    {"hijri_month": 9, "hijri_day": 21, "title": "Possible Laylat al-Qadr (odd night, last 10)", "is_holiday": False, "color": "green", "event_source": "sunni"},
    {"hijri_month": 9, "hijri_day": 23, "title": "Possible Laylat al-Qadr (odd night, last 10)", "is_holiday": False, "color": "green", "event_source": "sunni"},
    {"hijri_month": 9, "hijri_day": 25, "title": "Possible Laylat al-Qadr (odd night, last 10)", "is_holiday": False, "color": "green", "event_source": "sunni"},
    {"hijri_month": 9, "hijri_day": 27, "title": "Possible Laylat al-Qadr (odd night, last 10)", "is_holiday": False, "color": "green", "event_source": "sunni"},
    {"hijri_month": 9, "hijri_day": 29, "title": "Possible Laylat al-Qadr (odd night, last 10)", "is_holiday": False, "color": "green", "event_source": "sunni"},

    # Shawwal (10)
    {"hijri_month": 10, "hijri_day": 1, "title": "Eid al-Fitr", "is_holiday": True, "color": "green", "event_source": "sunni"},

    # Dhul-Qi'dah (11) -- no fixed-day festivals

    # Dhul-Hijjah (12)
    {"hijri_month": 12, "hijri_day": 1, "title": "Nine Blessed Days begin", "is_holiday": False, "color": "green", "event_source": "sunni"},
    {"hijri_month": 12, "hijri_day": 2, "title": "Nine Blessed Days", "is_holiday": False, "color": "green", "event_source": "sunni"},
    {"hijri_month": 12, "hijri_day": 3, "title": "Nine Blessed Days", "is_holiday": False, "color": "green", "event_source": "sunni"},
    {"hijri_month": 12, "hijri_day": 4, "title": "Nine Blessed Days", "is_holiday": False, "color": "green", "event_source": "sunni"},
    {"hijri_month": 12, "hijri_day": 5, "title": "Nine Blessed Days", "is_holiday": False, "color": "green", "event_source": "sunni"},
    {"hijri_month": 12, "hijri_day": 6, "title": "Nine Blessed Days", "is_holiday": False, "color": "green", "event_source": "sunni"},
    {"hijri_month": 12, "hijri_day": 7, "title": "Nine Blessed Days", "is_holiday": False, "color": "green", "event_source": "sunni"},
    {"hijri_month": 12, "hijri_day": 8, "title": "Nine Blessed Days", "is_holiday": False, "color": "green", "event_source": "sunni"},
    {"hijri_month": 12, "hijri_day": 9, "title": "Day of Arafah", "is_fasting_day": True, "color": "green", "event_source": "sunni"},
    {"hijri_month": 12, "hijri_day": 10, "title": "Eid al-Adha", "is_holiday": True, "color": "green", "event_source": "sunni"},
    {"hijri_month": 12, "hijri_day": 11, "title": "Days of Tashreeq (fasting prohibited)", "is_holiday": False, "color": "green", "event_source": "sunni"},
    {"hijri_month": 12, "hijri_day": 12, "title": "Days of Tashreeq (fasting prohibited)", "is_holiday": False, "color": "green", "event_source": "sunni"},
    {"hijri_month": 12, "hijri_day": 13, "title": "Days of Tashreeq (fasting prohibited)", "is_holiday": False, "color": "green", "event_source": "sunni"},
]

# NOTE: "International Al-Quds Day" (last Friday of Ramadan) is intentionally
# NOT included -- it's a floating weekday rule, not a fixed hijri_day, and this
# table has no way to express "last Friday of month X". Would need to be
# computed at render time from the grid function, not stored as a row here.
SHIA_EVENTS = [
    # Muharram (1)
    {"hijri_month": 1, "hijri_day": 1, "title": "Islamic New Year", "is_holiday": True, "color": "purple", "event_source": "shia"},
    {"hijri_month": 1, "hijri_day": 2, "title": "Arrival of Imam Hussain in Karbala", "is_holiday": False, "color": "purple", "event_source": "shia"},
    {"hijri_month": 1, "hijri_day": 7, "title": "Water supply blocked to Imam Hussain's camp", "is_holiday": False, "color": "purple", "event_source": "shia"},
    {"hijri_month": 1, "hijri_day": 9, "title": "Tasu'a (Eve of Ashura)", "is_holiday": False, "color": "purple", "event_source": "shia"},
    {"hijri_month": 1, "hijri_day": 10, "title": "Ashura (Martyrdom of Imam Husayn)", "is_holiday": True, "color": "purple", "event_source": "shia"},
    {"hijri_month": 1, "hijri_day": 11, "title": "Captivity and movement of the Ahl al-Bayt caravan", "is_holiday": False, "color": "purple", "event_source": "shia"},
    {"hijri_month": 1, "hijri_day": 25, "title": "Martyrdom of Imam Ali Zain-ul-Abideen", "is_holiday": False, "color": "purple", "event_source": "shia"},

    # Safar (2)
    {"hijri_month": 2, "hijri_day": 1, "title": "Entry of captives into Damascus", "is_holiday": False, "color": "purple", "event_source": "shia"},
    {"hijri_month": 2, "hijri_day": 7, "title": "Birth of Imam Musa al-Kadhim / Martyrdom narration of Imam Hasan", "is_holiday": False, "color": "purple", "event_source": "shia"},
    {"hijri_month": 2, "hijri_day": 17, "title": "Martyrdom of Imam Ali al-Ridha", "is_holiday": False, "color": "purple", "event_source": "shia"},
    {"hijri_month": 2, "hijri_day": 20, "title": "Arba'een (40th day after Ashura)", "is_holiday": True, "color": "purple", "event_source": "shia"},
    {"hijri_month": 2, "hijri_day": 28, "title": "Martyrdom of Prophet Muhammad and Imam Hasan", "is_holiday": False, "color": "purple", "event_source": "shia"},

    # Rabi al-Awwal (3)
    {"hijri_month": 3, "hijri_day": 8, "title": "Martyrdom of Imam Hasan al-Askari", "is_holiday": False, "color": "purple", "event_source": "shia"},
    {"hijri_month": 3, "hijri_day": 9, "title": "Eid-e-Zehra (Beginning of Imam Mahdi's imamate)", "is_holiday": False, "color": "purple", "event_source": "shia"},
    {"hijri_month": 3, "hijri_day": 17, "title": "Birth of Prophet Muhammad and Imam Ja'far al-Sadiq", "is_holiday": False, "color": "purple", "event_source": "shia"},

    # Rabi al-Thani (4)
    {"hijri_month": 4, "hijri_day": 8, "title": "Birth of Imam Hasan al-Askari", "is_holiday": False, "color": "purple", "event_source": "shia"},
    {"hijri_month": 4, "hijri_day": 10, "title": "Demise of Fatima Masumeh of Qom", "is_holiday": False, "color": "purple", "event_source": "shia"},

    # Jumada al-Awwal (5)
    {"hijri_month": 5, "hijri_day": 5, "title": "Birth of Sayyidah Zainab", "is_holiday": False, "color": "purple", "event_source": "shia"},
    {"hijri_month": 5, "hijri_day": 13, "title": "First narration of the martyrdom of Sayyidah Fatimah (start of Fatimiyyah)", "is_holiday": False, "color": "purple", "event_source": "shia"},

    # Jumada al-Thani (6)
    {"hijri_month": 6, "hijri_day": 3, "title": "Main narration of the martyrdom of Sayyidah Fatimah", "is_holiday": False, "color": "purple", "event_source": "shia"},
    {"hijri_month": 6, "hijri_day": 20, "title": "Birth of Sayyidah Fatimah", "is_holiday": False, "color": "purple", "event_source": "shia"},

    # Rajab (7)
    {"hijri_month": 7, "hijri_day": 1, "title": "Birth of Imam Muhammad al-Baqir", "is_holiday": False, "color": "purple", "event_source": "shia"},
    {"hijri_month": 7, "hijri_day": 3, "title": "Martyrdom of Imam Ali al-Hadi", "is_holiday": False, "color": "purple", "event_source": "shia"},
    {"hijri_month": 7, "hijri_day": 10, "title": "Birth of Imam Muhammad al-Jawad", "is_holiday": False, "color": "purple", "event_source": "shia"},
    {"hijri_month": 7, "hijri_day": 13, "title": "Birth of Imam Ali ibn Abi Talib", "is_holiday": False, "color": "purple", "event_source": "shia"},
    {"hijri_month": 7, "hijri_day": 15, "title": "Demise of Sayyidah Zainab", "is_holiday": False, "color": "purple", "event_source": "shia"},
    {"hijri_month": 7, "hijri_day": 25, "title": "Martyrdom of Imam Musa al-Kadhim", "is_holiday": False, "color": "purple", "event_source": "shia"},
    {"hijri_month": 7, "hijri_day": 27, "title": "Mab'ath (Declaration of Prophethood)", "is_holiday": False, "color": "purple", "event_source": "shia"},

    # Shaban (8)
    {"hijri_month": 8, "hijri_day": 3, "title": "Birth of Imam Hussain", "is_holiday": False, "color": "purple", "event_source": "shia"},
    {"hijri_month": 8, "hijri_day": 4, "title": "Birth of Hazrat Abbas", "is_holiday": False, "color": "purple", "event_source": "shia"},
    {"hijri_month": 8, "hijri_day": 5, "title": "Birth of Imam Ali Zain-ul-Abideen", "is_holiday": False, "color": "purple", "event_source": "shia"},
    {"hijri_month": 8, "hijri_day": 11, "title": "Birth of Ali Akbar", "is_holiday": False, "color": "purple", "event_source": "shia"},
    {"hijri_month": 8, "hijri_day": 15, "title": "Birth of Imam Muhammad al-Mahdi", "is_holiday": False, "color": "purple", "event_source": "shia"},

    # Ramadan (9)
    {"hijri_month": 9, "hijri_day": 1, "title": "Ramadan begins", "is_fasting_day": True, "color": "purple", "event_source": "shia"},
    {"hijri_month": 9, "hijri_day": 10, "title": "Demise of Lady Khadijah", "is_holiday": False, "color": "purple", "event_source": "shia"},
    {"hijri_month": 9, "hijri_day": 15, "title": "Birth of Imam Hasan ibn Ali", "is_holiday": False, "color": "purple", "event_source": "shia"},
    {"hijri_month": 9, "hijri_day": 18, "title": "First Night of Qadr / Attack on Imam Ali", "is_holiday": False, "color": "purple", "event_source": "shia"},
    {"hijri_month": 9, "hijri_day": 19, "title": "Wounding of Imam Ali in the mosque of Kufa", "is_holiday": False, "color": "purple", "event_source": "shia"},
    {"hijri_month": 9, "hijri_day": 21, "title": "Martyrdom of Imam Ali ibn Abi Talib", "is_holiday": True, "color": "purple", "event_source": "shia"},
    {"hijri_month": 9, "hijri_day": 23, "title": "Greatest estimated Night of Qadr", "is_holiday": False, "color": "purple", "event_source": "shia"},

    # Shawwal (10)
    {"hijri_month": 10, "hijri_day": 1, "title": "Eid al-Fitr", "is_holiday": True, "color": "purple", "event_source": "shia"},
    {"hijri_month": 10, "hijri_day": 8, "title": "Youm al-Hadm (Destruction of Jannat al-Baqi shrines)", "is_holiday": False, "color": "purple", "event_source": "shia"},
    {"hijri_month": 10, "hijri_day": 25, "title": "Martyrdom of Imam Ja'far al-Sadiq", "is_holiday": False, "color": "purple", "event_source": "shia"},

    # Dhu al-Qi'dah (11)
    {"hijri_month": 11, "hijri_day": 1, "title": "Birth of Sayyidah Fatimah Masumeh", "is_holiday": False, "color": "purple", "event_source": "shia"},
    {"hijri_month": 11, "hijri_day": 11, "title": "Birth of Imam Ali al-Ridha", "is_holiday": False, "color": "purple", "event_source": "shia"},
    {"hijri_month": 11, "hijri_day": 23, "title": "Martyrdom commemoration of Imam Ali al-Ridha", "is_holiday": False, "color": "purple", "event_source": "shia"},
    {"hijri_month": 11, "hijri_day": 25, "title": "Dahw al-Ardh (Rolling of the Earth)", "is_holiday": False, "color": "purple", "event_source": "shia"},
    {"hijri_month": 11, "hijri_day": 29, "title": "Martyrdom of Imam Muhammad al-Jawad", "is_holiday": False, "color": "purple", "event_source": "shia"},

    # Dhu al-Hijjah (12)
    {"hijri_month": 12, "hijri_day": 1, "title": "Marriage of Imam Ali and Sayyidah Fatimah", "is_holiday": False, "color": "purple", "event_source": "shia"},
    {"hijri_month": 12, "hijri_day": 7, "title": "Martyrdom of Imam Muhammad al-Baqir", "is_holiday": False, "color": "purple", "event_source": "shia"},
    {"hijri_month": 12, "hijri_day": 8, "title": "Tarwiyya Day / Imam Hussain departs Mecca", "is_holiday": False, "color": "purple", "event_source": "shia"},
    {"hijri_month": 12, "hijri_day": 9, "title": "Day of Arafah / Martyrdom of Muslim ibn Aqil", "is_holiday": False, "color": "purple", "event_source": "shia"},
    {"hijri_month": 12, "hijri_day": 10, "title": "Eid al-Adha (Festival of Sacrifice)", "is_holiday": True, "color": "purple", "event_source": "shia"},
    {"hijri_month": 12, "hijri_day": 15, "title": "Birth of Imam Ali al-Hadi", "is_holiday": False, "color": "purple", "event_source": "shia"},
    {"hijri_month": 12, "hijri_day": 18, "title": "Eid al-Ghadir (Appointment of Imam Ali)", "is_holiday": True, "color": "purple", "event_source": "shia"},
    {"hijri_month": 12, "hijri_day": 24, "title": "Day of Mubahala", "is_holiday": False, "color": "purple", "event_source": "shia"},
    {"hijri_month": 12, "hijri_day": 25, "title": "Revelation of Surah Al-Insan (Hal Ata)", "is_holiday": False, "color": "purple", "event_source": "shia"},
]

SEED_EVENTS = EID_AND_FASTING_EVENTS + MAJOR_OBSERVANCES + URS_EVENTS


def refresh_interfaith_events(start_year: int, end_year: int):
    """Regenerate InterfaithEvent rows for [start_year, end_year] inclusive.
    Safe to call repeatedly (e.g. on every app startup) -- it wipes and
    rebuilds just that year range so edits to interfaith_calendar.py take
    effect on next restart without manual DB migration."""
    from . import interfaith_calendar as ic

    db = SessionLocal()
    try:
        db.query(InterfaithEvent).filter(
            InterfaithEvent.event_date >= f"{start_year}-01-01",
            InterfaithEvent.event_date <= f"{end_year}-12-31",
        ).delete(synchronize_session=False)
        for year in range(start_year, end_year + 1):
            for e in ic.get_interfaith_events(year):
                db.add(InterfaithEvent(
                    event_date=e["date"], title=e["title"],
                    tradition=e["tradition"], is_holiday=e.get("is_holiday", False),
                    color=e.get("color", "black"),
                ))
        db.commit()
    finally:
        db.close()


def seed_if_empty():
    db = SessionLocal()
    try:
        if db.query(HijriEvent).count() == 0:
            for e in SEED_EVENTS:
                db.add(HijriEvent(**e))
            db.commit()
    finally:
        db.close()


def seed_missing_sources():
    """seed_if_empty() only ever fires once, on a table with zero rows total
    -- if Bohra events were seeded before Sunni/Shia events existed in this
    file (as happened here), the table is no longer empty and those two
    sources never get added, forever. This seeds any event_source
    (bohra/sunni/shia) that currently has zero rows, independently of the
    other sources' row counts, so it's safe to call on every startup and
    won't duplicate rows or touch your existing custom events."""
    db = SessionLocal()
    try:
        for source, events in (("bohra", SEED_EVENTS), ("sunni", SUNNI_EVENTS), ("shia", SHIA_EVENTS)):
            if not events:
                continue
            count = db.query(HijriEvent).filter(HijriEvent.event_source == source).count()
            if count == 0:
                for e in events:
                    data = dict(e)
                    data.setdefault("event_source", source)
                    db.add(HijriEvent(**data))
        db.commit()
    finally:
        db.close()


def refresh_seeded_events(sources=("sunni", "shia")):
    """Same pattern as refresh_interfaith_events(): wipe and rebuild the
    non-custom rows for the given event_source(s) on every startup, so
    editing SUNNI_EVENTS / SHIA_EVENTS in this file takes effect on next
    restart without a manual DB script.

    Only deletes rows with is_custom == False -- anything a user added
    themselves through the UI (is_custom == True) is never touched.

    Deliberately does NOT default to including "bohra": Bohra events are
    routinely hand-edited/added to by users through the events.html UI,
    and while is_custom protects those specifically, there's no reason to
    add churn to that source's seed rows on every deploy. Pass sources
    explicitly (e.g. refresh_seeded_events(("bohra","sunni","shia"))) if
    you want Bohra's seed list refreshed too.
    """
    source_map = {"bohra": SEED_EVENTS, "sunni": SUNNI_EVENTS, "shia": SHIA_EVENTS}
    db = SessionLocal()
    try:
        for source in sources:
            events = source_map.get(source)
            if not events:
                continue
            db.query(HijriEvent).filter(
                HijriEvent.event_source == source,
                HijriEvent.is_custom == False,
            ).delete(synchronize_session=False)
            for e in events:
                data = dict(e)
                data.setdefault("event_source", source)
                db.add(HijriEvent(**data))
        db.commit()
    finally:
        db.close()
