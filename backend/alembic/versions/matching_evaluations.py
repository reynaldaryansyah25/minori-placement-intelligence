"""Add evaluation history and matching inputs without rebuilding existing parent tables."""

import sqlalchemy as sa
from alembic import context, op

revision = "explainable_matching"
down_revision = "placement_database"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "candidates",
        sa.Column("preferred_prefectures", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "vacancies", sa.Column("preferred_skills", sa.JSON(), nullable=False, server_default="[]")
    )
    op.add_column(
        "vacancies",
        sa.Column("preferred_certifications", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "vacancies",
        sa.Column(
            "language_test_max_age_months",
            sa.Integer(),
            sa.CheckConstraint(
                "language_test_max_age_months IS NULL OR language_test_max_age_months > 0",
                name=op.f("ck_vacancies_positive_language_age"),
            ),
            nullable=True,
        ),
    )
    op.create_table(
        "match_evaluations",
        sa.Column("id", sa.Uuid(native_uuid=False), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column("candidate_id", sa.Uuid(native_uuid=False), nullable=False),
        sa.Column("vacancy_id", sa.Uuid(native_uuid=False), nullable=False),
        sa.Column(
            "eligibility_status",
            sa.Enum(
                "ELIGIBLE",
                "NOT_ELIGIBLE",
                "NEEDS_REVIEW",
                name="evaluation_eligibility",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("total_score", sa.Double(), nullable=True),
        sa.Column("algorithm_version", sa.String(80), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(), nullable=False),
        sa.Column("input_fingerprint", sa.String(64), nullable=False),
        sa.Column("explanation", sa.JSON(), nullable=False),
        sa.CheckConstraint(
            "total_score IS NULL OR (total_score >= 0 AND total_score <= 1)",
            name=op.f("ck_match_evaluations_evaluation_score_range"),
        ),
        sa.CheckConstraint(
            "(eligibility_status = 'ELIGIBLE' AND total_score IS NOT NULL) OR "
            "(eligibility_status != 'ELIGIBLE' AND total_score IS NULL)",
            name=op.f("ck_match_evaluations_eligibility_score"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_match_evaluations")),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["candidates.id"],
            ondelete="RESTRICT",
            name=op.f("fk_match_evaluations_candidate_id_candidates"),
        ),
        sa.ForeignKeyConstraint(
            ["vacancy_id"],
            ["vacancies.id"],
            ondelete="RESTRICT",
            name=op.f("fk_match_evaluations_vacancy_id_vacancies"),
        ),
        sa.UniqueConstraint(
            "candidate_id",
            "vacancy_id",
            "input_fingerprint",
            "evaluated_at",
            "algorithm_version",
            name="uq_match_evaluations_input_time",
        ),
    )
    op.create_index(
        "ix_match_evaluations_pair_time",
        "match_evaluations",
        ["candidate_id", "vacancy_id", "evaluated_at"],
    )
    op.create_index(
        "ix_match_evaluations_vacancy_eligibility",
        "match_evaluations",
        ["vacancy_id", "eligibility_status"],
    )


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("Refusing downgrade without inspecting stored matching data")
    connection = op.get_bind()
    legacy_tables = (
        "candidates",
        "candidate_language_tests",
        "candidate_certifications",
        "candidate_experiences",
        "vacancies",
        "vacancy_language_requirements",
        "vacancy_drafts",
        "matches",
        "placements",
        "placement_stages",
        "notifications",
        "notification_attempts",
        "audit_logs",
    )
    # SQLite DDL is not rolled back if a later migration refuses a deeper downgrade.
    # Require the explicit parent target when legacy rows exist, before changing any schema.
    if context.get_revision_argument() != down_revision and any(
        connection.scalar(sa.text(f"SELECT count(*) FROM {table}")) for table in legacy_tables
    ):
        raise RuntimeError("Refusing downgrade below placement_database while business rows exist")
    if (
        connection.scalar(sa.text("SELECT count(*) FROM match_evaluations"))
        or connection.scalar(
            sa.text("SELECT count(*) FROM candidates WHERE preferred_prefectures != '[]'")
        )
        or connection.scalar(
            sa.text(
                "SELECT count(*) FROM vacancies WHERE preferred_skills != '[]' "
                "OR preferred_certifications != '[]' OR language_test_max_age_months IS NOT NULL"
            )
        )
    ):
        raise RuntimeError("Refusing downgrade: matching history or configured preferences exist")
    op.drop_table("match_evaluations")
    op.drop_column("vacancies", "language_test_max_age_months")
    op.drop_column("vacancies", "preferred_certifications")
    op.drop_column("vacancies", "preferred_skills")
    op.drop_column("candidates", "preferred_prefectures")
