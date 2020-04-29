"""empty message

Revision ID: 34debc9a1657
Revises: f2e15ebf3a1d
Create Date: 2020-04-29 20:24:13.613311

"""
from alembic import op
import sqlalchemy as sa
import sys

sys.path.append("../../")
import app
from sqlalchemy.dialects.postgresql import ENUM


# revision identifiers, used by Alembic.
revision = "34debc9a1657"
down_revision = "f2e15ebf3a1d"
branch_labels = None
depends_on = None

genre_type = ENUM(
    "jazz",
    "classical",
    "reggae",
    "swing",
    "folk",
    "r_b",
    "hip_hop",
    "rock_n_roll",
    name="genre_type",
)


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("Artist", "genres")
    genre_type.create(op.get_bind())
    op.add_column(
        "Artist", sa.Column("genres", app.ArrayOfEnum(genre_type), nullable=True,),
    )
    op.add_column("Artist", sa.Column("seeking_description", sa.Text(), nullable=True))
    op.add_column("Artist", sa.Column("seeking_venue", sa.Boolean(), nullable=True))
    op.add_column("Artist", sa.Column("website", sa.String(length=120), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("Artist", "genres")
    op.add_column("Artist", sa.Column("genres", sa.String(length=120), nullable=True))
    op.drop_column("Artist", "website")
    op.drop_column("Artist", "seeking_venue")
    op.drop_column("Artist", "seeking_description")
    # ### end Alembic commands ###