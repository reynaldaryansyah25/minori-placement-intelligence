"""Optional candidate contacts and immutable approved email snapshots."""

import sqlalchemy as sa
from alembic import context, op

revision = "ai_message_snapshots"
down_revision = "placement_reminders"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("vacancy_drafts", sa.Column("analysis_metadata", sa.JSON()))
    op.add_column("candidates", sa.Column("email", sa.String(254)))
    op.add_column(
        "candidates", sa.Column("email_verified", sa.Boolean(), nullable=False, server_default="0")
    )
    op.add_column(
        "candidates", sa.Column("email_consent", sa.Boolean(), nullable=False, server_default="0")
    )
    for column in (
        sa.Column("approved_message", sa.JSON()),
        sa.Column("approved_by", sa.String(80)),
        sa.Column("approved_at", sa.DateTime()),
        sa.Column("approval_fingerprint", sa.String(64)),
        sa.Column("manual_request_key", sa.String(80)),
    ):
        op.add_column("notifications", column)
    op.create_index(
        "ix_notifications_manual_request_key", "notifications", ["manual_request_key"], unique=True
    )


def downgrade():
    if context.is_offline_mode():
        raise RuntimeError("Refusing downgrade without inspecting stored AI/contact data")
    connection = op.get_bind()
    if (
        connection.scalar(
            sa.text(
                "SELECT count(*) FROM candidates WHERE email IS NOT NULL OR email_verified != 0 OR email_consent != 0"
            )
        )
        or connection.scalar(
            sa.text(
                "SELECT count(*) FROM notifications WHERE approved_message IS NOT NULL OR approved_by IS NOT NULL OR approved_at IS NOT NULL OR manual_request_key IS NOT NULL"
            )
        )
        or connection.scalar(
            sa.text("SELECT count(*) FROM vacancy_drafts WHERE analysis_metadata IS NOT NULL")
        )
    ):
        raise RuntimeError(
            "Refusing downgrade: stored contacts or approved AI/email history exists"
        )
    target = context.get_revision_argument()
    populated = connection.scalar(sa.text("SELECT count(*) FROM candidates")) or connection.scalar(
        sa.text("SELECT count(*) FROM vacancies")
    )
    if populated and target not in {down_revision, "explainable_matching", "placement_database"}:
        raise RuntimeError("Refusing downgrade below the supported legacy parent revisions")
    if (
        populated
        and target != down_revision
        and connection.scalar(sa.text("SELECT count(*) FROM notifications WHERE managed = 1"))
    ):
        raise RuntimeError("Refusing downgrade: managed reminder history exists")
    if (
        populated
        and target == "placement_database"
        and (
            connection.scalar(sa.text("SELECT count(*) FROM match_evaluations"))
            or connection.scalar(
                sa.text("SELECT count(*) FROM candidates WHERE preferred_prefectures != '[]'")
            )
            or connection.scalar(
                sa.text(
                    "SELECT count(*) FROM vacancies WHERE preferred_skills != '[]' OR preferred_certifications != '[]' OR language_test_max_age_months IS NOT NULL"
                )
            )
        )
    ):
        raise RuntimeError("Refusing downgrade: matching history or configured preferences exist")
    op.drop_index("ix_notifications_manual_request_key", table_name="notifications")
    for column in (
        "manual_request_key",
        "approval_fingerprint",
        "approved_at",
        "approved_by",
        "approved_message",
    ):
        op.drop_column("notifications", column)
    for column in ("email_consent", "email_verified", "email"):
        op.drop_column("candidates", column)
    op.drop_column("vacancy_drafts", "analysis_metadata")
