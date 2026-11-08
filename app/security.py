import re
from dataclasses import dataclass

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

from app.errors import ServiceError
from app.policy import RELATIONSHIPS

# Exact node types, not inheritance: newly introduced SQL features fail closed.
ALLOWED_NODES = frozenset(
    {
        exp.Select,
        exp.From,
        exp.Table,
        exp.TableAlias,
        exp.Identifier,
        exp.Column,
        exp.Alias,
        exp.Literal,
        exp.Star,
        exp.Count,
        exp.Sum,
        exp.Avg,
        exp.Min,
        exp.Max,
        exp.Round,
        exp.Coalesce,
        exp.TimestampTrunc,
        exp.Var,
        exp.Where,
        exp.Group,
        exp.Having,
        exp.Order,
        exp.Ordered,
        exp.Limit,
        exp.Join,
        exp.EQ,
        exp.NEQ,
        exp.GT,
        exp.GTE,
        exp.LT,
        exp.LTE,
        exp.And,
        exp.Or,
        exp.Not,
        exp.Is,
        exp.Null,
        exp.Boolean,
        exp.Paren,
        exp.Add,
        exp.Sub,
        exp.Mul,
        exp.Div,
        exp.Neg,
    }
)
NAME = re.compile(r"[a-z][a-z0-9_]{0,62}\Z")


@dataclass(frozen=True)
class ValidatedQuery:
    sql: str
    source_views: tuple[str, ...]
    row_limit: int


def reject() -> None:
    raise ServiceError(
        "SQL_REJECTED", "The generated query does not satisfy the read-only SQL policy.", 422
    )


def validate_sql(sql: str, schema: dict[str, dict[str, str]], row_limit: int) -> ValidatedQuery:
    try:
        return _validate(sql, schema, row_limit)
    except ServiceError:
        raise
    except (SqlglotError, ValueError, TypeError, AttributeError, RecursionError):
        reject()


def _validate(sql: str, schema: dict[str, dict[str, str]], row_limit: int) -> ValidatedQuery:
    if not isinstance(sql, str) or not 0 < len(sql) <= 12000 or not 1 <= row_limit <= 1000:
        reject()
    statements = sqlglot.parse(sql, read="postgres")
    if len(statements) != 1 or type(statements[0]) is not exp.Select:
        reject()
    tree = statements[0]
    nodes = list(tree.walk())
    if len(nodes) > 250:
        reject()
    for node in nodes:
        if type(node) not in ALLOWED_NODES or node.comments or node.depth > 24:
            reject()
        if isinstance(node, exp.Select) and node is not tree:
            reject()
        if isinstance(node, exp.Identifier) and (node.quoted or not NAME.fullmatch(node.name)):
            reject()
        if isinstance(node, exp.Literal) and len(node.this) > 256:
            reject()
        if isinstance(node, exp.Star) and not (
            type(node.parent) is exp.Count and node.parent.this is node
        ):
            reject()
        if isinstance(node, exp.Var) and not (
            type(node.parent) is exp.TimestampTrunc
            and node.arg_key == "unit"
            and node.name.upper() in {"DAY", "MONTH", "YEAR"}
        ):
            reject()
    # Reject structural modifiers even if their child node types happen to be allowed.
    if any(
        value
        for key, value in tree.args.items()
        if key
        not in {"expressions", "from_", "joins", "where", "group", "having", "order", "limit"}
    ):
        reject()
    source = tree.args.get("from_")
    if source is None or type(source.this) is not exp.Table:
        reject()
    tables = list(tree.find_all(exp.Table))
    aliases = {}
    for table in tables:
        if table.catalog or table.db != "analytics" or table.name not in schema:
            reject()
        if any(value for key, value in table.args.items() if key not in {"this", "db", "alias"}):
            reject()
        if not table.alias or table.alias in aliases or table.name in aliases.values():
            reject()
        if table.args["alias"].args.get("columns"):
            reject()
        aliases[table.alias] = table.name
    if not tables or len(tables) > 3 or {"reviews", "order_items"} <= set(aliases.values()):
        reject()
    projections = tree.expressions
    if not 1 <= len(projections) <= 20:
        reject()
    output_names = [p.alias_or_name for p in projections]
    if any(not NAME.fullmatch(n) for n in output_names) or len(set(output_names)) != len(
        output_names
    ):
        reject()
    for column in tree.find_all(exp.Column):
        if column.db or column.catalog:
            reject()
        if not column.table:
            # Output aliases are usable only in ORDER BY, never as unresolved input columns.
            if column.name not in output_names or column.find_ancestor(exp.Order) is None:
                reject()
        elif column.table not in aliases or column.name not in schema[aliases[column.table]]:
            reject()
    for trunc in tree.find_all(exp.TimestampTrunc):
        if type(trunc.this) is not exp.Column or trunc.args.get("zone"):
            reject()
    connected = {source.this.alias}
    joins = tree.args.get("joins") or []
    if len(joins) != len(tables) - 1:
        reject()
    for join in joins:
        if join.args.get("side") not in {None, "", "LEFT"} or join.args.get("kind") not in {
            None,
            "",
            "INNER",
        }:
            reject()
        if any(
            value for key, value in join.args.items() if key not in {"this", "on", "side", "kind"}
        ):
            reject()
        on = join.args.get("on")
        if type(join.this) is not exp.Table or type(on) is not exp.EQ:
            reject()
        if type(on.this) is not exp.Column or type(on.expression) is not exp.Column:
            reject()
        left, right = on.this, on.expression
        new_alias = join.this.alias
        if not (
            (left.table == new_alias and right.table in connected)
            or (right.table == new_alias and left.table in connected)
        ):
            reject()
        relationship = (aliases[left.table], left.name, aliases[right.table], right.name)
        reverse = (relationship[2], relationship[3], relationship[0], relationship[1])
        if relationship not in RELATIONSHIPS and reverse not in RELATIONSHIPS:
            reject()
        connected.add(new_alias)
    limit = tree.args.get("limit")
    limit_value = row_limit + 1
    if limit:
        literal = limit.expression
        if (
            type(literal) is not exp.Literal
            or literal.is_string
            or not re.fullmatch(r"[0-9]{1,7}", literal.this)
            or int(literal.this) < 1
        ):
            reject()
        limit_value = min(int(literal.this), row_limit + 1)
    tree.set("limit", exp.Limit(expression=exp.Literal.number(limit_value)))
    return ValidatedQuery(
        tree.sql(dialect="postgres"),
        tuple(sorted("analytics." + name for name in aliases.values())),
        row_limit,
    )
