"""Initial schema — users, papers, audit, webhooks, hypotheses.

Revision ID: 0001
Revises:
Create Date: 2026-06-09
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("name", sa.String(), server_default=""),
        sa.Column("role", sa.String(), server_default="viewer"),
        sa.Column("api_key", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("TRUE")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("api_key"),
    )
    op.create_index("idx_users_email", "users", ["email"])
    op.create_index("idx_users_api_key", "users", ["api_key"])

    op.create_table(
        "papers",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("abstract", sa.Text(), server_default=""),
        sa.Column("authors", postgresql.JSONB(), server_default="[]"),
        sa.Column("doi", sa.String(), nullable=True),
        sa.Column("source", sa.String(), server_default="unknown"),
        sa.Column("source_id", sa.String(), server_default=""),
        sa.Column("url", sa.String(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("categories", postgresql.JSONB(), server_default="[]"),
        sa.Column("citations_count", sa.Integer(), server_default="0"),
        sa.Column("quality_score", sa.Float(), nullable=True),
        sa.Column("provenance", postgresql.JSONB(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), server_default="{}"),
        sa.Column("archived", sa.Boolean(), server_default=sa.text("FALSE")),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("indexed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_papers_source", "papers", ["source"])
    op.create_index("idx_papers_doi", "papers", ["doi"])
    op.create_index("idx_papers_quality", "papers", ["quality_score"])
    op.create_index("idx_papers_archived", "papers", ["archived"])
    op.create_index("idx_papers_published", "papers", ["published_at"])

    op.create_table(
        "audit_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("actor", sa.String(), nullable=False),
        sa.Column("resource", sa.String(), nullable=True),
        sa.Column("detail", postgresql.JSONB(), server_default="{}"),
        sa.Column("status", sa.String(), server_default="success"),
        sa.Column("ip_address", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_audit_action", "audit_events", ["action"])
    op.create_index("idx_audit_actor", "audit_events", ["actor"])
    op.create_index("idx_audit_timestamp", "audit_events", ["timestamp"])

    op.create_table(
        "webhooks",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("events", postgresql.JSONB(), server_default='["all"]'),
        sa.Column("secret", sa.String(), nullable=True),
        sa.Column("active", sa.Boolean(), server_default=sa.text("TRUE")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "hypotheses",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("hypothesis_text", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), server_default="0.5"),
        sa.Column("supporting_evidence", postgresql.JSONB(), server_default="[]"),
        sa.Column("evidence_items", postgresql.JSONB(), server_default="[]"),
        sa.Column("suggested_experiments", postgresql.JSONB(), server_default="[]"),
        sa.Column("related_concepts", postgresql.JSONB(), server_default="[]"),
        sa.Column("source_category", sa.String(), nullable=True),
        sa.Column("evaluated", sa.Boolean(), server_default=sa.text("FALSE")),
        sa.Column("evaluation_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_hypotheses_created", "hypotheses", ["created_at"])
    op.create_index("idx_hypotheses_source", "hypotheses", ["source_category"])


def downgrade() -> None:
    op.drop_table("hypotheses")
    op.drop_table("webhooks")
    op.drop_table("audit_events")
    op.drop_table("papers")
    op.drop_table("users")
