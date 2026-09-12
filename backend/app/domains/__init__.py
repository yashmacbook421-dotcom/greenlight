"""Domain registry. Routers may import domains; app.core never does."""

from app.core.extraction import FieldSpec
from app.domains import interconnection
from app.domains.interconnection.extraction_fields import FIELDS as INTERCONNECTION_FIELDS

DOCUMENT_KINDS: dict[str, frozenset[str]] = {
    interconnection.DOMAIN: frozenset(k.value for k in interconnection.DocumentKind),
}

EXTRACTION_FIELDS: dict[str, tuple[FieldSpec, ...]] = {
    interconnection.DOMAIN: INTERCONNECTION_FIELDS,
}
