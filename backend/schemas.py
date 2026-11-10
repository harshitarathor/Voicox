from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

Intent = Literal[
    "total",        # one number: revenue or quantity for a period
    "ranked",       # top or slow-moving products or categories
    "trend",        # daily values for a chart
    "compare",      # period A against period B
    "low_stock",    # items below reorder level
    "wastage",      # damaged quantity
    "stock_gap",    # Stock Loss Detective
    "explain_gap",  # "Chawal mein gap kyun hai?"
]

Period = Literal["today", "yesterday", "this_week", "last_week", "this_month",
                 "last_month", "last_30_days", "all"]


class StructuredQuery(BaseModel):
    """The only thing the language model is allowed to produce."""
    model_config = ConfigDict(extra="forbid")   # unknown fields are rejected

    intent: Intent
    metric: Literal["revenue", "quantity"] = "revenue"
    group_by: Literal["product", "category"] = "product"
    period: Period = "last_30_days"
    compare_period: Optional[Period] = None
    product: Optional[str] = None
    category: Optional[str] = None
    limit: int = Field(default=5, ge=1, le=20)
    order: Literal["asc", "desc"] = "desc"
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)