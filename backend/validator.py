import difflib
from typing import NamedTuple, Optional, Union

from pydantic import ValidationError

from backend import phrases
from backend.config import ALIASES, PRODUCTS
from backend.schemas import StructuredQuery

CONFIDENCE_MIN = 0.6
_PRODUCTS = {a.lower(): p for p, names in ALIASES.items() for a in names}
_CATEGORIES = {details[0].lower(): details[0] for details in PRODUCTS.values()}


class Verdict(NamedTuple):
    status: str                      # ok | confirm | clarify | reject
    query: Optional[StructuredQuery]
    message: str                     # shown on screen and spoken when not "ok"


def resolve_product(text: str):
    """Returns (standard_name, status). status is exact, confirm or unknown."""
    t = text.strip().lower()
    if t in _PRODUCTS:
        return _PRODUCTS[t], "exact"
    close = difflib.get_close_matches(t, list(_PRODUCTS), n=1, cutoff=0.8)
    if close:
        return _PRODUCTS[close[0]], "confirm"
    return None, "unknown"


def validate(raw: Union[dict, StructuredQuery], lang: str = "hn") -> Verdict:
    # 1. shape: anything outside the schema is rejected
    try:
        q = raw if isinstance(raw, StructuredQuery) else StructuredQuery.model_validate(raw)
    except ValidationError:
        return Verdict("reject", None, phrases.s("v_reject", lang))

    status, message = "ok", ""

    # 2. product must be a known product (aliases allowed, near matches ask first)
    if q.product:
        name, how = resolve_product(q.product)
        if how == "unknown":
            return Verdict("clarify", None, phrases.s("v_unknown_product", lang, q.product))
        q = q.model_copy(update={"product": name})
        if how == "confirm":
            status, message = "confirm", phrases.s("v_confirm_product", lang, phrases.nm(lang, name))

    # 3. category must be a known category
    if q.category:
        cat = _CATEGORIES.get(q.category.strip().lower())
        if cat is None:
            return Verdict("clarify", None, phrases.s("v_unknown_cat", lang, q.category))
        q = q.model_copy(update={"category": cat})

    # 4. a comparison needs two periods
    if q.intent == "compare" and q.compare_period is None:
        return Verdict("clarify", None, phrases.s("v_compare_period", lang))

    # 5. low confidence: ask before running
    if status == "ok" and q.confidence < CONFIDENCE_MIN:
        status, message = "confirm", phrases.s("v_confirm_query", lang)

    return Verdict(status, q, message)
