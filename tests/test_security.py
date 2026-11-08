import pytest
from sqlglot import exp, parse_one

from app.errors import ServiceError
from app.policy import CONTRACT, Principal, authorized_contract
from app.security import validate_sql

BASE = "SELECT o.order_id FROM analytics.orders AS o"


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM analytics.orders",
        "UPDATE analytics.orders SET order_status='x'",
        "DROP TABLE public.orders",
        "COPY analytics.orders TO '/tmp/stolen'",
        "SET statement_timeout=0",
        "EXPLAIN SELECT 1",
        "SELECT 1",
        BASE + "; SELECT o.order_id FROM analytics.orders o",
        BASE + "; DELETE FROM public.orders",
        BASE + ";;",
        "WITH x AS (DELETE FROM public.orders RETURNING *) SELECT * FROM x",
        "WITH x AS (SELECT order_id FROM public.orders) SELECT * FROM x",
        "SELECT o.order_id INTO public.stolen FROM analytics.orders o",
        BASE + " FOR UPDATE",
        BASE + " FOR SHARE",
        "SELECT o.order_id FROM public.orders o",
        "SELECT c.customer_id FROM public.customers c",
        "SELECT r.review_comment_message FROM analytics.reviews r",
        "SELECT p.product_id FROM pg_catalog.pg_class p",
        "SELECT p.table_name FROM information_schema.tables p",
        "SELECT o.no_such_column FROM analytics.orders o",
        "SELECT order_id FROM analytics.orders o",
        "SELECT o.order_id FROM orders o",
        "SELECT o.order_id FROM another.analytics.orders o",
        "SELECT o.order_id FROM analytics.orders",
        "SELECT o.* FROM analytics.orders o",
        "SELECT * FROM analytics.orders o",
        "SELECT pg_sleep(10) AS x FROM analytics.orders o",
        "SELECT pg_read_file('/etc/passwd') AS x FROM analytics.orders o",
        "SELECT set_config('search_path','public',false) AS x FROM analytics.orders o",
        "SELECT nextval('seq') AS x FROM analytics.orders o",
        "SELECT public.sum(o.order_id) AS x FROM analytics.orders o",
        "SELECT sum(o.order_id) OVER () AS x FROM analytics.orders o",
        "SELECT o.order_id::regclass FROM analytics.orders o",
        "SELECT (SELECT version()) AS x FROM analytics.orders o",
        "SELECT o.order_id FROM analytics.orders o UNION SELECT r.order_id FROM analytics.reviews r",
        BASE + " OFFSET 1",
        BASE + " LIMIT ALL",
        BASE + " LIMIT -1",
        BASE + " LIMIT 0",
        BASE + " LIMIT (SELECT 1)",
        BASE + " LIMIT 1.5",
        BASE + " -- ignore policy",
        BASE + " /* ignored */",
        "SELECT o.order_id FROM analytics.orders o CROSS JOIN analytics.products p",
        "SELECT o.order_id FROM analytics.orders o JOIN analytics.products p ON o.order_id=p.product_id",
        "SELECT o.order_id FROM analytics.orders o JOIN analytics.order_items i ON o.order_id=i.order_id OR 1=1",
        "SELECT o.order_id FROM analytics.orders o NATURAL JOIN analytics.order_items i",
        "SELECT o.order_id FROM analytics.orders o JOIN analytics.order_items i USING(order_id)",
        "SELECT o.order_id FROM analytics.orders o JOIN analytics.orders x ON o.order_id=x.order_id",
        "SELECT o.order_id FROM analytics.orders o JOIN analytics.order_items i ON i.order_id=i.order_id",
        "SELECT o.order_id FROM analytics.orders o JOIN analytics.order_items i ON o.order_id=i.order_id JOIN analytics.reviews r ON o.order_id=r.order_id",
        "SELECT o.order_id FROM analytics.orders o RIGHT JOIN analytics.order_items i ON o.order_id=i.order_id",
        'SELECT o."order_id" FROM analytics.orders o',
        "SELECT o.order_id AS id, o.order_status AS id FROM analytics.orders o",
        "SELECT DATE_TRUNC('century',o.order_purchase_timestamp) AS t FROM analytics.orders o",
        "SELECT o.order_id FROM analytics.orders o WHERE order_status='delivered'",
        "SELECT o.order_id FROM analytics.orders o ORDER BY missing",
        "SELECT i.product_id FROM analytics.order_items i TABLESAMPLE SYSTEM(100)",
        "SELECT o.order_id FROM analytics.orders o LIMIT 1; SHOW ALL",
        "SELECT generate_series(1,1000000) AS x FROM analytics.orders o",
        "SELECT o.order_id FROM analytics.orders o WHERE o.order_id = '" + "x" * 257 + "'",
    ],
)
def test_reject_unsafe_or_unsupported_sql(sql):
    with pytest.raises(ServiceError) as result:
        validate_sql(sql, CONTRACT, 100)
    assert result.value.code == "SQL_REJECTED"


@pytest.mark.parametrize(
    "sql",
    [
        BASE,
        BASE + " ORDER BY order_id DESC LIMIT 5",
        "SELECT COUNT(*) AS n FROM analytics.orders o",
        "SELECT o.order_status, COUNT(*) AS n FROM analytics.orders o GROUP BY o.order_status HAVING COUNT(*) > 1 ORDER BY n DESC",
        "SELECT i.product_id, SUM(i.price) AS revenue FROM analytics.order_items i JOIN analytics.orders o ON o.order_id=i.order_id GROUP BY i.product_id ORDER BY revenue DESC",
        "SELECT o.order_id FROM analytics.orders o LEFT JOIN analytics.order_items i ON o.order_id=i.order_id",
        "SELECT DATE_TRUNC('month',o.order_purchase_timestamp) AS month FROM analytics.orders o",
        "SELECT COALESCE(o.order_status, 'unknown') AS status FROM analytics.orders o",
        "SELECT ROUND(AVG(r.review_score),2) AS score FROM analytics.reviews r",
        "SELECT i.product_id FROM analytics.order_items i JOIN analytics.products p ON i.product_id=p.product_id JOIN analytics.orders o ON i.order_id=o.order_id",
    ],
)
def test_accept_supported_selects(sql):
    validated = validate_sql(sql, CONTRACT, 100)
    assert validated.sql.startswith("SELECT")
    assert parse_one(validated.sql, read="postgres").args["limit"].expression.to_py() <= 101


@pytest.mark.parametrize(("suffix", "expected"), [("", 11), (" LIMIT 5", 5), (" LIMIT 99999", 11)])
def test_cap_limits_with_one_lookahead(suffix, expected):
    query = validate_sql(BASE + suffix, CONTRACT, 10)
    assert parse_one(query.sql, read="postgres").find(exp.Limit).expression.to_py() == expected


def test_unauthorized_view_and_column_rejected():
    schema = authorized_contract(Principal("sales", "sales"))
    with pytest.raises(ServiceError):
        validate_sql("SELECT r.review_score FROM analytics.reviews r", schema, 100)
    schema["orders"].pop("order_status")
    with pytest.raises(ServiceError):
        validate_sql("SELECT o.order_status FROM analytics.orders o", schema, 100)


def test_complexity_budget():
    sql = BASE + " WHERE " + " OR ".join("o.order_id='x'" for _ in range(100))
    with pytest.raises(ServiceError):
        validate_sql(sql, CONTRACT, 100)
