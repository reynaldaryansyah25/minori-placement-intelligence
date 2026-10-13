"""business_tables

Revision ID: placement_database
Revises: foundation
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op

revision: str = "placement_database"
down_revision: str | Sequence[str] | None = "foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_logs",
        sa.Column("actor_reference", sa.String(length=80), nullable=False),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column(
            "entity_type",
            sa.Enum(
                "candidate",
                "vacancy",
                "placement",
                "notification",
                name="audit_entity_type",
                native_enum=False,
                create_constraint=False,
            ),
            nullable=False,
        ),
        sa.Column("entity_id", sa.Uuid(native_uuid=False), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("context", sa.JSON(), nullable=False),
        sa.Column("reference", sa.String(length=64), nullable=False),
        sa.Column("id", sa.Uuid(native_uuid=False), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "entity_type IN ('candidate', 'vacancy', 'placement', 'notification')",
            name=op.f("ck_audit_logs_audit_entity_type"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_logs")),
        sa.UniqueConstraint("reference", name=op.f("uq_audit_logs_reference")),
    )
    with op.batch_alter_table("audit_logs", schema=None) as batch_op:
        batch_op.create_index(
            "ix_audit_logs_entity_time", ["entity_type", "entity_id", "occurred_at"], unique=False
        )

    op.create_table(
        "candidates",
        sa.Column("full_name", sa.String(length=160), nullable=False),
        sa.Column(
            "preferred_program",
            sa.Enum(
                "titp",
                "ssw",
                "engineer",
                name="candidate_program",
                native_enum=False,
                create_constraint=False,
            ),
            nullable=False,
        ),
        sa.Column("education_level", sa.String(length=80), nullable=False),
        sa.Column("domicile_city", sa.String(length=80), nullable=False),
        sa.Column("skills", sa.JSON(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "registered",
                "preparing",
                "ready",
                "inactive",
                name="candidate_status",
                native_enum=False,
                create_constraint=False,
            ),
            nullable=False,
        ),
        sa.Column("reference", sa.String(length=64), nullable=False),
        sa.Column("id", sa.Uuid(native_uuid=False), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "preferred_program IN ('titp', 'ssw', 'engineer')",
            name=op.f("ck_candidates_candidate_program"),
        ),
        sa.CheckConstraint(
            "status IN ('registered', 'preparing', 'ready', 'inactive')",
            name=op.f("ck_candidates_candidate_status"),
        ),
        sa.CheckConstraint(
            "length(trim(full_name)) > 0", name=op.f("ck_candidates_full_name_not_blank")
        ),
        sa.CheckConstraint(
            "length(trim(reference)) > 0", name=op.f("ck_candidates_reference_not_blank")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_candidates")),
        sa.UniqueConstraint("reference", name=op.f("uq_candidates_reference")),
    )
    with op.batch_alter_table("candidates", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_candidates_preferred_program"), ["preferred_program"], unique=False
        )
        batch_op.create_index(batch_op.f("ix_candidates_status"), ["status"], unique=False)

    op.create_table(
        "vacancies",
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("employer_name", sa.String(length=160), nullable=False),
        sa.Column(
            "program",
            sa.Enum(
                "titp",
                "ssw",
                "engineer",
                name="vacancy_program",
                native_enum=False,
                create_constraint=False,
            ),
            nullable=False,
        ),
        sa.Column("sector", sa.String(length=80), nullable=False),
        sa.Column("prefecture", sa.String(length=80), nullable=False),
        sa.Column("quota", sa.Integer(), nullable=False),
        sa.Column("minimum_experience_months", sa.Integer(), nullable=False),
        sa.Column("required_skills", sa.JSON(), nullable=False),
        sa.Column("required_certifications", sa.JSON(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "open",
                "paused",
                "closed",
                name="vacancy_status",
                native_enum=False,
                create_constraint=False,
            ),
            nullable=False,
        ),
        sa.Column("application_deadline", sa.DateTime(), nullable=True),
        sa.Column("reference", sa.String(length=64), nullable=False),
        sa.Column("id", sa.Uuid(native_uuid=False), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "program IN ('titp', 'ssw', 'engineer')", name=op.f("ck_vacancies_vacancy_program")
        ),
        sa.CheckConstraint(
            "status IN ('open', 'paused', 'closed')", name=op.f("ck_vacancies_vacancy_status")
        ),
        sa.CheckConstraint(
            "length(trim(reference)) > 0", name=op.f("ck_vacancies_reference_not_blank")
        ),
        sa.CheckConstraint("length(trim(title)) > 0", name=op.f("ck_vacancies_title_not_blank")),
        sa.CheckConstraint(
            "minimum_experience_months >= 0", name=op.f("ck_vacancies_nonnegative_experience")
        ),
        sa.CheckConstraint("quota > 0", name=op.f("ck_vacancies_positive_quota")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_vacancies")),
        sa.UniqueConstraint("reference", name=op.f("uq_vacancies_reference")),
    )
    with op.batch_alter_table("vacancies", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_vacancies_application_deadline"), ["application_deadline"], unique=False
        )
        batch_op.create_index(batch_op.f("ix_vacancies_program"), ["program"], unique=False)
        batch_op.create_index(batch_op.f("ix_vacancies_sector"), ["sector"], unique=False)
        batch_op.create_index(batch_op.f("ix_vacancies_status"), ["status"], unique=False)

    op.create_table(
        "candidate_certifications",
        sa.Column("candidate_id", sa.Uuid(native_uuid=False), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("issuer", sa.String(length=160), nullable=False),
        sa.Column("issued_on", sa.Date(), nullable=False),
        sa.Column("expires_on", sa.Date(), nullable=True),
        sa.Column("id", sa.Uuid(native_uuid=False), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "expires_on IS NULL OR expires_on >= issued_on",
            name=op.f("ck_candidate_certifications_validity_range"),
        ),
        sa.CheckConstraint(
            "length(trim(code)) > 0", name=op.f("ck_candidate_certifications_code_not_blank")
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["candidates.id"],
            name=op.f("fk_candidate_certifications_candidate_id_candidates"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_candidate_certifications")),
        sa.UniqueConstraint(
            "candidate_id",
            "code",
            "issued_on",
            name=op.f("uq_candidate_certifications_candidate_id"),
        ),
    )
    with op.batch_alter_table("candidate_certifications", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_candidate_certifications_candidate_id"), ["candidate_id"], unique=False
        )

    op.create_table(
        "candidate_experiences",
        sa.Column("candidate_id", sa.Uuid(native_uuid=False), nullable=False),
        sa.Column("employer_name", sa.String(length=160), nullable=False),
        sa.Column("sector", sa.String(length=80), nullable=False),
        sa.Column("role", sa.String(length=120), nullable=False),
        sa.Column("started_on", sa.Date(), nullable=False),
        sa.Column("ended_on", sa.Date(), nullable=True),
        sa.Column("id", sa.Uuid(native_uuid=False), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "ended_on IS NULL OR ended_on >= started_on",
            name=op.f("ck_candidate_experiences_employment_range"),
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["candidates.id"],
            name=op.f("fk_candidate_experiences_candidate_id_candidates"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_candidate_experiences")),
        sa.UniqueConstraint(
            "candidate_id",
            "employer_name",
            "role",
            "started_on",
            name=op.f("uq_candidate_experiences_candidate_id"),
        ),
    )
    with op.batch_alter_table("candidate_experiences", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_candidate_experiences_candidate_id"), ["candidate_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_candidate_experiences_sector"), ["sector"], unique=False
        )

    op.create_table(
        "candidate_language_tests",
        sa.Column("candidate_id", sa.Uuid(native_uuid=False), nullable=False),
        sa.Column(
            "test_type",
            sa.Enum(
                "jlpt",
                "jft_basic",
                name="language_test_type",
                native_enum=False,
                create_constraint=False,
            ),
            nullable=False,
        ),
        sa.Column("level", sa.String(length=8), nullable=False),
        sa.Column("taken_on", sa.Date(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("id", sa.Uuid(native_uuid=False), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(test_type = 'jlpt' AND level IN ('N1','N2','N3','N4','N5')) OR"
            "(test_type = 'jft_basic' AND level IN ('A1','A2.1','A2.2'))",
            name=op.f("ck_candidate_language_tests_test_level_pair"),
        ),
        sa.CheckConstraint(
            "score IS NULL OR"
            "(test_type = 'jlpt' AND score BETWEEN 0 AND 180) OR"
            "(test_type = 'jft_basic' AND score BETWEEN 10 AND 250)",
            name=op.f("ck_candidate_language_tests_score_range"),
        ),
        sa.CheckConstraint(
            "test_type IN ('jlpt', 'jft_basic')",
            name=op.f("ck_candidate_language_tests_language_test_type"),
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["candidates.id"],
            name=op.f("fk_candidate_language_tests_candidate_id_candidates"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_candidate_language_tests")),
        sa.UniqueConstraint(
            "candidate_id",
            "test_type",
            "taken_on",
            name=op.f("uq_candidate_language_tests_candidate_id"),
        ),
    )
    with op.batch_alter_table("candidate_language_tests", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_candidate_language_tests_candidate_id"), ["candidate_id"], unique=False
        )

    op.create_table(
        "matches",
        sa.Column("candidate_id", sa.Uuid(native_uuid=False), nullable=False),
        sa.Column("vacancy_id", sa.Uuid(native_uuid=False), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "proposed",
                "approved",
                "rejected",
                name="match_status",
                native_enum=False,
                create_constraint=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "source",
            sa.Enum(
                "manual", "import", name="match_source", native_enum=False, create_constraint=False
            ),
            nullable=False,
        ),
        sa.Column("score", sa.Double(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Uuid(native_uuid=False), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(status = 'proposed' AND reviewed_at IS NULL) OR"
            "(status IN ('approved','rejected') AND reviewed_at IS NOT NULL)",
            name=op.f("ck_matches_review_timestamp"),
        ),
        sa.CheckConstraint("source IN ('manual', 'import')", name=op.f("ck_matches_match_source")),
        sa.CheckConstraint(
            "status IN ('proposed', 'approved', 'rejected')", name=op.f("ck_matches_match_status")
        ),
        sa.CheckConstraint(
            "score IS NULL OR (score >= 0 AND score <= 1)", name=op.f("ck_matches_score_range")
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["candidates.id"],
            name=op.f("fk_matches_candidate_id_candidates"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["vacancy_id"],
            ["vacancies.id"],
            name=op.f("fk_matches_vacancy_id_vacancies"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_matches")),
        sa.UniqueConstraint("candidate_id", "vacancy_id", name=op.f("uq_matches_candidate_id")),
        sa.UniqueConstraint("id", "candidate_id", "vacancy_id", name=op.f("uq_matches_id")),
    )
    with op.batch_alter_table("matches", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_matches_candidate_id"), ["candidate_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_matches_status"), ["status"], unique=False)
        batch_op.create_index(batch_op.f("ix_matches_vacancy_id"), ["vacancy_id"], unique=False)

    op.create_table(
        "vacancy_drafts",
        sa.Column("source_channel", sa.String(length=80), nullable=False),
        sa.Column("source_reference", sa.String(length=120), nullable=False),
        sa.Column("proposed_data", sa.JSON(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "draft",
                "review",
                "published",
                "rejected",
                name="draft_status",
                native_enum=False,
                create_constraint=False,
            ),
            nullable=False,
        ),
        sa.Column("published_vacancy_id", sa.Uuid(native_uuid=False), nullable=True),
        sa.Column("reference", sa.String(length=64), nullable=False),
        sa.Column("id", sa.Uuid(native_uuid=False), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(status = 'published' AND published_vacancy_id IS NOT NULL) OR"
            "(status != 'published' AND published_vacancy_id IS NULL)",
            name=op.f("ck_vacancy_drafts_publication_link"),
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'review', 'published', 'rejected')",
            name=op.f("ck_vacancy_drafts_draft_status"),
        ),
        sa.ForeignKeyConstraint(
            ["published_vacancy_id"],
            ["vacancies.id"],
            name=op.f("fk_vacancy_drafts_published_vacancy_id_vacancies"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_vacancy_drafts")),
        sa.UniqueConstraint(
            "published_vacancy_id", name=op.f("uq_vacancy_drafts_published_vacancy_id")
        ),
        sa.UniqueConstraint("reference", name=op.f("uq_vacancy_drafts_reference")),
        sa.UniqueConstraint(
            "source_channel", "source_reference", name=op.f("uq_vacancy_drafts_source_channel")
        ),
    )
    with op.batch_alter_table("vacancy_drafts", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_vacancy_drafts_status"), ["status"], unique=False)

    op.create_table(
        "vacancy_language_requirements",
        sa.Column("vacancy_id", sa.Uuid(native_uuid=False), nullable=False),
        sa.Column(
            "test_type",
            sa.Enum(
                "jlpt",
                "jft_basic",
                name="requirement_test_type",
                native_enum=False,
                create_constraint=False,
            ),
            nullable=False,
        ),
        sa.Column("minimum_level", sa.String(length=8), nullable=False),
        sa.Column("id", sa.Uuid(native_uuid=False), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(test_type = 'jlpt' AND minimum_level IN ('N1','N2','N3','N4','N5')) OR"
            "(test_type = 'jft_basic' AND minimum_level IN ('A1','A2.1','A2.2'))",
            name=op.f("ck_vacancy_language_requirements_test_level_pair"),
        ),
        sa.CheckConstraint(
            "test_type IN ('jlpt', 'jft_basic')",
            name=op.f("ck_vacancy_language_requirements_requirement_test_type"),
        ),
        sa.ForeignKeyConstraint(
            ["vacancy_id"],
            ["vacancies.id"],
            name=op.f("fk_vacancy_language_requirements_vacancy_id_vacancies"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_vacancy_language_requirements")),
        sa.UniqueConstraint(
            "vacancy_id", "test_type", name=op.f("uq_vacancy_language_requirements_vacancy_id")
        ),
    )
    with op.batch_alter_table("vacancy_language_requirements", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_vacancy_language_requirements_vacancy_id"), ["vacancy_id"], unique=False
        )

    op.create_table(
        "placements",
        sa.Column("candidate_id", sa.Uuid(native_uuid=False), nullable=False),
        sa.Column("vacancy_id", sa.Uuid(native_uuid=False), nullable=False),
        sa.Column("match_id", sa.Uuid(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "preparing",
                "in_progress",
                "completed",
                "cancelled",
                name="placement_status",
                native_enum=False,
                create_constraint=False,
            ),
            nullable=False,
        ),
        sa.Column("planned_departure_at", sa.DateTime(), nullable=True),
        sa.Column("actual_departure_at", sa.DateTime(), nullable=True),
        sa.Column("reference", sa.String(length=64), nullable=False),
        sa.Column("id", sa.Uuid(native_uuid=False), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('preparing', 'in_progress', 'completed', 'cancelled')",
            name=op.f("ck_placements_placement_status"),
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["candidates.id"],
            name=op.f("fk_placements_candidate_id_candidates"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["match_id", "candidate_id", "vacancy_id"],
            ["matches.id", "matches.candidate_id", "matches.vacancy_id"],
            name="fk_placements_match_pair",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["vacancy_id"],
            ["vacancies.id"],
            name=op.f("fk_placements_vacancy_id_vacancies"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_placements")),
        sa.UniqueConstraint("candidate_id", "vacancy_id", name=op.f("uq_placements_candidate_id")),
        sa.UniqueConstraint("id", "candidate_id", name=op.f("uq_placements_id")),
        sa.UniqueConstraint("reference", name=op.f("uq_placements_reference")),
    )
    with op.batch_alter_table("placements", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_placements_candidate_id"), ["candidate_id"], unique=False
        )
        batch_op.create_index(batch_op.f("ix_placements_match_id"), ["match_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_placements_status"), ["status"], unique=False)
        batch_op.create_index(batch_op.f("ix_placements_vacancy_id"), ["vacancy_id"], unique=False)

    op.create_table(
        "placement_stages",
        sa.Column("placement_id", sa.Uuid(native_uuid=False), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column(
            "step_type",
            sa.Enum(
                "interview",
                "medical_check",
                "documents",
                "orientation",
                "departure",
                name="step_type",
                native_enum=False,
                create_constraint=False,
            ),
            nullable=False,
        ),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "scheduled",
                "in_progress",
                "completed",
                "cancelled",
                name="step_status",
                native_enum=False,
                create_constraint=False,
            ),
            nullable=False,
        ),
        sa.Column("scheduled_at", sa.DateTime(), nullable=True),
        sa.Column("due_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("location", sa.String(length=160), nullable=True),
        sa.Column("id", sa.Uuid(native_uuid=False), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(status = 'completed' AND completed_at IS NOT NULL) OR"
            "(status != 'completed' AND completed_at IS NULL)",
            name=op.f("ck_placement_stages_completion_timestamp"),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'scheduled', 'in_progress', 'completed', 'cancelled')",
            name=op.f("ck_placement_stages_step_status"),
        ),
        sa.CheckConstraint(
            "status NOT IN ('scheduled','in_progress') OR scheduled_at IS NOT NULL",
            name=op.f("ck_placement_stages_scheduled_status"),
        ),
        sa.CheckConstraint(
            "step_type IN ('interview', 'medical_check', 'documents', 'orientation', 'departure')",
            name=op.f("ck_placement_stages_step_type"),
        ),
        sa.CheckConstraint(
            "completed_at IS NULL OR scheduled_at IS NULL OR completed_at >= scheduled_at",
            name=op.f("ck_placement_stages_completion_range"),
        ),
        sa.CheckConstraint(
            "due_at IS NULL OR (scheduled_at IS NOT NULL AND due_at >= scheduled_at)",
            name=op.f("ck_placement_stages_schedule_range"),
        ),
        sa.CheckConstraint(
            "length(trim(code)) > 0", name=op.f("ck_placement_stages_code_not_blank")
        ),
        sa.CheckConstraint(
            "sequence_number > 0", name=op.f("ck_placement_stages_positive_sequence")
        ),
        sa.ForeignKeyConstraint(
            ["placement_id"],
            ["placements.id"],
            name=op.f("fk_placement_stages_placement_id_placements"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_placement_stages")),
        sa.UniqueConstraint("id", "placement_id", name=op.f("uq_placement_stages_id")),
        sa.UniqueConstraint("placement_id", "code", name=op.f("uq_placement_stages_placement_id")),
        sa.UniqueConstraint(
            "placement_id", "sequence_number", name=op.f("uq_placement_stages_placement_id")
        ),
    )
    with op.batch_alter_table("placement_stages", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_placement_stages_placement_id"), ["placement_id"], unique=False
        )
        batch_op.create_index(
            "ix_placement_stages_status_scheduled_at", ["status", "scheduled_at"], unique=False
        )

    op.create_table(
        "notifications",
        sa.Column("deduplication_key", sa.String(length=160), nullable=False),
        sa.Column("candidate_id", sa.Uuid(native_uuid=False), nullable=False),
        sa.Column("placement_id", sa.Uuid(), nullable=True),
        sa.Column("placement_stage_id", sa.Uuid(), nullable=True),
        sa.Column("template_code", sa.String(length=80), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(), nullable=False),
        sa.Column(
            "channel",
            sa.Enum(
                "internal",
                "email",
                "whatsapp",
                name="notification_channel",
                native_enum=False,
                create_constraint=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "sent",
                "failed",
                "cancelled",
                name="notification_status",
                native_enum=False,
                create_constraint=False,
            ),
            nullable=False,
        ),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("reference", sa.String(length=64), nullable=False),
        sa.Column("id", sa.Uuid(native_uuid=False), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(status = 'sent' AND sent_at IS NOT NULL) OR (status != 'sent' AND sent_at IS NULL)",
            name=op.f("ck_notifications_sent_timestamp"),
        ),
        sa.CheckConstraint(
            "channel IN ('internal', 'email', 'whatsapp')",
            name=op.f("ck_notifications_notification_channel"),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'sent', 'failed', 'cancelled')",
            name=op.f("ck_notifications_notification_status"),
        ),
        sa.CheckConstraint(
            "placement_stage_id IS NULL OR placement_id IS NOT NULL",
            name=op.f("ck_notifications_step_parent"),
        ),
        sa.CheckConstraint(
            "sent_at IS NULL OR sent_at >= scheduled_at", name=op.f("ck_notifications_sent_range")
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["candidates.id"],
            name=op.f("fk_notifications_candidate_id_candidates"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["placement_id", "candidate_id"],
            ["placements.id", "placements.candidate_id"],
            name="fk_notifications_placement_candidate",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["placement_stage_id", "placement_id"],
            ["placement_stages.id", "placement_stages.placement_id"],
            name="fk_notifications_step_placement",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notifications")),
        sa.UniqueConstraint("deduplication_key", name=op.f("uq_notifications_deduplication_key")),
        sa.UniqueConstraint("reference", name=op.f("uq_notifications_reference")),
    )
    with op.batch_alter_table("notifications", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_notifications_candidate_id"), ["candidate_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_notifications_placement_id"), ["placement_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_notifications_placement_stage_id"), ["placement_stage_id"], unique=False
        )
        batch_op.create_index(
            "ix_notifications_status_scheduled_at", ["status", "scheduled_at"], unique=False
        )

    op.create_table(
        "notification_attempts",
        sa.Column("notification_id", sa.Uuid(native_uuid=False), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "succeeded",
                "failed",
                name="attempt_status",
                native_enum=False,
                create_constraint=False,
            ),
            nullable=False,
        ),
        sa.Column("attempted_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("provider_reference", sa.String(length=120), nullable=True),
        sa.Column("id", sa.Uuid(native_uuid=False), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(status = 'succeeded' AND error_code IS NULL) OR"
            "(status = 'failed' AND error_code IS NOT NULL)",
            name=op.f("ck_notification_attempts_error_status"),
        ),
        sa.CheckConstraint(
            "status IN ('succeeded', 'failed')",
            name=op.f("ck_notification_attempts_attempt_status"),
        ),
        sa.CheckConstraint(
            "attempt_number > 0", name=op.f("ck_notification_attempts_positive_attempt")
        ),
        sa.CheckConstraint(
            "finished_at >= attempted_at", name=op.f("ck_notification_attempts_attempt_range")
        ),
        sa.ForeignKeyConstraint(
            ["notification_id"],
            ["notifications.id"],
            name=op.f("fk_notification_attempts_notification_id_notifications"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notification_attempts")),
        sa.UniqueConstraint(
            "notification_id",
            "attempt_number",
            name=op.f("uq_notification_attempts_notification_id"),
        ),
    )
    with op.batch_alter_table("notification_attempts", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_notification_attempts_notification_id"),
            ["notification_id"],
            unique=False,
        )


def downgrade() -> None:
    """Only empty business tables can be removed; retain populated data intact."""
    if context.is_offline_mode():
        raise RuntimeError("Data-preserving downgrade requires an online connection")
    business_tables = (
        "audit_logs",
        "candidates",
        "vacancies",
        "candidate_language_tests",
        "candidate_certifications",
        "candidate_experiences",
        "vacancy_drafts",
        "vacancy_language_requirements",
        "matches",
        "placements",
        "placement_stages",
        "notifications",
        "notification_attempts",
    )
    connection = op.get_bind()
    for table_name in business_tables:
        if connection.execute(
            sa.select(sa.literal(1)).select_from(sa.table(table_name)).limit(1)
        ).first():
            raise RuntimeError("Refusing downgrade: business tables contain data")
    with op.batch_alter_table("notification_attempts", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_notification_attempts_notification_id"))

    op.drop_table("notification_attempts")
    with op.batch_alter_table("notifications", schema=None) as batch_op:
        batch_op.drop_index("ix_notifications_status_scheduled_at")
        batch_op.drop_index(batch_op.f("ix_notifications_placement_stage_id"))
        batch_op.drop_index(batch_op.f("ix_notifications_placement_id"))
        batch_op.drop_index(batch_op.f("ix_notifications_candidate_id"))

    op.drop_table("notifications")
    with op.batch_alter_table("placement_stages", schema=None) as batch_op:
        batch_op.drop_index("ix_placement_stages_status_scheduled_at")
        batch_op.drop_index(batch_op.f("ix_placement_stages_placement_id"))

    op.drop_table("placement_stages")
    with op.batch_alter_table("placements", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_placements_vacancy_id"))
        batch_op.drop_index(batch_op.f("ix_placements_status"))
        batch_op.drop_index(batch_op.f("ix_placements_match_id"))
        batch_op.drop_index(batch_op.f("ix_placements_candidate_id"))

    op.drop_table("placements")
    with op.batch_alter_table("vacancy_language_requirements", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_vacancy_language_requirements_vacancy_id"))

    op.drop_table("vacancy_language_requirements")
    with op.batch_alter_table("vacancy_drafts", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_vacancy_drafts_status"))

    op.drop_table("vacancy_drafts")
    with op.batch_alter_table("matches", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_matches_vacancy_id"))
        batch_op.drop_index(batch_op.f("ix_matches_status"))
        batch_op.drop_index(batch_op.f("ix_matches_candidate_id"))

    op.drop_table("matches")
    with op.batch_alter_table("candidate_language_tests", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_candidate_language_tests_candidate_id"))

    op.drop_table("candidate_language_tests")
    with op.batch_alter_table("candidate_experiences", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_candidate_experiences_sector"))
        batch_op.drop_index(batch_op.f("ix_candidate_experiences_candidate_id"))

    op.drop_table("candidate_experiences")
    with op.batch_alter_table("candidate_certifications", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_candidate_certifications_candidate_id"))

    op.drop_table("candidate_certifications")
    with op.batch_alter_table("vacancies", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_vacancies_status"))
        batch_op.drop_index(batch_op.f("ix_vacancies_sector"))
        batch_op.drop_index(batch_op.f("ix_vacancies_program"))
        batch_op.drop_index(batch_op.f("ix_vacancies_application_deadline"))

    op.drop_table("vacancies")
    with op.batch_alter_table("candidates", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_candidates_status"))
        batch_op.drop_index(batch_op.f("ix_candidates_preferred_program"))

    op.drop_table("candidates")
    with op.batch_alter_table("audit_logs", schema=None) as batch_op:
        batch_op.drop_index("ix_audit_logs_entity_time")

    op.drop_table("audit_logs")
