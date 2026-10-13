"""Extend existing administrative models for reliable reminders, preserving legacy rows."""

import sqlalchemy as sa
from alembic import context, op

revision = "placement_reminders"
down_revision = "explainable_matching"
branch_labels = None
depends_on = None

NOTIFICATION_COLUMNS = (
    sa.Column("managed", sa.Boolean(), server_default="0", nullable=False),
    sa.Column("dry_run", sa.Boolean(), server_default="1", nullable=False),
    sa.Column("available_at", sa.DateTime(), nullable=True),
    sa.Column("event_at", sa.DateTime(), nullable=True),
    sa.Column("schedule_revision", sa.Integer(), server_default="1", nullable=False),
    sa.Column("schedule_context", sa.JSON(), server_default="{}", nullable=False),
    sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
    sa.Column("max_attempts", sa.Integer(), server_default="3", nullable=False),
    sa.Column("claimed_at", sa.DateTime(), nullable=True),
    sa.Column("lease_expires_at", sa.DateTime(), nullable=True),
    sa.Column("claim_token_hash", sa.String(64), nullable=True),
    sa.Column("processed_at", sa.DateTime(), nullable=True),
    sa.Column("last_error_code", sa.String(64), nullable=True),
)


def activity_table():
    """Freeze all original constraints; legacy duplicate names cannot round-trip reflection."""
    metadata = sa.MetaData()
    sa.Table("placements", metadata, sa.Column("id", sa.Uuid(native_uuid=False), primary_key=True))
    return sa.Table(
        "placement_stages",
        metadata,
        sa.Column("id", sa.Uuid(native_uuid=False), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column("placement_id", sa.Uuid(native_uuid=False), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("step_type", sa.String(13), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(11), nullable=False),
        sa.Column("scheduled_at", sa.DateTime()),
        sa.Column("due_at", sa.DateTime()),
        sa.Column("completed_at", sa.DateTime()),
        sa.Column("location", sa.String(160)),
        sa.ForeignKeyConstraint(
            ["placement_id"],
            ["placements.id"],
            ondelete="RESTRICT",
            name="fk_placement_stages_placement_id_placements",
        ),
        sa.UniqueConstraint("placement_id", "code", name="uq_placement_stages_code"),
        sa.UniqueConstraint("placement_id", "sequence_number", name="uq_placement_stages_sequence"),
        sa.UniqueConstraint("id", "placement_id", name="uq_placement_stages_owner"),
        sa.CheckConstraint("sequence_number > 0", name="ck_placement_stages_positive_sequence"),
        sa.CheckConstraint("length(trim(code)) > 0", name="ck_placement_stages_code_not_blank"),
        sa.CheckConstraint(
            "due_at IS NULL OR (scheduled_at IS NOT NULL AND due_at >= scheduled_at)",
            name="ck_placement_stages_schedule_range",
        ),
        sa.CheckConstraint(
            "status NOT IN ('scheduled','in_progress') OR scheduled_at IS NOT NULL",
            name="ck_placement_stages_scheduled_status",
        ),
        sa.CheckConstraint(
            "(status = 'completed' AND completed_at IS NOT NULL) OR "
            "(status != 'completed' AND completed_at IS NULL)",
            name="ck_placement_stages_completion_timestamp",
        ),
        sa.CheckConstraint(
            "completed_at IS NULL OR scheduled_at IS NULL OR completed_at >= scheduled_at",
            name="ck_placement_stages_completion_range",
        ),
        sa.CheckConstraint(
            "step_type IN ('interview','medical_check','documents','orientation','departure')",
            name="ck_placement_stages_step_type",
        ),
        sa.CheckConstraint(
            "status IN ('pending','scheduled','in_progress','completed','cancelled')",
            name="ck_placement_stages_step_status",
        ),
        sa.Index("ix_placement_stages_placement_id", "placement_id"),
        sa.Index("ix_placement_stages_status_scheduled_at", "status", "scheduled_at"),
    )


def replace_check(batch, table, name, expression):
    batch.drop_constraint(op.f(f"ck_{table}_{name}"), type_="check")
    batch.create_check_constraint(op.f(f"ck_{table}_{name}"), expression)


def upgrade():
    if context.is_offline_mode():
        raise RuntimeError("Reminder migration requires an online SQLite connection")
    with op.batch_alter_table("audit_logs") as batch:
        batch.alter_column("entity_type", existing_type=sa.String(12), type_=sa.String(15))
        replace_check(
            batch,
            "audit_logs",
            "audit_entity_type",
            "entity_type IN ('candidate','vacancy','placement','notification',"
            "'match','placement_stage')",
        )
    with op.batch_alter_table("notification_attempts") as batch:
        batch.add_column(sa.Column("claim_token_hash", sa.String(64), nullable=True))
        batch.create_unique_constraint(
            "uq_notification_attempts_claim_token_hash", ["claim_token_hash"]
        )
        batch.alter_column("status", existing_type=sa.String(9), type_=sa.String(10))
        batch.alter_column("finished_at", existing_type=sa.DateTime(), nullable=True)
        replace_check(
            batch,
            "notification_attempts",
            "attempt_status",
            "status IN ('succeeded','failed','processing','simulated','abandoned')",
        )
        replace_check(
            batch,
            "notification_attempts",
            "attempt_range",
            "finished_at IS NULL OR finished_at >= attempted_at",
        )
        replace_check(
            batch,
            "notification_attempts",
            "error_status",
            "(status IN ('succeeded','simulated','processing') AND error_code IS NULL) OR "
            "(status IN ('failed','abandoned') AND error_code IS NOT NULL)",
        )
        batch.create_check_constraint(
            op.f("ck_notification_attempts_attempt_finish"),
            "(status = 'processing' AND finished_at IS NULL) OR "
            "(status != 'processing' AND finished_at IS NOT NULL)",
        )
    with op.batch_alter_table("notifications") as batch:
        for column in NOTIFICATION_COLUMNS:
            batch.add_column(column)
        batch.alter_column("status", existing_type=sa.String(9), type_=sa.String(10))
        replace_check(
            batch,
            "notifications",
            "notification_status",
            "status IN ('pending','sent','failed','cancelled','processing','simulated','missed')",
        )
        batch.create_check_constraint(
            op.f("ck_notifications_queue_counters"),
            "schedule_revision > 0 AND attempt_count >= 0 AND max_attempts > 0",
        )
        batch.create_check_constraint(
            op.f("ck_notifications_claim_state"),
            "(status = 'processing' AND claimed_at IS NOT NULL AND lease_expires_at > claimed_at "
            "AND claim_token_hash IS NOT NULL) OR (status != 'processing' "
            "AND claimed_at IS NULL AND lease_expires_at IS NULL)",
        )
        batch.create_check_constraint(
            op.f("ck_notifications_managed_schedule"),
            "managed = 0 OR (event_at IS NOT NULL AND available_at IS NOT NULL "
            "AND placement_stage_id IS NOT NULL)",
        )
        batch.create_index("ix_notifications_queue_due", ["managed", "status", "available_at"])
    with op.batch_alter_table("placement_stages", copy_from=activity_table()) as batch:
        batch.add_column(
            sa.Column("schedule_revision", sa.Integer(), server_default="1", nullable=False)
        )
        batch.create_check_constraint(
            op.f("ck_placement_stages_positive_schedule_revision"), "schedule_revision > 0"
        )


def downgrade():
    if context.is_offline_mode():
        raise RuntimeError("Refusing downgrade without inspecting reminder data")
    connection = op.get_bind()
    target = context.get_revision_argument()
    dirty = (
        "SELECT count(*) FROM notifications WHERE managed = 1 OR attempt_count != 0 "
        "OR status NOT IN ('pending','sent','failed','cancelled')",
        "SELECT count(*) FROM notification_attempts WHERE claim_token_hash IS NOT NULL "
        "OR status NOT IN ('succeeded','failed')",
        "SELECT count(*) FROM placement_stages WHERE schedule_revision != 1",
        "SELECT count(*) FROM audit_logs WHERE entity_type IN ('match','placement_stage')",
    )
    if any(connection.scalar(sa.text(query)) for query in dirty):
        raise RuntimeError("Refusing downgrade: reminder or staff decision history exists")
    if target != down_revision:
        if target != "placement_database" and connection.scalar(
            sa.text("SELECT count(*) FROM candidates")
        ):
            raise RuntimeError("Refusing downgrade below populated business schema")
        if connection.scalar(sa.text("SELECT count(*) FROM match_evaluations")):
            raise RuntimeError("Refusing downgrade: matching history exists")
    with op.batch_alter_table("placement_stages") as batch:
        batch.drop_constraint(op.f("ck_placement_stages_positive_schedule_revision"), type_="check")
        batch.drop_column("schedule_revision")
    with op.batch_alter_table("notifications") as batch:
        batch.drop_index("ix_notifications_queue_due")
        for name in ("queue_counters", "claim_state", "managed_schedule"):
            batch.drop_constraint(op.f(f"ck_notifications_{name}"), type_="check")
        replace_check(
            batch,
            "notifications",
            "notification_status",
            "status IN ('pending','sent','failed','cancelled')",
        )
        batch.alter_column("status", existing_type=sa.String(10), type_=sa.String(9))
        for column in reversed(NOTIFICATION_COLUMNS):
            batch.drop_column(column.name)
    with op.batch_alter_table("notification_attempts") as batch:
        batch.drop_constraint("uq_notification_attempts_claim_token_hash", type_="unique")
        batch.drop_constraint(op.f("ck_notification_attempts_attempt_finish"), type_="check")
        replace_check(
            batch, "notification_attempts", "attempt_status", "status IN ('succeeded','failed')"
        )
        replace_check(
            batch, "notification_attempts", "attempt_range", "finished_at >= attempted_at"
        )
        replace_check(
            batch,
            "notification_attempts",
            "error_status",
            "(status = 'succeeded' AND error_code IS NULL) OR "
            "(status = 'failed' AND error_code IS NOT NULL)",
        )
        batch.alter_column("finished_at", existing_type=sa.DateTime(), nullable=False)
        batch.alter_column("status", existing_type=sa.String(10), type_=sa.String(9))
        batch.drop_column("claim_token_hash")
    with op.batch_alter_table("audit_logs") as batch:
        replace_check(
            batch,
            "audit_logs",
            "audit_entity_type",
            "entity_type IN ('candidate','vacancy','placement','notification')",
        )
        batch.alter_column("entity_type", existing_type=sa.String(15), type_=sa.String(12))
