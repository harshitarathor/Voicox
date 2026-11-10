"""Spoken question (as text) -> StructuredQuery, using fixed keyword rules.

No model and no API key. Returns None when nothing in the question is understood.
The validator still checks everything this file returns.
"""
import difflib
import re
import unicodedata
from typing import Optional

from backend.config import ALIASES, PRODUCTS
from backend.schemas import StructuredQuery


# ---------------------------------------------------------------- text cleanup
def _basic(s: str) -> str:
    return unicodedata.normalize("NFC", s).lower().replace("\u093c", "")   # drop nukta


_PUNCT = re.compile(r"[?!.,;:।|\"'()\[\]{}\-–—/\\*]")

# spelling variants -> one standard spelling
_WORD_FIX = {
    "pichhle": "pichle", "pichhla": "pichle", "pichla": "pichle",
    "iss": "is",
    "jyada": "zyada", "zyaada": "zyada", "jyaada": "zyada", "zyda": "zyada", "jyda": "zyada",
    "kyu": "kyun", "kyon": "kyun", "kyoon": "kyun",
    "kaaran": "karan",
    "hafta": "hafte", "haftey": "hafte", "mahina": "mahine", "mahiney": "mahine",
    "bikta": "bika", "bikte": "bika", "bike": "bika", "bikne": "bika",
    "biki": "bika", "bikti": "bika",
    "bikka": "bika", "bikkaa": "bika", "bikaa": "bika", "bikkaye": "bika",   # how Prisma spells it
}


_TIME_WORDS = ("mahine", "hafte", "din", "saal")
_NOT_PICHLE = {"this", "last", "next", "past", "agle", "agla", "pehle", "pehla", "iss", "aaj",
               "pure", "poore", "sabhi", "kitne", "kitna", "kitni", "kuch"}


def _fix_pichle(words: list) -> list:
    """Speech-to-text sometimes writes 'pichle' as 'pikal'. Only a mis-heard word that
    sits right before mahine/hafte/din/saal is turned back into 'pichle'."""
    out = list(words)
    for i in range(len(out) - 1):
        w = out[i]
        if (out[i + 1] in _TIME_WORDS and len(w) >= 4 and w.isascii() and w.isalpha()
                and w not in _NOT_PICHLE and w != "pichle"
                and difflib.SequenceMatcher(None, w, "pichle").ratio() >= 0.5):
            out[i] = "pichle"
    return out


def normalize(text: str) -> str:
    t = _PUNCT.sub(" ", _basic(text))
    return " ".join(_fix_pichle([_WORD_FIX.get(w, w) for w in t.split()]))


def _has(t: str, *phrases: str) -> bool:
    padded = f" {t} "
    return any(f" {_basic(p)} " in padded for p in phrases)


# ---------------------------------------------------------------- word lists
# "Mera chawal kahan gaya?" is a gap question, and the owner is asking why, so these count as both.
GONE = ("kahan gaya", "kahan gayi", "kahan gaye", "kam nikla", "kam nikli", "kam nikle", "kam ho gaya", "kam ho gayi",
        "kam ho gaye", "कहाँ गया", "कहां गया", "कहाँ गई", "कहां गई", "कहाँ गए", "कहां गए", "कम निकला", "कम हो गया")
WHY = ("kyun", "wajah", "karan", "reason", "why", "क्यों", "क्यूं", "कारण", "वजह", *GONE)
GAP = ("mismatch", "gap", "gadbad", "discrepancy", "farak", "chori", "ghata", "ghate",
       "missing", "gayab", "gaayab", "nuksan", "loss", "match nahi", "mel nahi",
       "मिसमैच", "गैप", "गड़बड़", "गायब", "फर्क", "चोरी",
       "match karta", "match kar raha", "match hota", "match karte", "mel khata", "मैच", "मेल खाता",
       *GONE)
# Questions the shop data cannot answer (there is no cost price): refuse instead of giving a wrong number.
UNSUPPORTED = ("profit", "margin", "munafa", "munaafa", "nafa", "nafaa", "labh", "fayda", "faayda",
               "cost price", "मुनाफा", "मुनाफ़ा", "नफा", "लाभ", "फायदा", "मार्जिन", "प्रॉफिट")
# Advice questions ("How to increase the sales of my shop?"): the records can show what happened, not what to do.
ADVICE = ("how to", "how can i", "how do i", "how should i", "what should i do", "tips", "tip", "suggest", "suggestion",
          "advice", "idea", "ideas", "strategy", "badhane", "badhana", "badhau", "badhaun", "badhaye", "badhayein",
          "badhaen", "tarike", "tareeke", "upay", "salah", "sujhav", "kya karu", "kya karun", "kya karna chahiye",
          "बढ़ाने", "बढ़ाना", "बढ़ाऊं", "बढ़ाएं", "तरीके", "सलाह", "सुझाव", "उपाय", "क्या करूं")
def is_advice(text: str) -> bool:
    return _has(normalize(text), *ADVICE)
# Things the records cannot answer: the future, customers, staff, market prices.
OUTSCOPE = ("next month", "next week", "next year", "agle mahine", "agle hafte", "agle saal", "aane wale", "predict",
            "forecast", "prediction", "kab tak",
            "customer", "customers", "grahak", "gaahak", "ग्राहक", "udhar", "udhaar", "उधार",
            "employee", "employees", "staff", "worker", "workers", "naukar", "supplier", "suppliers", "vendor",
            "salary", "tankhwah", "bhav", "bhaav", "भाव", "daam", "दाम", "price", "prices", "keemat", "kimat",
            "कीमत", "rate", "mandi", "market", "मंडी", "discount", "discounts", "gst", "tax", "rent", "bijli")


def _why_sales(t: str) -> bool:
    """'Why are my sales low?': the records can explain a stock gap, not why sales rose or fell."""
    return _has(t, *WHY) and _has(t, *SALES) and not (_has(t, *GAP) or _has(t, *STOCK))


_MONTHS = ("january", "february", "march", "april", "june", "july", "august", "september", "october",
           "november", "december", "jan", "feb", "aug", "sept", "sep", "oct", "nov", "dec")
YEARWORDS = ("saal", "sal", "year", "years", "varsh", "quarter", "साल", "वर्ष", "2023", "2024", "2025", "2026", "2027")


def _bad_period(t: str) -> bool:
    """A period the app does not compute (a year, a named month, a quarter): say so, never use 30 days instead."""
    return _has(t, *YEARWORDS) or _has(t, *_MONTHS)


_NOT_A_PRODUCT = set("""total kul poori puri sab sabhi saari sara all overall each every any my our your the a an
 meri mera mere hamari hamara apni apna dukaan dukan shop store aaj kal parso is iss pichle pichhle agle last this next
 previous today yesterday daily weekly monthly roz rozana hafte hafta mahine mahina din week month days day
 stock sales sale revenue bikri kamai gap mismatch kitna kitni kitne kya kaun kaunsa product products item items
 saman samaan maal low most least top best
 mein me ko ka ki ke se par pe hai hain tha thi hua hui hue ne aur ya bhi to kab kahan kaise batao bata batana dikhao
 dikha do dena show tell give get see you we they are was were did does have has had how much many much with and for
 from into over about our ours""".split()) | set(_MONTHS)
_KNOWN_WORDS = {_basic(w) for name, val in list(globals().items())
                if name.isupper() and isinstance(val, tuple) for w in val if isinstance(w, str)}
_HN_ASK = re.compile(r"(?:^| )([a-z]{3,}) (?:ki|ka|ke|mein) (?:bikri|sales|stock|revenue|kamai|gap|mismatch|bika)\b")
_EN_ASK = re.compile(r"\b(?:sales|sale|stock|revenue|gap|sold|sell) (?:of|for) (?:the |my |our )?([a-z]{3,})\b")
_KITNA = re.compile(r"(?:^| )(?:kitna ([a-z]{3,}) bika|([a-z]{3,}) kitna bika)\b|\bhow (?:much|many) ([a-z]{3,}) "
                    r"(?:did we |have we |were )?(?:sold|sell)\b|\bwhy is ([a-z]{3,}) short\b")


def _unknown_product(t: str):
    """The product-looking word in 'Maggi ki bikri kitni hui' when it is not one of the shop's products."""
    padded = f" {t} "
    if any(f" {a} " in padded for a in _ALIAS_NAMES) or _find_product(t):
        return None                                  # a real product, or a near-miss the validator will confirm
    for rx in (_HN_ASK, _EN_ASK, _KITNA):
        for m in rx.finditer(t):
            w = next((g for g in m.groups() if g), None)
            if w and w not in _NOT_A_PRODUCT and w not in _KNOWN_WORDS and w.isalpha():
                return w
    return None


def refusal(text: str):
    """(message key, argument) when the app must decline instead of guessing, else None."""
    t = normalize(text)
    if _has(t, *ADVICE):
        return "m_advice", None
    if _has(t, *OUTSCOPE) or _why_sales(t):
        return "m_scope", None
    if _bad_period(t):
        return "m_period", None
    w = _unknown_product(t)
    if w:
        return "m_unknown_product", w.capitalize()
    return None


def is_out_of_scope(text: str) -> bool:
    t = normalize(text)
    return _has(t, *OUTSCOPE) or _why_sales(t)


STOCK = ("stock", "स्टॉक", "स्टोक")
LOW = ("kam", "low", "khatam", "khatm", "bacha", "finish", "कम", "खत्म")
ITEMS = ("saman", "samaan", "samān", "maal", "item", "items", "सामान", "माल")          # "Kaun sa saman kam bach gaya"
LEFT = ("bach", "bacha", "bache", "bachi", "बचा", "बचे", "बची")
REORDER = ("reorder", "restock", "order", "mangwana", "mangwani", "mangwao",
           "kharidna", "khareedna", "ऑर्डर")
WASTAGE = ("kharab", "kharaab", "damage", "damaged", "wastage", "waste", "toot", "tuta",
           "expire", "expired", "barbad", "खराब", "बर्बाद")
COMPARE = ("compare", "comparison", "tulna", "muqabla", "mukabla", "mukable",
           "versus", "vs", "तुलना")
TREND = ("trend", "daily", "roz", "rozana", "har din", "din wise", "dinwise",
         "din ke hisaab", "din ke hisab")
RANK_DESC = ("sabse zyada", "top", "best", "most", "highest", "bestseller",
             "sabse achha", "sabse accha", "सबसे ज्यादा", "टॉप")
RANK_ASC = ("sabse kam", "kam bika", "slow", "dheere", "least", "lowest", "worst",
            "nahi bika", "सबसे कम")
SALES = ("bikri", "sales", "revenue", "kamai", "income", "amdani", "turnover", "bika",
         "sold", "sell", "becha", "bechi", "total", "kitna", "kitni", "kitne", "paisa", "paise", "rupaye",
         "बिक्री", "कमाई", "कितना", "कितनी", "कितने", "बिका", "बिकी", "बिके")
QTY_EXPLICIT = ("unit", "units", "quantity", "kilo", "kg", "packet", "packets",
                "piece", "pieces", "maatra", "matra", "यूनिट", "किलो", "पैकेट")
REV_WORDS = ("revenue", "kamai", "income", "amdani", "turnover", "sales", "bikri",
             "paisa", "paise", "rupaye", "rupee", "rupees", "rs", "₹", "बिक्री", "कमाई")
SOLD_WORDS = ("bika", "sold", "sell", "becha", "bechi", "बिका", "बिकी", "बिके")
CATEGORY_WORD = ("category", "categories", "shreni", "श्रेणी")

_PERIODS = [
    ("last_month",   ("pichle mahine", "last month", "पिछले महीने")),
    ("this_month",   ("is mahine", "this month", "इस महीने")),
    ("last_week",    ("pichle hafte", "last week", "पिछले हफ्ते")),
    ("this_week",    ("is hafte", "this week", "इस हफ्ते")),
    ("last_30_days", ("pichle 30 din", "last 30 days", "30 din", "30 days")),
    ("yesterday",    ("kal", "yesterday", "कल")),
    ("today",        ("aaj", "today", "आज")),
    ("all",          ("ab tak", "all time", "overall", "shuru se", "अब तक")),
]

_ALIASES = sorted(((_basic(a), p) for p, names in ALIASES.items() for a in names),
                  key=lambda x: -len(x[0]))
_ALIAS_NAMES = [a for a, _ in _ALIASES]
_CATEGORIES = {details[0].lower(): details[0] for details in PRODUCTS.values()}


# ---------------------------------------------------------------- finders
def _find_product(t: str) -> Optional[str]:
    padded = f" {t} "
    best = None
    for alias, product in _ALIASES:
        i = padded.find(f" {alias} ")
        if i != -1 and (best is None or i < best[0]):
            best = (i, product)
    if best:
        return best[1]
    # Not an exact alias: pass a near-match word on as typed. The validator will
    # ask "Kya aap Chawal keh rahe hain?" before anything runs.
    for tok in t.split():
        if len(tok) >= 4 and tok.isascii() and tok.isalpha():
            if difflib.get_close_matches(tok, _ALIAS_NAMES, n=1, cutoff=0.8):
                return tok
    return None


def _find_periods(t: str) -> list:
    """Named periods in the order they were spoken."""
    padded = f" {t} "
    found = {}
    for code, phrases in _PERIODS:
        for p in phrases:
            i = padded.find(f" {_basic(p)} ")
            if i != -1 and (code not in found or i < found[code]):
                found[code] = i
    return [code for code, _ in sorted(found.items(), key=lambda kv: kv[1])]


def _find_category(t: str) -> Optional[str]:
    for tok in t.split():
        if tok in _CATEGORIES:
            return _CATEGORIES[tok]
    return None


# Numbers as speech-to-text writes them: digits, English words or Hindi words (Roman).
NUMBER_WORDS = {
    "ek": 1, "one": 1, "do": 2, "two": 2, "teen": 3, "three": 3, "char": 4, "chaar": 4, "four": 4,
    "paanch": 5, "panch": 5, "five": 5, "chhe": 6, "che": 6, "chhah": 6, "six": 6,
    "saat": 7, "sat": 7, "seven": 7, "aath": 8, "eight": 8, "nau": 9, "nine": 9,
    "das": 10, "dus": 10, "ten": 10,
}
_NUM = r"(\d{1,3}|" + "|".join(sorted(NUMBER_WORDS, key=len, reverse=True)) + r")"


def _to_int(tok: str) -> int:
    return int(tok) if tok.isdigit() else NUMBER_WORDS[tok]


def _find_limit(t: str) -> int:
    t = re.sub(r"\b(?:pichle )?30 (?:din|days)\b", " ", t)
    m = (re.search(r"\b(?:top|first|pehle)\s+" + _NUM + r"\b", t)
         or re.search(r"\b" + _NUM + r"\s+(?:products?|items?|cheez\w*|saman)\b", t))
    return max(1, min(_to_int(m.group(1)), 20)) if m else None      # None: no number was said


_DAY_SPAN = re.compile(r"\b(?:pichle|last|past)\s+" + _NUM + r"\s+(?:din|days?)\b")


def _unsupported_day_span(t: str) -> bool:
    """'Pichle 7 din' has no matching period here (only 30 days, weeks and months do)."""
    m = _DAY_SPAN.search(t)
    return bool(m) and _to_int(m.group(1)) != 30


PLURAL = ("products", "items", "cheezein", "cheezen", "chizein", "kaunse", "प्रोडक्ट्स")
SINGULAR_ASK = ("sabse zyada", "sabse kam", "which", "kaunsa", "kaun sa", "कौनसा", "कौन सा",
                "सबसे ज्यादा", "सबसे ज़्यादा", "सबसे कम")


def _limit_for(t: str, default: int = 5) -> int:
    """A number said aloud wins. 'Sabse zyada kya bika?' (one, not plural) means 1."""
    said = _find_limit(t)
    if said:
        return said
    if _has(t, *SINGULAR_ASK) and not _has(t, *PLURAL):
        return 1
    return default


def _metric(t: str) -> str:
    if _has(t, *QTY_EXPLICIT):
        return "quantity"
    if _has(t, *REV_WORDS):
        return "revenue"
    if _has(t, *SOLD_WORDS):
        return "quantity"
    return "revenue"


# ---------------------------------------------------------------- main entry
def keyword_extract(text: str) -> Optional[StructuredQuery]:
    t = normalize(text)
    if not t:
        return None
    if _has(t, *UNSUPPORTED) or refusal(text):
        return None

    product = _find_product(t)
    periods = _find_periods(t)
    category = None if product else _find_category(t)
    asc, desc = _has(t, *RANK_ASC), _has(t, *RANK_DESC)
    ranked = asc or desc
    has_gap = _has(t, *GAP)

    if _has(t, *WHY) and (has_gap or product or _has(t, *STOCK)):
        intent = "explain_gap"
    elif has_gap:
        intent = "stock_gap"
    elif (_has(t, *STOCK) and _has(t, *LOW)) or _has(t, *REORDER):
        intent = "low_stock"
    elif not ranked and _has(t, *ITEMS) and _has(t, "kam", "कम") and _has(t, *LEFT):
        intent = "low_stock"            # "Kaun sa saman kam bach gaya hai"
    elif product and not ranked and (_has(t, *STOCK) or _has(t, "bacha", "bachi", "bache")):
        intent = "low_stock"            # "Daal ka stock kitna hai", "Chawal kitna bacha hai"
    elif _has(t, *WASTAGE):
        intent = "wastage"
    elif _has(t, *COMPARE) or (len(periods) >= 2 and not ranked):
        intent = "compare"
    elif _has(t, *TREND):
        intent = "trend"
    elif ranked:
        intent = "ranked"
    elif _has(t, *SALES):
        intent = "total"
    else:
        return None

    data = {"intent": intent, "product": product, "confidence": 0.9}

    if intent == "explain_gap" and product is None:
        data["confidence"] = 0.4            # asks "Kya aapka matlab yahi sawaal hai?"

    if intent in ("total", "ranked", "trend", "compare"):
        data["metric"] = _metric(t)
        data["category"] = category
        data["period"] = periods[0] if periods else "last_30_days"
        if not periods and _unsupported_day_span(t):
            data["confidence"] = 0.5            # asks first, instead of silently using 30 days

    if intent == "compare" and len(periods) >= 2:
        data["compare_period"] = periods[1]     # one period only -> validator asks for the other

    if intent == "ranked":
        data["order"] = "asc" if asc else "desc"
        data["limit"] = _limit_for(t)
        if category is None and _has(t, *CATEGORY_WORD):
            data["group_by"] = "category"

    if intent == "wastage":
        data["period"] = periods[0] if periods else "all"
        data["limit"] = _limit_for(t)

    return StructuredQuery(**data)


def extract(text: str) -> Optional[StructuredQuery]:
    """The function the API calls. The Gemini layer will be added here later,
    with keyword_extract as the fallback."""
    return keyword_extract(text)