import sqlglot
from sqlglot import exp


def _sqlglot_parameter_syntax(sql: str) -> str:
    """Expose psycopg named bindings to SQLGlot without touching quoted text."""

    result: list[str] = []
    index = 0
    state = "code"
    while index < len(sql):
        pair = sql[index : index + 2]
        if state == "code" and pair == "--":
            state = "line_comment"
            result.append(pair)
            index += 2
        elif state == "code" and pair == "/*":
            state = "block_comment"
            result.append(pair)
            index += 2
        elif state == "line_comment" and sql[index] == "\n":
            state = "code"
            result.append(sql[index])
            index += 1
        elif state == "block_comment" and pair == "*/":
            state = "code"
            result.append(pair)
            index += 2
        elif state == "code" and sql[index] in {"'", '"'}:
            state = "single_quote" if sql[index] == "'" else "double_quote"
            result.append(sql[index])
            index += 1
        elif state == "single_quote" and pair == "''":
            result.append(pair)
            index += 2
        elif state == "double_quote" and pair == '""':
            result.append(pair)
            index += 2
        elif state in {"single_quote", "double_quote"} and sql[index] == (
            "'" if state == "single_quote" else '"'
        ):
            state = "code"
            result.append(sql[index])
            index += 1
        elif state == "code" and sql.startswith("%(", index):
            close = sql.find(")s", index + 2)
            name = sql[index + 2 : close] if close != -1 else ""
            if name.isidentifier():
                result.append(f":{name}")
                index = close + 2
            else:
                result.append(sql[index])
                index += 1
        else:
            result.append(sql[index])
            index += 1
    return "".join(result)


RETAIL_V1_TABLES = frozenset(
    {"customers", "orders", "order_lines", "returns", "customer_monthly_targets"}
)
REVIEWED_FUNCTIONS = frozenset(
    {
        "and",
        "case",
        "cast",
        "coalesce",
        "exists",
        "if",
        "nullif",
        "or",
        "row_number",
        "sum",
        "timestamp_trunc",
    }
)
# Tier-0 plans may aggregate any column kind the compiler admits; these are
# the only additional functions the plan compiler can emit.
PLAN_AGGREGATE_FUNCTIONS = frozenset(
    {"count", "avg", "min", "max", "distinct", "lag", "filter"}
)


class PostgresSqlPolicy:
    """Allowlist gate over the physical SQL AST.

    The defaults keep the reviewed retail_v1 contract unchanged. A datasource
    built from introspection passes its own table allowlist, and the plan
    compiler path additionally allows the plan aggregate functions.
    """

    def __init__(
        self,
        *,
        tables: frozenset[str] | set[str] | None = None,
        functions: frozenset[str] | set[str] | None = None,
    ) -> None:
        self._tables = set(RETAIL_V1_TABLES if tables is None else tables)
        self._functions = set(REVIEWED_FUNCTIONS if functions is None else functions)

    _forbidden_nodes = (
        exp.Delete,
        exp.Insert,
        exp.Update,
        exp.Merge,
        exp.Create,
        exp.Drop,
        exp.Alter,
        exp.Copy,
        exp.Command,
        exp.Transaction,
        exp.Lock,
    )

    def assert_safe_select_statement(self, sql: str) -> str:
        try:
            parsed = sqlglot.parse(_sqlglot_parameter_syntax(sql), read="postgres")
        except Exception as error:
            raise ValueError("invalid PostgreSQL statement") from error
        if len(parsed) != 1 or not isinstance(parsed[0], (exp.Select, exp.With)):
            raise ValueError("only one SELECT statement is allowed")
        statement = parsed[0]
        with_clause = statement.args.get("with_")
        if with_clause is not None and with_clause.args.get("recursive"):
            raise ValueError("recursive CTEs are not supported")
        if any(statement.find(node) is not None for node in self._forbidden_nodes):
            raise ValueError("non-read-only SQL is denied")
        cte_names = {
            cte.alias_or_name
            for cte in statement.find_all(exp.CTE)
            if cte.alias_or_name
        }
        for table in statement.find_all(exp.Table):
            if table.name in cte_names:
                continue
            if table.db != "public" or table.name not in self._tables:
                raise ValueError("unapproved relation")
        for function in statement.find_all(exp.Func):
            sql_name = function.sql_name().lower()
            function_name = (
                (function.name or sql_name).lower()
                if sql_name == "anonymous"
                else sql_name
            )
            if function_name not in self._functions:
                raise ValueError("unapproved function")
        if statement.find(exp.Into):
            raise ValueError("SELECT INTO is denied")
        return sql
