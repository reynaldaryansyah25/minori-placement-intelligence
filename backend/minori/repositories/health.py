"""Database readiness adapter with sanitized operational logging."""

import logging

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class SqlAlchemyDatabaseProbe:
    def __init__(self, session: Session) -> None:
        self._session = session

    def is_ready(self) -> bool:
        try:
            return self._session.execute(text("SELECT 1")).scalar_one() == 1
        except SQLAlchemyError:
            logger.error("Database readiness query failed")
            return False
