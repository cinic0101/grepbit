"""Deterministic proposals for column policies; a reviewer approves them.

The proposer never decides. It writes a draft (``*.proposed.json``) the runtime
does not load; whatever the reviewer copies into the datasource overlay is the
policy. Rules are datasource-agnostic: kinds, cardinality, key columns, and
words in column names and comments that usually mark personal data.
"""

from __future__ import annotations

import re

from grepbit.domain.overlay import ColumnPolicy, Sensitivity
from grepbit.domain.plan import ColumnRef
from grepbit.domain.schema_model import ColumnKind, SchemaModel

# Words that usually mark a person: names, contact details, identifiers of a
# customer, member or employee. Matched against column names and comments,
# case-folded; Latin words need boundaries, CJK phrases do not.
PERSONAL_WORDS = (
    "name",
    "email",
    "e_mail",
    "phone",
    "mobile",
    "tel",
    "address",
    "birthday",
    "birth",
    "member",
    "customer",
    "employee",
    "staff",
    "user",
    "account",
    "id_no",
    "national_id",
    "passport",
    "姓名",
    "名字",
    "人員",
    "員工",
    "會員",
    "客戶",
    "顧客",
    "電話",
    "手機",
    "地址",
    "生日",
    "身分證",
    "帳號",
)
# Names that mean a thing, not a person, even though they contain "name".
THING_WORDS = (
    "store",
    "product",
    "category",
    "shop",
    "branch",
    "item",
    "sku",
    "門市",
    "商品",
    "分類",
    "品項",
    "店名",
)  # not 店 alone: 店長姓名 names a person, 門市名稱 a thing
GROUNDABLE_MAX_DISTINCT = 5000
PROPOSER_REVISION = "policy-proposer-v1"


def _mentions(text: str, words: tuple[str, ...]) -> bool:
    lowered = text.casefold()
    for word in words:
        if word.isascii():
            if re.search(rf"(?<![a-z0-9]){re.escape(word)}(?![a-z0-9])", lowered):
                return True
        elif word in lowered:
            return True
    return False


def propose_policies(schema: SchemaModel) -> list[ColumnPolicy]:
    """One proposal per text column: sensitivity and whether to ground it.

    - key columns (primary or foreign) are never grounded: their values are
      identifiers, not vocabulary;
    - a column whose name or comment mentions a person is ``personal`` (no
      sampling, no grounding) unless the name clearly means a thing (store,
      product, category), which keeps ``store_name`` public;
    - other text columns are ``public`` and grounded when their cardinality is
      known to be at most ``GROUNDABLE_MAX_DISTINCT``; unknown cardinality
      (sampling off) is proposed as grounded too, the index caps it later.
    """

    keys = {(fk.table, fk.column) for fk in schema.foreign_keys}
    for table in schema.tables:
        keys.update((table.name, column) for column in table.primary_key)
    proposals: list[ColumnPolicy] = []
    for table in schema.tables:
        for column in table.columns:
            if column.kind is not ColumnKind.TEXT:
                continue
            ref = ColumnRef(table=table.name, column=column.name)
            text = f"{column.name} {column.comment or ''}"
            if (table.name, column.name) in keys:
                proposals.append(ColumnPolicy(column=ref, ground=False))
                continue
            personal = _mentions(text, PERSONAL_WORDS) and not _mentions(
                text, THING_WORDS
            )
            if personal:
                proposals.append(
                    ColumnPolicy(column=ref, sensitivity=Sensitivity.PERSONAL)
                )
                continue
            too_many = (
                column.distinct_estimate is not None
                and column.distinct_estimate > GROUNDABLE_MAX_DISTINCT
            )
            proposals.append(ColumnPolicy(column=ref, ground=not too_many))
    return proposals
