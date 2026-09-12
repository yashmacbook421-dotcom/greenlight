"""Domain registry. Routers may import domains; app.core never does."""

from app.domains import interconnection

DOCUMENT_KINDS: dict[str, frozenset[str]] = {
    interconnection.DOMAIN: frozenset(k.value for k in interconnection.DocumentKind),
}
