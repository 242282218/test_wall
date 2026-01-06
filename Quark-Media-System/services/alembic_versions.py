"""Add task retry fields to virtual_media

Revision ID: add_task_retry_fields
Revises: 
Create Date: 2026-01-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'add_task_retry_fields'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('virtualmedia', sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('virtualmedia', sa.Column('error_message', sa.String(), nullable=True))
    op.add_column('virtualmedia', sa.Column('last_retry_at', sa.DateTime(), nullable=True))
    op.add_column('virtualmedia', sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()))


def downgrade() -> None:
    op.drop_column('virtualmedia', 'updated_at')
    op.drop_column('virtualmedia', 'last_retry_at')
    op.drop_column('virtualmedia', 'error_message')
    op.drop_column('virtualmedia', 'retry_count')