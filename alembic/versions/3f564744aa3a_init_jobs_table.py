"""Init jobs table

Revision ID: 3f564744aa3a
Revises: 29b731e42935
Create Date: 2026-06-12 13:19:06.227097

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3f564744aa3a'
down_revision: Union[str, Sequence[str], None] = '29b731e42935'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    ... 


def downgrade() -> None:
    """Downgrade schema."""
    ...
