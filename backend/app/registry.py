"""Domain registry for routers and orchestration. app.core never imports this.

Kept out of app/domains/__init__.py on purpose: importing a domain package (as the
screen engine does) must not drag in extraction, the LLM client, or the database.
"""

from app.core.extraction import FieldSpec
from app.domains import interconnection
from app.domains.interconnection.extraction_fields import FIELDS as INTERCONNECTION_FIELDS

DOCUMENT_KINDS: dict[str, frozenset[str]] = {
    interconnection.DOMAIN: frozenset(k.value for k in interconnection.DocumentKind),
}

EXTRACTION_FIELDS: dict[str, tuple[FieldSpec, ...]] = {
    interconnection.DOMAIN: INTERCONNECTION_FIELDS,
}
