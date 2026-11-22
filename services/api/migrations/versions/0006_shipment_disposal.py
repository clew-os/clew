# SPDX-FileCopyrightText: The Clew Authors
# SPDX-License-Identifier: Apache-2.0
"""shipment status `disposed` and disposal columns (held food is never released)

Revision ID: 0006
Revises: 0005
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

OLD = "status IN ('planned', 'ready', 'held', 'dispatched', 'delivered')"
DISPOSED_RECORD = (
    "status <> 'disposed' OR (disposed_at IS NOT NULL AND disposed_by IS NOT NULL AND disposal_reason IS NOT NULL)"
)
NEW = "status IN ('planned', 'ready', 'held', 'dispatched', 'delivered', 'disposed')"


def upgrade() -> None:
    op.add_column("shipment", sa.Column("disposed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("shipment", sa.Column("disposed_by", sa.String(length=100), nullable=True))
    op.add_column("shipment", sa.Column("disposal_reason", sa.String(length=500), nullable=True))
    op.drop_constraint(op.f("ck_shipment_status_valid"), "shipment", type_="check")
    op.create_check_constraint(op.f("ck_shipment_status_valid"), "shipment", NEW)
    op.create_check_constraint(op.f("ck_shipment_disposed_has_record"), "shipment", DISPOSED_RECORD)


def downgrade() -> None:
    # Disposed rows cannot satisfy the old constraint; they are kept as `held` (the state they came from).
    op.drop_constraint(op.f("ck_shipment_disposed_has_record"), "shipment", type_="check")
    op.execute("UPDATE shipment SET status = 'held' WHERE status = 'disposed'")
    op.drop_constraint(op.f("ck_shipment_status_valid"), "shipment", type_="check")
    op.create_check_constraint(op.f("ck_shipment_status_valid"), "shipment", OLD)
    op.drop_column("shipment", "disposal_reason")
    op.drop_column("shipment", "disposed_by")
    op.drop_column("shipment", "disposed_at")
