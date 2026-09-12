from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.config import settings
from app.core.storage import LocalStorage
from app.db import get_session


def get_storage() -> LocalStorage:
    return LocalStorage(settings.storage_dir)


SessionDep = Annotated[Session, Depends(get_session)]
StorageDep = Annotated[LocalStorage, Depends(get_storage)]
