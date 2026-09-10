"""A registered datasource: how to reach it and which overlay describes it.

Credentials never appear here: ``dsn_env`` names the environment variable
that holds the connection string, so the registry can live in git while the
secret stays in the shell or the process environment.
"""

from __future__ import annotations

from pydantic import Field

from grepbit.domain.models import DomainModel

_IDENTIFIER = r"^[A-Za-z_][A-Za-z0-9_]*$"


class DatasourceRegistration(DomainModel):
    id: str = Field(pattern=_IDENTIFIER)
    dsn_env: str = Field(pattern=r"^[A-Z][A-Z0-9_]*$")
    overlay: str | None = None  # path, relative to the registry file
    schema_name: str = "public"
    business_timezone: str = "Asia/Taipei"
    enum_distinct_limit: int = Field(default=0, ge=0)
    description: str | None = None


class DatasourceRegistry(DomainModel):
    datasources: list[DatasourceRegistration] = Field(min_length=1)

    def get(self, datasource_id: str) -> DatasourceRegistration | None:
        return next((d for d in self.datasources if d.id == datasource_id), None)
