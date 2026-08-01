"""
Christian liturgical calendar helpers -- liturgical season/color, and a
small curated Saint of the Day dataset.

LITURGICAL SEASON [likely] -- standard Western (Roman) liturgical calendar,
computed off the same Meeus/Jones/Butcher Easter algorithm already used in
interfaith_calendar.py (verified there against known 2024-2027 Easter
dates). Season boundaries used here:

  Advent         4th Sunday before Dec 25 (i.e. the Sunday on/before Dec 24,
                 minus 3 weeks) through Dec 24.
  Christmas      Dec 25 through Jan 13 (approximated as a FIXED date rather
                 than the real rule, "the Sunday after Epiphany" -- that
                 real rule can land anywhere Jan 7-13, so this is
                 [likely close, not exact] in most years).
  Lent           Ash Wednesday (46 days before Easter) through the day
                 before Easter.
  Easter         Easter Sunday through the day before Pentecost.
  Pentecost      Pentecost Sunday itself only.
  Ordinary Time  everything else.

This is a simplification of the real calendar in one deliberate way: Holy
Week (Palm Sunday through Holy Saturday) is liturgically red/purple in
places, not uniformly "Lent purple" -- not modelled here. Good enough for
"what color should the app lean today", not for actual liturgical planning.

SAINT OF THE DAY [guessing -- curated subset, not authoritative]: ~50
well-known fixed-date feasts from the General Roman Calendar. A missing
date means "not in this small list", not "no feast exists that day".
Verify against a proper source (e.g. a Martyrologium or Universalis-style
calendar) before treating this as complete or authoritative.
"""

from datetime import date, timedelta


def _easter(year: int) -> date:
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


SEASON_COLORS = {
    "Advent":        {"color_name": "Purple",     "color_hex": "#5b3a8e"},
    "Christmas":     {"color_name": "White/Gold",  "color_hex": "#c9a227"},
    "Lent":          {"color_name": "Purple",     "color_hex": "#5b3a8e"},
    "Easter":        {"color_name": "White/Gold",  "color_hex": "#c9a227"},
    "Pentecost":     {"color_name": "Red",        "color_hex": "#b5121b"},
    "Ordinary Time": {"color_name": "Green",      "color_hex": "#2e8b57"},
}


def liturgical_season(g: date) -> dict:
    """Return {'season', 'color_name', 'color_hex'} for a Gregorian date.
    [likely] -- see module docstring for boundary caveats."""
    year = g.year
    easter = _easter(year)
    ash_wednesday = easter - timedelta(days=46)
    pentecost = easter + timedelta(days=49)
    christmas = date(year, 12, 25)
    baptism_of_lord = date(year, 1, 13)

    d = date(year, 12, 24)
    while d.weekday() != 6:  # walk back to the Sunday on/before Dec 24
        d -= timedelta(days=1)
    advent_start = d - timedelta(weeks=3)

    if date(year, 1, 1) <= g <= baptism_of_lord:
        season = "Christmas"
    elif ash_wednesday <= g < easter:
        season = "Lent"
    elif g == pentecost:
        season = "Pentecost"
    elif easter <= g < pentecost:
        season = "Easter"
    elif advent_start <= g < christmas:
        season = "Advent"
    elif g >= christmas:
        season = "Christmas"
    else:
        season = "Ordinary Time"

    c = SEASON_COLORS[season]
    return {"season": season, "color_name": c["color_name"], "color_hex": c["color_hex"]}


# (month, day) -> {"name", "title", "prayer"}. See module docstring --
# curated subset, fixed dates only (no moveable feasts, no per-country
# calendars). "prayer" lines below are short original invocations written
# for this app, not quotations from any liturgical text.
SAINTS = {
    (1, 1):   {"name": "Mary, Mother of God",  "title": "Solemnity",        "prayer": "Mary, Mother of God, help us begin this year rooted in grace."},
    (1, 25):  {"name": "St. Paul",             "title": "Conversion of St. Paul", "prayer": "St. Paul, whose road to Damascus changed everything, turn our hearts toward truth."},
    (2, 3):   {"name": "St. Blaise",           "title": "Bishop and Martyr", "prayer": "St. Blaise, protector of the sick, watch over those who suffer today."},
    (2, 14):  {"name": "St. Valentine",        "title": "Priest and Martyr", "prayer": "St. Valentine, patron of love freely given, guard the bonds we cherish."},
    (2, 22):  {"name": "Chair of St. Peter",   "title": "Feast",            "prayer": "On the Chair of Peter, we ask for unity and steadfast faith."},
    (3, 17):  {"name": "St. Patrick",          "title": "Bishop",           "prayer": "St. Patrick, who carried faith to unfamiliar shores, give us that same courage."},
    (3, 19):  {"name": "St. Joseph",           "title": "Spouse of Mary",   "prayer": "St. Joseph, quiet and faithful worker, teach us steadiness in hard seasons."},
    (3, 25):  {"name": "The Annunciation",     "title": "Solemnity",        "prayer": "At the Annunciation, we ask for the courage to say yes to what is asked of us."},
    (4, 23):  {"name": "St. George",           "title": "Martyr",           "prayer": "St. George, patron of courage, strengthen us to stand for what is right."},
    (4, 25):  {"name": "St. Mark",             "title": "Evangelist",       "prayer": "St. Mark, who wrote so plainly of the Gospel, help us live it as simply."},
    (5, 1):   {"name": "St. Joseph the Worker","title": "Feast",            "prayer": "St. Joseph the Worker, bless the labor of our hands today."},
    (5, 3):   {"name": "Sts. Philip and James","title": "Apostles",         "prayer": "Sts. Philip and James, who asked to see clearly, help us seek clarity too."},
    (5, 14):  {"name": "St. Matthias",         "title": "Apostle",          "prayer": "St. Matthias, chosen to complete the Twelve, remind us that every calling matters."},
    (5, 26):  {"name": "St. Philip Neri",      "title": "Priest",           "prayer": "St. Philip Neri, joyful in faith, keep our hearts light and generous."},
    (6, 11):  {"name": "St. Barnabas",         "title": "Apostle",          "prayer": "St. Barnabas, son of encouragement, help us build others up today."},
    (6, 13):  {"name": "St. Anthony of Padua", "title": "Priest and Doctor","prayer": "St. Anthony, finder of what is lost, help us recover what matters most."},
    (6, 24):  {"name": "St. John the Baptist", "title": "Nativity",         "prayer": "St. John the Baptist, voice in the wilderness, help us prepare the way."},
    (6, 29):  {"name": "Sts. Peter and Paul",  "title": "Apostles",         "prayer": "Sts. Peter and Paul, pillars of the early Church, ground us in that same faith."},
    (7, 3):   {"name": "St. Thomas",           "title": "Apostle",          "prayer": "St. Thomas, honest in doubt, meet us in our own uncertainty."},
    (7, 11):  {"name": "St. Benedict",         "title": "Abbot",            "prayer": "St. Benedict, patron of order and prayer, bring quiet discipline to our day."},
    (7, 22):  {"name": "St. Mary Magdalene",   "title": "Apostle to the Apostles", "prayer": "St. Mary Magdalene, first witness of the Resurrection, keep our hope alive."},
    (7, 25):  {"name": "St. James",            "title": "Apostle",          "prayer": "St. James, who left his nets to follow, help us answer our own call."},
    (7, 26):  {"name": "Sts. Joachim and Anne","title": "Parents of Mary",  "prayer": "Sts. Joachim and Anne, watch over families and grandparents today."},
    (8, 6):   {"name": "The Transfiguration",  "title": "Feast",            "prayer": "In the Transfiguration's light, help us glimpse what is holy in the everyday."},
    (8, 10):  {"name": "St. Lawrence",         "title": "Deacon and Martyr","prayer": "St. Lawrence, generous even in trial, teach us to give without counting the cost."},
    (8, 15):  {"name": "The Assumption of Mary","title": "Solemnity",       "prayer": "Mary, taken up in glory, keep watch over those we love."},
    (8, 20):  {"name": "St. Bernard",          "title": "Abbot and Doctor", "prayer": "St. Bernard, eloquent in devotion, help us speak of faith with warmth."},
    (8, 24):  {"name": "St. Bartholomew",      "title": "Apostle",          "prayer": "St. Bartholomew, called with no guile, keep our intentions honest."},
    (8, 28):  {"name": "St. Augustine",        "title": "Bishop and Doctor","prayer": "St. Augustine, restless until you found peace, guide our own searching hearts."},
    (9, 8):   {"name": "The Nativity of Mary", "title": "Feast",            "prayer": "On Mary's birthday, we give thanks for every quiet beginning."},
    (9, 14):  {"name": "The Exaltation of the Holy Cross", "title": "Feast","prayer": "At the Cross, help us find meaning in what we carry."},
    (9, 21):  {"name": "St. Matthew",          "title": "Apostle and Evangelist", "prayer": "St. Matthew, called from the tax booth, remind us no one is beyond a fresh start."},
    (9, 29):  {"name": "Sts. Michael, Gabriel & Raphael", "title": "Archangels", "prayer": "Archangels Michael, Gabriel, and Raphael, guard, guide, and heal us today."},
    (9, 30):  {"name": "St. Jerome",           "title": "Priest and Doctor","prayer": "St. Jerome, devoted to Scripture, help us return to it often."},
    (10, 1):  {"name": "St. Therese of Lisieux","title": "Doctor of the Church", "prayer": "St. Therese, who found greatness in small things, teach us her 'little way'."},
    (10, 4):  {"name": "St. Francis of Assisi","title": "Religious",        "prayer": "St. Francis, brother to all creation, help us live simply and gently."},
    (10, 15): {"name": "St. Teresa of Avila",  "title": "Doctor of the Church", "prayer": "St. Teresa of Avila, bold in prayer, deepen our own quiet conversations with God."},
    (10, 18): {"name": "St. Luke",             "title": "Evangelist",       "prayer": "St. Luke, physician and storyteller, help us notice the overlooked."},
    (10, 28): {"name": "Sts. Simon and Jude",  "title": "Apostles",         "prayer": "Sts. Simon and Jude, patrons of difficult causes, stay with us in hard moments."},
    (11, 1):  {"name": "All Saints",           "title": "Solemnity",        "prayer": "All you saints, known and unknown, pray for us and for those we've lost."},
    (11, 2):  {"name": "All Souls",            "title": "Commemoration",    "prayer": "We remember today all who have gone before us in faith."},
    (11, 4):  {"name": "St. Charles Borromeo", "title": "Bishop",           "prayer": "St. Charles Borromeo, reformer and shepherd, help leaders serve with humility."},
    (11, 11): {"name": "St. Martin of Tours",  "title": "Bishop",           "prayer": "St. Martin, who shared his cloak with a stranger, make us that generous."},
    (11, 22): {"name": "St. Cecilia",          "title": "Martyr, patron of music", "prayer": "St. Cecilia, patron of musicians, let today carry a little more harmony."},
    (11, 30): {"name": "St. Andrew",           "title": "Apostle",          "prayer": "St. Andrew, first called, help us bring others gently toward what we've found good."},
    (12, 3):  {"name": "St. Francis Xavier",   "title": "Priest, Missionary","prayer": "St. Francis Xavier, tireless traveler, give us energy for what's still ahead of us."},
    (12, 6):  {"name": "St. Nicholas",         "title": "Bishop",           "prayer": "St. Nicholas, quiet giver, remind us that generosity doesn't need an audience."},
    (12, 8):  {"name": "The Immaculate Conception", "title": "Solemnity",   "prayer": "Mary, conceived without sin, help us believe that grace can reach anyone."},
    (12, 13): {"name": "St. Lucy",             "title": "Virgin and Martyr","prayer": "St. Lucy, patron of light, help us hold onto hope in the darker days."},
    (12, 26): {"name": "St. Stephen",          "title": "First Martyr",     "prayer": "St. Stephen, first to give everything, steady our own courage."},
    (12, 27): {"name": "St. John the Evangelist", "title": "Apostle",       "prayer": "St. John, beloved disciple, help us love as plainly as you wrote of it."},
    (12, 28): {"name": "The Holy Innocents",   "title": "Martyrs",          "prayer": "We remember today the most vulnerable, and pray for their protection."},
    (12, 31): {"name": "St. Sylvester",        "title": "Pope",             "prayer": "St. Sylvester, as this year closes, we give thanks for what it held."},
}


def saint_of_day(month: int, day: int):
    """Return this app's saint-of-the-day entry for (month, day), or None
    if that date isn't in the curated list. [guessing] -- see module
    docstring."""
    return SAINTS.get((month, day))
