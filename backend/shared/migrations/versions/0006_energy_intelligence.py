"""create energy intelligence schema (risk scoring, disruption signals, data ingestion)

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-05
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS energy")

    # risk_factors
    op.create_table(
        "risk_factors",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("uuid", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), unique=True),
        sa.Column("name", sa.Text(), nullable=False, unique=True),
        sa.Column("description", sa.Text()),
        sa.Column("weight", sa.Double(), server_default="1.0"),
        sa.Column("data_source", sa.Text()),
        sa.Column("config", sa.JSON(), server_default="{}"),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("version", sa.Integer(), server_default="1"),
        sa.Column("created_by", sa.Text(), server_default="system"),
        sa.Column("updated_by", sa.Text(), server_default="system"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="energy",
    )

    # risk_scores
    op.create_table(
        "risk_scores",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("uuid", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), unique=True),
        sa.Column("entity_uuid", sa.Uuid(), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("dimension", sa.Text(), nullable=False),
        sa.Column("score", sa.Double(), nullable=False),
        sa.Column("confidence", sa.Double(), server_default="0.7"),
        sa.Column("breakdown", sa.JSON(), server_default="{}"),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="energy",
    )
    op.create_index("idx_risk_scores_entity", "risk_scores", ["entity_uuid", "entity_type"], schema="energy")
    op.create_index("idx_risk_scores_dimension", "risk_scores", ["dimension"], schema="energy")
    op.create_index("idx_risk_scores_score_desc", "risk_scores", [sa.text("score DESC")], schema="energy")
    op.create_index("idx_risk_scores_expires", "risk_scores", ["expires_at"], schema="energy")

    # disruption_signals
    op.create_table(
        "disruption_signals",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("uuid", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), unique=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("severity", sa.Text(), nullable=False, server_default="moderate"),
        sa.Column("risk_dimension", sa.Text(), nullable=False, server_default="operational"),
        sa.Column("affected_entity_type", sa.Text()),
        sa.Column("affected_entity_uuid", sa.Uuid()),
        sa.Column("affected_commodities", sa.ARRAY(sa.Text()), server_default="{}"),
        sa.Column("affected_regions", sa.ARRAY(sa.Text()), server_default="{}"),
        sa.Column("confidence", sa.Double(), server_default="0.7"),
        sa.Column("evidence_urls", sa.ARRAY(sa.Text()), server_default="{}"),
        sa.Column("ttl_hours", sa.Integer(), server_default="72"),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="energy",
    )
    op.create_index("idx_disruption_signals_severity", "disruption_signals", ["severity", "expires_at"], schema="energy")
    op.create_index("idx_disruption_signals_created", "disruption_signals", [sa.text("created_at DESC")], schema="energy")
    op.create_index("idx_disruption_signals_dimension", "disruption_signals", ["risk_dimension"], schema="energy")
    op.create_index("idx_disruption_signals_entity", "disruption_signals", ["affected_entity_uuid"], schema="energy")

    # response_telemetry
    op.create_table(
        "response_telemetry",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("uuid", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), unique=True),
        sa.Column("signal_id", sa.Uuid()),
        sa.Column("signal_type", sa.String(50), nullable=False),
        sa.Column("signal_detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("analysis_started_at", sa.DateTime(timezone=True)),
        sa.Column("analysis_completed_at", sa.DateTime(timezone=True)),
        sa.Column("recommendation_generated_at", sa.DateTime(timezone=True)),
        sa.Column("recommendation_approved_at", sa.DateTime(timezone=True)),
        sa.Column("total_latency_seconds", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="energy",
    )
    op.create_index("idx_response_telemetry_signal", "response_telemetry", ["signal_id"], schema="energy")

    # commodity_prices
    op.create_table(
        "commodity_prices",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("uuid", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), unique=True),
        sa.Column("commodity_name", sa.Text(), nullable=False),
        sa.Column("commodity_family", sa.Text(), nullable=False),
        sa.Column("price", sa.Double(), nullable=False),
        sa.Column("unit", sa.Text(), nullable=False),
        sa.Column("change_pct", sa.Double(), server_default="0"),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema="energy",
    )
    op.create_index("idx_commodity_prices_family", "commodity_prices", ["commodity_family", sa.text("recorded_at DESC")], schema="energy")
    op.create_index("idx_commodity_prices_recent", "commodity_prices", [sa.text("recorded_at DESC")], schema="energy")

    # ais_positions
    op.create_table(
        "ais_positions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("uuid", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), unique=True),
        sa.Column("location_name", sa.Text(), nullable=False),
        sa.Column("latitude", sa.Double(), nullable=False),
        sa.Column("longitude", sa.Double(), nullable=False),
        sa.Column("location_type", sa.Text(), nullable=False, server_default="chokepoint"),
        sa.Column("vessel_count", sa.Integer(), server_default="0"),
        sa.Column("avg_speed_knots", sa.Double()),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema="energy",
    )
    op.create_index("idx_ais_positions_type", "ais_positions", ["location_type", sa.text("recorded_at DESC")], schema="energy")
    op.create_index("idx_ais_positions_recent", "ais_positions", [sa.text("recorded_at DESC")], schema="energy")

    # sanctions
    op.create_table(
        "sanctions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("uuid", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), unique=True),
        sa.Column("country_code", sa.String(10), nullable=False),
        sa.Column("country_name", sa.Text(), nullable=False),
        sa.Column("sanction_scope", sa.Text(), nullable=False),
        sa.Column("imposed_by", sa.Text(), nullable=False),
        sa.Column("affected_commodities", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.Text(), nullable=False, server_default="primary"),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("source", sa.Text(), nullable=False, server_default="sanctions"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("country_code", "sanction_scope"),
        schema="energy",
    )
    op.create_index("idx_sanctions_country", "sanctions", ["country_code"], schema="energy")
    op.create_index("idx_sanctions_active", "sanctions", ["is_active"], schema="energy")

    # port_congestion
    op.create_table(
        "port_congestion",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("uuid", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), unique=True),
        sa.Column("port_name", sa.Text(), nullable=False),
        sa.Column("country", sa.Text(), nullable=False),
        sa.Column("latitude", sa.Double()),
        sa.Column("longitude", sa.Double()),
        sa.Column("congestion_pct", sa.Double(), server_default="0"),
        sa.Column("waiting_vessels", sa.Integer(), server_default="0"),
        sa.Column("avg_wait_hours", sa.Double(), server_default="0"),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema="energy",
    )
    op.create_index("idx_port_congestion_country", "port_congestion", ["country", sa.text("recorded_at DESC")], schema="energy")
    op.create_index("idx_port_congestion_pct", "port_congestion", [sa.text("congestion_pct DESC")], schema="energy")

    # tanker_availability
    op.create_table(
        "tanker_availability",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("uuid", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), unique=True),
        sa.Column("vessel_type", sa.Text(), nullable=False),
        sa.Column("vessels_available", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_vessels", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("avg_daily_rate_usd", sa.Double(), server_default="0"),
        sa.Column("utilization_pct", sa.Double(), server_default="0"),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema="energy",
    )
    op.create_index("idx_tanker_availability_type", "tanker_availability", ["vessel_type", sa.text("recorded_at DESC")], schema="energy")

    # scenario_assumptions
    op.create_table(
        "scenario_assumptions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("uuid", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), unique=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), server_default=""),
        sa.Column("assumptions", sa.JSON(), server_default="{}"),
        sa.Column("risk_dimensions", sa.ARRAY(sa.Text()), server_default="{geopolitical,operational,economic,environmental}"),
        sa.Column("created_by", sa.Text(), server_default="system"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="energy",
    )
    op.create_index("idx_scenario_assumptions_name", "scenario_assumptions", ["name"], schema="energy")
    op.create_index("idx_scenario_assumptions_created", "scenario_assumptions", [sa.text("created_at DESC")], schema="energy")


def downgrade() -> None:
    tables = [
        "scenario_assumptions", "tanker_availability", "port_congestion",
        "sanctions", "ais_positions", "commodity_prices",
        "response_telemetry", "disruption_signals", "risk_scores", "risk_factors",
    ]
    for t in tables:
        op.drop_table(t, schema="energy", if_exists=True)
