"""Record the initial database revision without introducing business tables."""

revision: str = "foundation"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Alembic creates and records its own version table for this revision."""


def downgrade() -> None:
    """No application tables were created by this revision."""
