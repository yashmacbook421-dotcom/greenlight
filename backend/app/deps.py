from typing import Annotated

import anthropic
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.core.llm import MessagesClient, default_client
from app.core.storage import LocalStorage
from app.db import get_session


def get_storage() -> LocalStorage:
    return LocalStorage(settings.storage_dir)


def get_llm_client() -> MessagesClient:
    try:
        return default_client()
    except anthropic.AnthropicError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, f"Claude API is not configured: {exc}") from exc


def get_optional_llm_client() -> MessagesClient | None:
    """The review pipeline degrades to deterministic drafting when Claude is not configured."""
    try:
        return default_client()
    except anthropic.AnthropicError:
        return None


SessionDep = Annotated[Session, Depends(get_session)]
OptionalLLMDep = Annotated[MessagesClient | None, Depends(get_optional_llm_client)]
LLMDep = Annotated[MessagesClient, Depends(get_llm_client)]
StorageDep = Annotated[LocalStorage, Depends(get_storage)]
