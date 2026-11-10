"""Every sentence Voicox says, in three languages.

  hn  Hinglish (Hindi in Roman letters)   - the default, and what the first version said
  en  proper English
  hi  proper Hindi in Devanagari

Numbers are never worked out here. The functions only put numbers that engine.py and
insights.py already computed into sentences. `to_voice` makes a second copy of a
sentence for the speaker (Gnani Timbre), because what reads well on screen is not
always what is pronounced well.
"""
import re
from datetime import date

LANGS = ("en", "hi", "hn")


def norm(lang) -> str:
    return lang if lang in LANGS else "hn"


# ---------------------------------------------------------------- names
NAME = {
    "hn": {},   # Hinglish keeps the names as stored: Chawal, Doodh ...
    "en": {"Chawal": "Rice", "Atta": "Flour", "Tel": "Oil", "Cheeni": "Sugar", "Daal": "Lentils",
           "Doodh": "Milk", "Dahi": "Curd", "Biscuit": "Biscuits", "Namkeen": "Savoury snacks",
           "Sabun": "Soap", "Grocery": "Grocery", "Dairy": "Dairy", "Snacks": "Snacks", "Home": "Home"},
    "hi": {"Chawal": "चावल", "Atta": "आटा", "Tel": "तेल", "Cheeni": "चीनी", "Daal": "दाल",
           "Doodh": "दूध", "Dahi": "दही", "Biscuit": "बिस्कुट", "Namkeen": "नमकीन", "Sabun": "साबुन",
           "Grocery": "किराना", "Dairy": "डेयरी", "Snacks": "स्नैक्स", "Home": "घरेलू सामान"},
}
_CATEGORIES = ("Grocery", "Dairy", "Snacks", "Home")
DEVANAGARI = {k: v for k, v in NAME["hi"].items() if k not in _CATEGORIES}   # products only


def nm(lang: str, label) -> str:
    """A product or category name in the answer's language."""
    label = str(label)
    return NAME[norm(lang)].get(label, label)


# ---------------------------------------------------------------- numbers and dates
_HI_0_99 = (
    "शून्य एक दो तीन चार पाँच छह सात आठ नौ दस ग्यारह बारह तेरह चौदह पंद्रह सोलह सत्रह अठारह उन्नीस "
    "बीस इक्कीस बाईस तेईस चौबीस पच्चीस छब्बीस सत्ताईस अट्ठाईस उनतीस तीस इकतीस बत्तीस तैंतीस चौंतीस "
    "पैंतीस छत्तीस सैंतीस अड़तीस उनतालीस चालीस इकतालीस बयालीस तैंतालीस चौवालीस पैंतालीस छियालीस "
    "सैंतालीस अड़तालीस उनचास पचास इक्यावन बावन तिरपन चौवन पचपन छप्पन सत्तावन अट्ठावन उनसठ साठ "
    "इकसठ बासठ तिरसठ चौंसठ पैंसठ छियासठ सड़सठ अड़सठ उनहत्तर सत्तर इकहत्तर बहत्तर तिहत्तर चौहत्तर "
    "पचहत्तर छिहत्तर सतहत्तर अठहत्तर उन्यासी अस्सी इक्यासी बयासी तिरासी चौरासी पचासी छियासी सत्तासी "
    "अट्ठासी नवासी नब्बे इक्यानवे बानवे तिरानवे चौरानवे पंचानवे छियानवे सत्तानवे अट्ठानवे निन्यानवे"
).split()
assert len(_HI_0_99) == 100

_MONTH_HI = ("जनवरी फ़रवरी मार्च अप्रैल मई जून जुलाई अगस्त सितंबर अक्टूबर नवंबर दिसंबर").split()

_UNITS = {"hn": (("crore", "crore"), ("lakh", "lakh"), ("hazaar", "hazaar")),
          "en": (("crore", "crore"), ("lakh", "lakh"), ("thousand", "thousand")),
          "hi": (("करोड़", "करोड़"), ("लाख", "लाख"), ("हज़ार", "हज़ार"))}


def say(n, lang="hn") -> str:
    """420000 -> '4 lakh 20 hazaar' / '4 lakh 20 thousand' / '4 लाख 20 हज़ार' (Indian grouping)."""
    lang = norm(lang)
    n = int(round(float(n)))
    if n < 0:
        return ("minus " if lang != "hi" else "ऋण ") + say(-n, lang)
    crore, n = divmod(n, 10_000_000)
    lakh, n = divmod(n, 100_000)
    thousand, n = divmod(n, 1000)
    names = _UNITS[lang]
    parts = [f"{v} {w[0]}" for v, w in zip((crore, lakh, thousand), names) if v]
    if n or not parts:
        parts.append(str(n))
    return " ".join(parts)


def amount(x, metric: str, lang="hn") -> str:
    lang = norm(lang)
    s = say(x, lang)
    one = int(round(float(x))) == 1
    if metric == "revenue":
        return f"{s} " + {"hn": "rupaye", "en": "rupee" if one else "rupees", "hi": "रुपये"}[lang]
    return f"{s} " + {"hn": "unit", "en": "unit" if one else "units", "hi": "यूनिट"}[lang]


def day_text(d, lang="hn", short=False) -> str:
    """31 October (short: 31 Oct); Hindi uses the Hindi month name."""
    d = d if isinstance(d, date) else date.fromisoformat(str(d)[:10])
    if norm(lang) == "hi":
        return f"{d.day} {_MONTH_HI[d.month - 1]}"
    return f"{d.day:02d} {d:%b}" if short else f"{d.day} {d:%B}"


# ---------------------------------------------------------------- periods
# ev: used before a verb ("Last month ..."); ki: used before a noun ("Last month's sales ...")
PERIOD = {
    "hn": {"today": ("Aaj", "Aaj ki"), "yesterday": ("Kal", "Kal ki"),
           "this_week": ("Is hafte", "Is hafte ki"), "last_week": ("Pichle hafte", "Pichle hafte ki"),
           "this_month": ("Is mahine", "Is mahine ki"), "last_month": ("Pichle mahine", "Pichle mahine ki"),
           "last_30_days": ("Pichle 30 din mein", "Pichle 30 din ki"), "all": ("Ab tak", "Ab tak ki")},
    "en": {"today": ("Today", "today"), "yesterday": ("Yesterday", "yesterday"),
           "this_week": ("This week", "this week"), "last_week": ("Last week", "last week"),
           "this_month": ("This month", "this month"), "last_month": ("Last month", "last month"),
           "last_30_days": ("In the last 30 days", "the last 30 days"), "all": ("So far", "all time")},
    "hi": {"today": ("आज", "आज की"), "yesterday": ("कल", "कल की"),
           "this_week": ("इस हफ्ते", "इस हफ्ते की"), "last_week": ("पिछले हफ्ते", "पिछले हफ्ते की"),
           "this_month": ("इस महीने", "इस महीने की"), "last_month": ("पिछले महीने", "पिछले महीने की"),
           "last_30_days": ("पिछले 30 दिनों में", "पिछले 30 दिनों की"), "all": ("अब तक", "अब तक की")},
}


def ev(lang, period) -> str:
    return PERIOD[norm(lang)][period][0]


def ki(lang, period) -> str:
    return PERIOD[norm(lang)][period][1]


# ---------------------------------------------------------------- sentences
# Each entry is a function; the three languages are kept side by side so a change in
# one is easy to match in the others.
def _plist(lang):
    """The shop's product names in the chosen language, for 'product not found' messages."""
    from backend.config import PRODUCTS
    return ", ".join(NAME[lang].get(p, p) for p in PRODUCTS)


S = {
    # ---- answers
    "no_data": {
        "hn": lambda ev, ki: f"{ev} ka koi sales data nahi mila.",
        "en": lambda ev, ki: f"No sales data was found for {ki}.",
        "hi": lambda ev, ki: f"{ev} के लिए कोई सेल्स डेटा नहीं मिला।"},
    "total_qty": {
        "hn": lambda ev, who, amt: f"{ev} {who or 'total'} {amt} bika.",
        "en": lambda ev, who, amt: f"{ev}, {amt} of {who} were sold." if who else f"{ev}, {amt} were sold in total.",
        "hi": lambda ev, who, amt: f"{ev} {who} की {amt} की बिक्री हुई।" if who else f"{ev} कुल {amt} की बिक्री हुई।"},
    "total_rev_who": {
        "hn": lambda ev, who, amt: f"{ev} {who} ki bikri {amt} rahi.",
        "en": lambda ev, who, amt: f"{ev}, sales of {who} were {amt}.",
        "hi": lambda ev, who, amt: f"{ev} {who} की बिक्री {amt} रही।"},
    "total_rev": {
        "hn": lambda ki, amt: f"{ki} total bikri {amt} rahi.",
        "en": lambda ki, amt: f"Total sales for {ki} were {amt}.",
        "hi": lambda ki, amt: f"{ki} कुल बिक्री {amt} रही।"},
    "rank_one_qty": {
        "hn": lambda ev, more, label, amt: f"{ev} sabse {'zyada' if more else 'kam'} {label} bika, {amt}.",
        "en": lambda ev, more, label, amt: f"{ev}, {label} sold the {'most' if more else 'least'}: {amt}.",
        "hi": lambda ev, more, label, amt: f"{ev} मात्रा में सबसे {'ज्यादा' if more else 'कम'} बिक्री {label} की रही: {amt}।"},
    "rank_one_rev": {
        "hn": lambda ev, more, label, amt: f"{ev} sabse {'zyada' if more else 'kam'} bikri {label} ki hui, {amt}.",
        "en": lambda ev, more, label, amt: f"{ev}, {label} had the {'highest' if more else 'lowest'} sales: {amt}.",
        "hi": lambda ev, more, label, amt: f"{ev} सबसे {'ज्यादा' if more else 'कम'} बिक्री {label} की हुई: {amt}।"},
    "rank_many": {
        "hn": lambda ev, more, n, items: f"{ev} sabse {'zyada' if more else 'kam'} bikne wale {n}: {items}.",
        "en": lambda ev, more, n, items: (f"{ev}, the top {n} sellers are: {items}." if more
                                           else f"{ev}, the {n} slowest sellers are: {items}."),
        "hi": lambda ev, more, n, items: f"{ev} सबसे {'ज्यादा' if more else 'कम'} बिकने वाले {n}: {items}।"},
    "trend": {
        "hn": lambda ki, amt, day: f"{ki} total {amt} raha. Sabse zyada {day} ko hua.",
        "en": lambda ki, amt, day: f"The total for {ki} was {amt}. The best day was {day}.",
        "hi": lambda ki, amt, day: f"{ki} कुल बिक्री {amt} रही। सबसे ज्यादा बिक्री {day} को हुई।"},
    "compare": {
        "hn": lambda A, va, B, vb, diff, pct, dirn: f"{A} {va} raha, {B[:1].lower() + B[1:]} {vb} tha. Yaani {diff}{pct} {dirn}.",
        "en": lambda A, va, B, vb, diff, pct, dirn: (
            f"{A}: {va}. {B}: {vb}. The two are about the same." if dirn == "same"
            else f"{A}: {va}. {B}: {vb}. That is {diff}{pct} {dirn} than {B[:1].lower() + B[1:]}."),
        "hi": lambda A, va, B, vb, diff, pct, dirn: f"{A} {va} रहा, {B} {vb} था। यानी {diff}{pct} {dirn}।"},
    "dir": {   # more / less / same
        "hn": {"more": "zyada", "less": "kam", "same": "barabar"},
        "en": {"more": "more", "less": "less", "same": "same"},
        "hi": {"more": "ज्यादा", "less": "कम", "same": "बराबर"}},
    "pct": {
        "hn": lambda p: f" ({p} percent)", "en": lambda p: f" ({p} percent)", "hi": lambda p: f" ({p} प्रतिशत)"},
    "low_empty": {
        "hn": "Koi item reorder level se neeche nahi hai.",
        "en": "No item is below its reorder level.",
        "hi": "कोई आइटम रीऑर्डर लेवल से नीचे नहीं है।"},
    "wastage_top": {
        "hn": lambda ev, label, n: f"{ev} sabse zyada kharab {label} hua: {n} unit.",
        "en": lambda ev, label, n: f"{ev}, {label} had the most damaged stock: {n} units.",
        "hi": lambda ev, label, n: f"{ev} सबसे ज्यादा खराबी {label} में रही: {n} यूनिट।"},
    "wastage_none": {
        "hn": "Koi kharab maal record nahi hua.",
        "en": "No damaged stock has been recorded.",
        "hi": "कोई खराब माल दर्ज नहीं हुआ।"},
    "gap_none_all": {
        "hn": "Sab items ka stock records se match kar raha hai.",
        "en": "All items match the records.",
        "hi": "सभी आइटम का स्टॉक रिकॉर्ड से मेल खाता है।"},
    "gap_none_one": {
        "hn": lambda p: f"{p} ka stock records se match karta hai.",
        "en": lambda p: f"The stock of {p} matches the records.",
        "hi": lambda p: f"{p} का स्टॉक रिकॉर्ड से मेल खाता है।"},
    # ---- alerts
    "alert_low": {
        "hn": lambda p, c, r: f"{p} ka stock kam hai: sirf {c} bacha hai, reorder level {r} hai.",
        "en": lambda p, c, r: f"The stock of {p} is low: only {c} left, and the reorder level is {r}.",
        "hi": lambda p, c, r: f"{p} का स्टॉक कम है: सिर्फ़ {c} बचा है, रीऑर्डर लेवल {r} है।"},
    "alert_short": {
        "hn": lambda p, gap, e, c: (f"{p} mein {gap} unit ka potential mismatch hai. "
                                    f"Records ke hisaab se {e} hona chahiye, ginti mein {c} mile."),
        "en": lambda p, gap, e, c: (f"{p} may be short by {gap} units. "
                                    f"The records say {e}, but the count found {c}."),
        "hi": lambda p, gap, e, c: (f"{p} में {gap} यूनिट का संभावित अंतर है। "
                                    f"रिकॉर्ड के हिसाब से {e} होना चाहिए, गिनती में {c} मिले।")},
    "alert_over": {
        "hn": lambda p, gap, e, c: (f"{p} mein records se {gap} unit zyada mile. "
                                    f"Records ke hisaab se {e} hona chahiye, ginti mein {c} mile."),
        "en": lambda p, gap, e, c: (f"{p} has {gap} more units than the records show. "
                                    f"The records say {e}, but the count found {c}."),
        "hi": lambda p, gap, e, c: (f"{p} में रिकॉर्ड से {gap} यूनिट ज्यादा मिले। "
                                    f"रिकॉर्ड के हिसाब से {e} होना चाहिए, गिनती में {c} मिले।")},
    "stock_ok": {
        "hn": lambda p, c, r: f"{p} ka stock theek hai: {c} bacha hai, reorder level {r} hai.",
        "en": lambda p, c, r: f"The stock of {p} is fine: {c} left, and the reorder level is {r}.",
        "hi": lambda p, c, r: f"{p} का स्टॉक ठीक है: {c} बचा है, रीऑर्डर लेवल {r} है।"},
    "alerts_more": {
        "hn": lambda n: f"Aur {n} items bhi hain, screen par dekhiye.",
        "en": lambda n: f"{n} more items are shown on the screen.",
        "hi": lambda n: f"{n} और आइटम स्क्रीन पर देखिए।"},
    # ---- "Why?"
    "why_none": {
        "hn": lambda p: f"{p} ka stock records se match karta hai, koi gap nahi hai.",
        "en": lambda p: f"The stock of {p} matches the records, so there is no gap.",
        "hi": lambda p: f"{p} का स्टॉक रिकॉर्ड से मेल खाता है, कोई अंतर नहीं है।"},
    "why_main": {
        "hn": lambda p, n, short, head, check, disc: (
            f"{p} mein {n} unit {'kam' if short else 'zyada'} hai. Sabse pehla sanket: {head}. "
            f"Agla kadam: {check} {disc}"),
        "en": lambda p, n, short, head, check, disc: (
            f"{p} is {n} units {'short' if short else 'over'}. The first clue: {head[:1].lower() + head[1:]}. "
            f"Next step: {check} {disc}"),
        "hi": lambda p, n, short, head, check, disc: (
            f"{p} में {n} यूनिट {'कम' if short else 'ज्यादा'} है। सबसे पहला संकेत: {head}। "
            f"अगला कदम: {check} {disc}")},
    "disclaimer": {
        "hn": "Yeh sirf sanket hain, nishkarsh nahi. Pehle records aur stock dobara check kijiye.",
        "en": "These are only clues, not conclusions. First check the records and count the stock again.",
        "hi": "ये सिर्फ़ संकेत हैं, निष्कर्ष नहीं। पहले रिकॉर्ड देखिए और स्टॉक दोबारा गिनिए।"},
    "r_nosales_whole": {
        "hn": lambda n, shown: f"{n} din ka sales record nahi hai ({shown})",
        "en": lambda n, shown: f"There is no sales record for {n} day{'s' if n != 1 else ''} ({shown})",
        "hi": lambda n, shown: f"{n} दिन का सेल्स रिकॉर्ड नहीं है ({shown})"},
    "r_nosales_one": {
        "hn": lambda n, p, shown: f"{n} din {p} ki bikri darj nahi hai ({shown})",
        "en": lambda n, p, shown: f"No sales of {p} are recorded on {n} day{'s' if n != 1 else ''} ({shown})",
        "hi": lambda n, p, shown: f"{n} दिन {p} की बिक्री दर्ज नहीं है ({shown})"},
    "r_nosales_detail": {
        "hn": lambda p, avg, est, need: (f"In dinon mein koi bikri darj nahi hai. Aam din mein {p} lagbhag "
                                         f"{avg} unit bikta hai, to kareeb {est} unit ka record chhut "
                                         f"sakta hai. Gap {need} unit ka hai."),
        "en": lambda p, avg, est, need: (f"No sales are recorded on those days. On a normal day about {avg} units "
                                         f"of {p} are sold, so around {est} units may be missing from the records. "
                                         f"The gap is {need} units."),
        "hi": lambda p, avg, est, need: (f"इन दिनों में कोई बिक्री दर्ज नहीं है। आम दिन में {p} लगभग "
                                         f"{avg} यूनिट बिकता है, इसलिए करीब {est} यूनिट का रिकॉर्ड छूट "
                                         f"सकता है। अंतर {need} यूनिट का है।")},
    "r_nosales_check": {
        "hn": "Un dinon ki bill book ya billing app dekhiye, aur sales export mein add kijiye.",
        "en": "Check the bill book or billing app for those days and add them to the sales export.",
        "hi": "उन दिनों की बिल बुक या बिलिंग ऐप देखिए, और सेल्स एक्सपोर्ट में जोड़िए।"},
    "r_damage_head": {
        "hn": lambda pct: f"Damage bahut zyada darj hai ({pct}% of purchases)",
        "en": lambda pct: f"Damage is unusually high ({pct}% of purchases)",
        "hi": lambda pct: f"खराबी बहुत ज्यादा दर्ज है (खरीद का {pct}%)"},
    "r_damage_detail": {
        "hn": lambda p, units, pct, med: (f"{p} ka damage {units} unit hai, yaani {pct}% of purchases. "
                                          f"Baaki items ka median {med}% hai."),
        "en": lambda p, units, pct, med: (f"{p} has {units} damaged units, which is {pct}% of purchases. "
                                          f"The median for the other items is {med}%."),
        "hi": lambda p, units, pct, med: (f"{p} की खराबी {units} यूनिट है, यानी खरीद का {pct}%। "
                                          f"बाकी आइटम का मध्यमान {med}% है।")},
    "r_damage_check": {
        "hn": "Damage ki entries check kijiye: kya sab sahi hain, ya kuch damage aur record hona baaki hai?",
        "en": "Check the damage entries: are they all correct, or is some damage still to be recorded?",
        "hi": "खराबी की एंट्रियाँ जाँचिए: क्या सब सही हैं, या कुछ खराबी दर्ज होना बाकी है?"},
    "r_unrec_head": {
        "hn": "Ho sakta hai koi purchase ya return darj nahi hua",
        "en": "A purchase or return may not have been recorded",
        "hi": "हो सकता है कोई खरीद या वापसी दर्ज न हुई हो"},
    "r_unrec_detail": {
        "hn": lambda gap: (f"Ginti mein {gap} unit zyada mile. Koi purchase, return ya "
                           f"opening stock ki entry chhut sakti hai."),
        "en": lambda gap: (f"The count found {gap} more units. A purchase, return or "
                           f"opening stock entry may be missing."),
        "hi": lambda gap: (f"गिनती में {gap} यूनिट ज्यादा मिले। कोई खरीद, वापसी या "
                           f"ओपनिंग स्टॉक की एंट्री छूट सकती है।")},
    "r_unrec_check": {
        "hn": "Supplier bills aur purchase entries dekhiye, aur ginti dobara kijiye.",
        "en": "Check the supplier bills and purchase entries, and count again.",
        "hi": "सप्लायर बिल और खरीद की एंट्रियाँ देखिए, और गिनती दोबारा कीजिए।"},
    "r_recount_head": {
        "hn": "Ginti mein galti ho sakti hai",
        "en": "There may be a counting mistake",
        "hi": "गिनती में गलती हो सकती है"},
    "r_recount_detail": {
        "hn": "Kabhi kabhi ginti ya entry mein chhoti galti se bhi gap aa jata hai.",
        "en": "Sometimes even a small slip in counting or data entry creates a gap.",
        "hi": "कभी-कभी गिनती या एंट्री की छोटी गलती से भी अंतर आ जाता है।"},
    "r_recount_check": {
        "hn": "Is item ki ginti ek baar aur kijiye.",
        "en": "Count this item once more.",
        "hi": "इस आइटम की गिनती एक बार और कीजिए।"},
    # ---- chart titles
    "t_rank": {
        "hn": lambda more, metric, ev: f"Sabse {'zyada' if more else 'kam'} ({metric}, {ev.lower()})",
        "en": lambda more, metric, ev: f"{'Top' if more else 'Slowest'} sellers ({metric}, {ev[:1].lower() + ev[1:]})",
        "hi": lambda more, metric, ev: f"सबसे {'ज्यादा' if more else 'कम'} ({'मात्रा' if metric == 'quantity' else 'बिक्री'}, {ev})"},
    "t_daily": {
        "hn": lambda who, metric: f"{who}: daily {metric}" if who else f"Daily {metric}",
        "en": lambda who, metric: (f"{who}: daily " if who else "Daily ") + ("units sold" if metric == "quantity" else "sales"),
        "hi": lambda who, metric: (f"{who}: " if who else "") + ("रोज़ की बिक्री (यूनिट)" if metric == "quantity" else "रोज़ की बिक्री")},
    "t_compare": {
        "hn": lambda metric: f"{metric}: comparison",
        "en": lambda metric: "Units sold: comparison" if metric == "quantity" else "Sales: comparison",
        "hi": lambda metric: "यूनिट की तुलना" if metric == "quantity" else "बिक्री की तुलना"},
    "t_low": {"hn": "Low stock items", "en": "Low stock items", "hi": "कम स्टॉक वाले आइटम"},
    "t_damaged": {"hn": "Damaged units", "en": "Damaged units", "hi": "खराब यूनिट"},
    "t_gap": {"hn": "Stock gap (counted - expected)", "en": "Stock gap (counted - expected)",
              "hi": "स्टॉक अंतर (गिना हुआ - अपेक्षित)"},
    "total_word": {"hn": "Total", "en": "Total", "hi": "कुल"},
    # ---- messages for the person (not answers)
    "m_empty": {
        "hn": "Kuch bolkar ya likhkar poochhiye.",
        "en": "Please speak or type your question.",
        "hi": "कुछ बोलकर या लिखकर पूछिए।"},
    "m_no_understand": {
        "hn": ("Mujhe yeh sawaal samajh nahi aaya. Jaise poochhiye: "
               "'Pichle mahine sabse zyada kya bika?'"),
        "en": "I did not understand that question. Try asking: 'Which product sold the most last month?'",
        "hi": "मुझे यह सवाल समझ नहीं आया। जैसे पूछिए: 'पिछले महीने सबसे ज्यादा क्या बिका?'"},
    "m_which_product": {
        "hn": "Kis product ka gap jaanna hai?",
        "en": "Which product's gap do you want to know about?",
        "hi": "किस प्रोडक्ट का अंतर जानना है?"},
    "m_advice": {
        "hn": ("Main sirf aapke sales aur stock ke records se jawab de sakta hoon, business ki salah nahi. "
               "Poochhiye: 'Pichle mahine sabse zyada kya bika?'"),
        "en": ("I can answer from your sales and stock records, but I cannot give business advice. "
               "Try asking: 'Which product sold the most last month?'"),
        "hi": ("मैं सिर्फ आपके सेल्स और स्टॉक के रिकॉर्ड से जवाब दे सकता हूं, बिज़नेस की सलाह नहीं। "
               "पूछिए: 'पिछले महीने सबसे ज्यादा क्या बिका?'")},
    "m_scope": {
        "hn": ("Main sirf aapke sales aur stock ke records se jawab deta hoon: bikri, top products, low stock, "
               "stock gap aur gap ka 'kyun'. Aage ka andaza, customers, staff, bhav, discount, tax ya bikri badalne ki wajah main nahi bata sakta."),
        "en": ("I answer only from your sales and stock records: sales, top products, low stock, stock gaps and why a gap "
               "happened. I cannot predict the future, or answer about customers, staff, market prices, discounts, tax or why sales changed."),
        "hi": ("मैं सिर्फ आपके सेल्स और स्टॉक के रिकॉर्ड से जवाब देता हूं: बिक्री, टॉप प्रोडक्ट, कम स्टॉक, स्टॉक गैप और गैप का कारण। "
               "आगे का अनुमान, ग्राहक, स्टाफ, बाज़ार भाव, डिस्काउंट, टैक्स या बिक्री बदलने की वजह मैं नहीं बता सकता।")},
    "m_period": {
        "hn": ("Main aaj, kal, is/pichle hafte, is/pichle mahine ya pichle 30 din ka jawab de sakta hoon. "
               "Aapka data 3 Aug se 31 Oct 2026 tak ka hai."),
        "en": ("I can answer for today, yesterday, this or last week, this or last month, and the last 30 days. "
               "Your data runs from 3 Aug to 31 Oct 2026."),
        "hi": ("मैं आज, कल, इस या पिछले हफ्ते, इस या पिछले महीने और पिछले 30 दिनों का जवाब दे सकता हूं। "
               "आपका डेटा 3 अगस्त से 31 अक्टूबर 2026 तक का है।")},
    "m_unknown_product": {
        "hn": lambda w: f"Mujhe '{w}' naam ka product nahi mila. Aapke products: {_plist('hn')}.",
        "en": lambda w: f"I could not find a product called '{w}'. Your products are: {_plist('en')}.",
        "hi": lambda w: f"मुझे '{w}' नाम का प्रोडक्ट नहीं मिला। आपके प्रोडक्ट: {_plist('hi')}।"},
    "m_unsupported": {
        "hn": "Yeh sawaal abhi supported nahi hai.",
        "en": "This question is not supported yet.",
        "hi": "यह सवाल अभी उपलब्ध नहीं है।"},
    "m_failed": {
        "hn": "Kuch gadbad ho gayi. Dobara koshish kijiye.",
        "en": "Something went wrong. Please try again.",
        "hi": "कुछ गड़बड़ हो गई। दोबारा कोशिश कीजिए।"},
    "m_failed_short": {
        "hn": "Kuch gadbad ho gayi.", "en": "Something went wrong.", "hi": "कुछ गड़बड़ हो गई।"},
    "m_audio_empty": {
        "hn": "Kuch record nahi hua. Dobara bolkar dekhiye.",
        "en": "Nothing was recorded. Please try speaking again.",
        "hi": "कुछ रिकॉर्ड नहीं हुआ। दोबारा बोलकर देखिए।"},
    "m_audio_long": {
        "hn": "Recording bahut lambi hai. 30 second se kam rakhiye.",
        "en": "The recording is too long. Keep it under 30 seconds.",
        "hi": "रिकॉर्डिंग बहुत लंबी है। 30 सेकंड से कम रखिए।"},
    "m_audio_unclear": {
        "hn": "Awaaz saaf nahi aayi. Dobara bolkar dekhiye.",
        "en": "I could not hear that clearly. Please try again.",
        "hi": "आवाज़ साफ़ नहीं आई। दोबारा बोलकर देखिए।"},
    "v_reject": {
        "hn": "Mujhe yeh sawaal samajh nahi aaya. Kripya dobara poochhiye.",
        "en": "I did not understand that question. Please ask again.",
        "hi": "मुझे यह सवाल समझ नहीं आया। कृपया दोबारा पूछिए।"},
    "v_unknown_product": {
        "hn": lambda p: f"Mujhe '{p}' naam ka product nahi mila.",
        "en": lambda p: f"I could not find a product called '{p}'.",
        "hi": lambda p: f"मुझे '{p}' नाम का प्रोडक्ट नहीं मिला।"},
    "v_confirm_product": {
        "hn": lambda n: f"Kya aap {n} keh rahe hain?",
        "en": lambda n: f"Do you mean {n}?",
        "hi": lambda n: f"क्या आप {n} कह रहे हैं?"},
    "v_unknown_cat": {
        "hn": lambda c: f"Mujhe '{c}' category nahi mili.",
        "en": lambda c: f"I could not find a category called '{c}'.",
        "hi": lambda c: f"मुझे '{c}' नाम की श्रेणी नहीं मिली।"},
    "v_compare_period": {
        "hn": "Kis period se compare karna hai?",
        "en": "Which period do you want to compare with?",
        "hi": "किस अवधि से तुलना करनी है?"},
    "v_confirm_query": {
        "hn": "Kya aapka matlab yahi sawaal hai?",
        "en": "Is this the question you meant?",
        "hi": "क्या आपका मतलब यही सवाल है?"},
    # ---- Gnani service problems (key = error code in gnani.py)
    "g_not_configured": {
        "hn": "Awaaz wali service set nahi hai. Likhkar poochhiye.",
        "en": "The voice service is not set up. Please type your question.",
        "hi": "आवाज़ वाली सेवा सेट नहीं है। लिखकर पूछिए।"},
    "g_auth": {
        "hn": "Awaaz wali service ki key sahi nahi hai. Likhkar poochhiye.",
        "en": "The voice service key is not valid. Please type your question.",
        "hi": "आवाज़ वाली सेवा की की (key) सही नहीं है। लिखकर पूछिए।"},
    "g_credit": {
        "hn": "Awaaz wali service ka credit khatam ho gaya. Likhkar poochhiye.",
        "en": "The voice service has run out of credit. Please type your question.",
        "hi": "आवाज़ वाली सेवा का क्रेडिट खत्म हो गया। लिखकर पूछिए।"},
    "g_busy": {
        "hn": "Awaaz wali service abhi vyast hai. Thodi der baad koshish kijiye.",
        "en": "The voice service is busy. Please try again in a moment.",
        "hi": "आवाज़ वाली सेवा अभी व्यस्त है। थोड़ी देर बाद कोशिश कीजिए।"},
    "g_bad_audio": {
        "hn": "Awaaz record theek se nahi hui. Dobara bolkar dekhiye.",
        "en": "The recording did not come out well. Please try speaking again.",
        "hi": "आवाज़ ठीक से रिकॉर्ड नहीं हुई। दोबारा बोलकर देखिए।"},
    "g_unavailable": {
        "hn": "Awaaz wali service abhi nahi mil rahi. Likhkar poochhiye.",
        "en": "The voice service is not available right now. Please type your question.",
        "hi": "आवाज़ वाली सेवा अभी उपलब्ध नहीं है। लिखकर पूछिए।"},
}


def s(key: str, lang="hn", *args):
    """A sentence (or the result of a sentence function) in the chosen language."""
    entry = S[key][norm(lang)]
    return entry(*args) if callable(entry) else entry


def direction(lang, change) -> tuple:
    """(word, kind) for a change: more / less / same in the chosen language."""
    kind = "more" if change > 0 else "less" if change < 0 else "same"
    return S["dir"][norm(lang)][kind], kind


# ---------------------------------------------------------------- for the speaker
_ROMAN_NAMES = re.compile(r"\b(" + "|".join(DEVANAGARI) + r")\b")
_NUMBER = re.compile(r"\d+(?:\.\d+)?")

# Hinglish words the speaker reads with English rules when they are in Roman letters
# ("Pichle" comes out as "pickle"). Written in Devanagari for the voice only; the text
# on screen is not changed. Add a word here whenever the speaker mispronounces one.
_HINGLISH_SPOKEN = {
    "pichle": "पिछले", "pichhle": "पिछले", "hafte": "हफ्ते", "mahine": "महीने", "din": "दिन",
    "dinon": "दिनों", "mein": "में", "aaj": "आज", "kal": "कल", "ab": "अब", "tak": "तक",
    "is": "इस", "ki": "की", "ka": "का", "ko": "को", "sabse": "सबसे", "zyada": "ज़्यादा",
    "kam": "कम", "bikne": "बिकने", "wale": "वाले", "bika": "बिका", "bikri": "बिक्री",
    "rahi": "रही", "raha": "रहा", "hui": "हुई", "hua": "हुआ", "tha": "था", "yaani": "यानी",
    "barabar": "बराबर", "kharab": "खराब", "maal": "माल", "hai": "है", "hain": "हैं",
    "nahi": "नहीं", "mila": "मिला", "koi": "कोई", "bacha": "बचा", "sirf": "सिर्फ़",
    "aur": "और", "bhi": "भी", "sab": "सब", "se": "से", "par": "पर", "neeche": "नीचे",
    "dekhiye": "देखिए", "kijiye": "कीजिए", "dobara": "दोबारा", "poochhiye": "पूछिए",
    "bolkar": "बोलकर", "likhkar": "लिखकर", "theek": "ठीक", "stock": "स्टॉक",
    "hazaar": "हज़ार", "lakh": "लाख", "crore": "करोड़", "rupaye": "रुपये",
}
_HINGLISH_WORD = re.compile(r"\b(" + "|".join(sorted(_HINGLISH_SPOKEN, key=len, reverse=True)) + r")\b",
                            re.IGNORECASE)


def _hindi_words(n: int) -> str:
    if n < 100:
        return _HI_0_99[n]
    hundreds, rest = divmod(n, 100)
    return _HI_0_99[hundreds] + " सौ" + (" " + _HI_0_99[rest] if rest else "")


def _hindi_number(m) -> str:
    whole, _, frac = m.group(0).partition(".")
    n = int(whole)
    words = _hindi_words(n) if n < 1000 else whole      # amounts are split into groups below 1000
    return words + (" दशमलव " + " ".join(_HI_0_99[int(d)] for d in frac) if frac else "")


def to_voice(text: str, lang="hn") -> str:
    """The same sentence, written the way the speaker pronounces it best.

    Hinglish: product names in Devanagari, so Chawal is not read like an English word.
    Hindi: digits as Hindi words. English: unchanged.
    """
    lang = norm(lang)
    if not text:
        return text
    if lang == "hn":
        text = _ROMAN_NAMES.sub(lambda m: DEVANAGARI[m.group(1)], text)
        return _HINGLISH_WORD.sub(lambda m: _HINGLISH_SPOKEN[m.group(1).lower()], text)
    if lang == "hi":
        return _NUMBER.sub(_hindi_number, text)
    return text


TTS_LANGUAGE = {"hn": "hi-en", "en": "en-IN", "hi": "hi-IN"}