from dataclasses import dataclass

from app.errors import ServiceError

# The authoritative contract; live metadata must match before it is used.
CONTRACT = {
    "orders": {
        "order_id": "text",
        "order_status": "text",
        "order_purchase_timestamp": "timestamp without time zone",
    },
    "order_items": {
        "order_id": "text",
        "order_item_id": "integer",
        "product_id": "text",
        "seller_id": "text",
        "price": "numeric",
        "freight_value": "numeric",
    },
    "products": {
        "product_id": "text",
        "product_category_name": "text",
        "product_weight_g": "integer",
    },
    "sellers": {"seller_id": "text", "seller_state": "text"},
    "reviews": {"order_id": "text", "review_score": "integer"},
}
SALES_VIEWS = frozenset({"orders", "order_items", "products", "sellers"})
RELATIONSHIPS = (
    ("order_items", "order_id", "orders", "order_id"),
    ("order_items", "product_id", "products", "product_id"),
    ("order_items", "seller_id", "sellers", "seller_id"),
    ("reviews", "order_id", "orders", "order_id"),
)
DEFINITIONS = {
    "revenue": "BRL; sum of item price on delivered orders, excluding freight.",
    "monthly_revenue": "Revenue grouped by order purchase month, not delivery month.",
    "review_score": "Average of review records; an order can have multiple review records.",
}


@dataclass(frozen=True)
class Principal:
    subject: str
    role: str

    @property
    def views(self) -> frozenset[str]:
        if self.role == "sales":
            return SALES_VIEWS
        if self.role == "analyst":
            return frozenset(CONTRACT)
        raise ServiceError("FORBIDDEN", "This caller has no query policy.", 403)


def authorized_contract(principal: Principal) -> dict[str, dict[str, str]]:
    return {name: dict(CONTRACT[name]) for name in sorted(principal.views)}


def schema_document(schema: dict[str, dict[str, str]]) -> dict:
    return {
        "schema": "analytics",
        "tables": schema,
        "relationships": [list(r) for r in RELATIONSHIPS if r[0] in schema and r[2] in schema],
        "definitions": DEFINITIONS,
    }
