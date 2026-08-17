"""
Run this ONCE, then restart the app so seed_missing_sources() re-fires
(it only inserts when count == 0 for that event_source).

Only deletes non-custom shia rows -- if you or anyone has manually added
a custom Shia event via the UI (is_custom=True), it's left alone.
"""
from database import SessionLocal, HijriEvent

db = SessionLocal()
try:
    deleted = (
        db.query(HijriEvent)
        .filter(HijriEvent.event_source == "shia", HijriEvent.is_custom == False)
        .delete(synchronize_session=False)
    )
    db.commit()
    print(f"Deleted {deleted} stale shia rows. Restart the app now.")
finally:
    db.close()
