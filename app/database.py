"""SQLite storage for Bohra calendar events (misaqs, urs, eids, etc.)."""

from datetime import datetime

from sqlalchemy import create_engine, Column, Integer, String, Boolean, Date, DateTime, Text
from sqlalchemy.orm import declarative_base, sessionmaker

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


class Note(Base):
    """A single freeform sticky-note, shown in the sidebar on every page --
    not a list of discrete to-do rows, one blob of HTML the user typed
    directly into a contenteditable box (bold + bullet lists only, from
    the two toolbar buttons in base.html). Always id=1: there's no login
    on this app, so it's one shared note for the whole deployment, same
    as the old version's list was shared. content is sanitized server-side
    before it's ever written here -- see sanitize_note_html() in main.py --
    so what's in this column is safe to render with |safe."""
    __tablename__ = "notes"

    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text, default="")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


def get_or_create_note(db):
    """The one sticky-note row (id=1), creating it on first use."""
    n = db.query(Note).get(1)
    if not n:
        n = Note(id=1, content="")
        db.add(n)
        db.commit()
        db.refresh(n)
    return n


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
SUNNI_EVENTS = [
    {"hijri_month": 1, "hijri_day": 1, "title": "Islamic New Year", "is_holiday": True, "color": "green", "event_source": "sunni"},
    {"hijri_month": 1, "hijri_day": 10, "title": "Day of Ashura", "is_fasting_day": True, "color": "green", "event_source": "sunni"},
    {"hijri_month": 9, "hijri_day": 1, "title": "Ramadan begins", "is_fasting_day": True, "color": "green", "event_source": "sunni"},
    {"hijri_month": 10, "hijri_day": 1, "title": "Eid al-Fitr", "is_holiday": True, "color": "green", "event_source": "sunni"},
    {"hijri_month": 12, "hijri_day": 9, "title": "Day of Arafah", "is_fasting_day": True, "color": "green", "event_source": "sunni"},
    {"hijri_month": 12, "hijri_day": 10, "title": "Eid al-Adha", "is_holiday": True, "color": "green", "event_source": "sunni"},
]

SHIA_EVENTS = [
    {"hijri_month": 1, "hijri_day": 1, "title": "Islamic New Year", "is_holiday": True, "color": "purple", "event_source": "shia"},
    {"hijri_month": 1, "hijri_day": 9, "title": "Tasu'a", "is_holiday": False, "color": "purple", "event_source": "shia"},
    {"hijri_month": 1, "hijri_day": 10, "title": "Ashura", "is_holiday": True, "color": "purple", "event_source": "shia"},
    {"hijri_month": 9, "hijri_day": 1, "title": "Ramadan begins", "is_fasting_day": True, "color": "purple", "event_source": "shia"},
    {"hijri_month": 10, "hijri_day": 1, "title": "Eid al-Fitr", "is_holiday": True, "color": "purple", "event_source": "shia"},
    {"hijri_month": 12, "hijri_day": 10, "title": "Eid al-Adha", "is_holiday": True, "color": "purple", "event_source": "shia"},
    {"hijri_month": 12, "hijri_day": 18, "title": "Eid al-Ghadeer", "is_holiday": True, "color": "purple", "event_source": "shia"},
]

SEED_EVENTS = EID_AND_FASTING_EVENTS + URS_EVENTS


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
