"""Initial schema migration for Phoenix AI Travel Companion.

Revision ID: 001
Revises:
Create Date: 2025-03-01 00:00:00

"""
from alembic import op
import sqlalchemy as sa
import sqlalchemy.dialects.postgresql as pg

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


# Import Vector from pgvector package
from pgvector.sqlalchemy import Vector


def upgrade() -> None:
    """Upgrade database schema with all initial tables."""

    # Use pgvector.Vector for embeddings (1536 dimensions for OpenAI)
    embedding_type = Vector(1536)

    # Users table
    op.create_table(
        'users',
        sa.Column('id', pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('email', sa.String(255), nullable=False, unique=True),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('display_name', sa.String(100), nullable=True),
        sa.Column('google_id', sa.String(255), nullable=True, unique=True),
        sa.Column('apple_id', sa.String(255), nullable=True, unique=True),
        sa.Column('preferred_language', sa.String(10), nullable=False, default='en'),
        sa.Column('timezone', sa.String(50), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('is_verified', sa.Boolean(), nullable=False, default=False),
        sa.Column('last_active_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('bio', sa.Text(), nullable=True),
        sa.Column('avatar_url', sa.String(500), nullable=True),
        sa.Column('home_city', sa.String(100), nullable=True),
        sa.Column('home_country', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), onupdate=sa.text('NOW()'), nullable=False),
    )
    op.create_index('idx_users_email', 'users', ['email'])
    op.create_index('idx_users_language', 'users', ['preferred_language'])
    op.create_index('idx_users_is_active', 'users', ['is_active'])

    # Refresh tokens table
    op.create_table(
        'refresh_tokens',
        sa.Column('id', pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', pg.UUID(as_uuid=True), nullable=False),
        sa.Column('token', sa.String(500), nullable=False, unique=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('is_revoked', sa.Boolean(), nullable=False, default=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('device_info', sa.String(255), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), onupdate=sa.text('NOW()'), nullable=False),
    )
    op.create_index('idx_refresh_tokens_user_id', 'refresh_tokens', ['user_id'])
    op.create_index('idx_refresh_tokens_token', 'refresh_tokens', ['token'])
    op.create_index('idx_refresh_tokens_is_revoked', 'refresh_tokens', ['is_revoked'])

    # Password resets table
    op.create_table(
        'password_resets',
        sa.Column('id', pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', pg.UUID(as_uuid=True), nullable=False),
        sa.Column('token', sa.String(255), nullable=False, unique=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('is_used', sa.Boolean(), nullable=False, default=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), onupdate=sa.text('NOW()'), nullable=False),
    )
    op.create_index('idx_password_resets_user_id', 'password_resets', ['user_id'])
    op.create_index('idx_password_resets_token', 'password_resets', ['token'])

    # User preferences table
    op.create_table(
        'user_preferences',
        sa.Column('id', pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', pg.UUID(as_uuid=True), nullable=False),
        sa.Column('preference_type', sa.String(50), nullable=False),
        sa.Column('category', sa.String(100), nullable=False),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column('embedding', embedding_type, nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=False, default=1.0),
        sa.Column('source', sa.String(50), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('context', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), onupdate=sa.text('NOW()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    )
    op.create_index('idx_user_preferences_user_id', 'user_preferences', ['user_id'])
    op.create_index('idx_user_preferences_type_category', 'user_preferences', ['preference_type', 'category'])

    # Preference conflicts table
    op.create_table(
        'preference_conflicts',
        sa.Column('id', pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', pg.UUID(as_uuid=True), nullable=False),
        sa.Column('preference_id_1', pg.UUID(as_uuid=True), nullable=False),
        sa.Column('preference_id_2', pg.UUID(as_uuid=True), nullable=False),
        sa.Column('conflict_type', sa.String(50), nullable=False),
        sa.Column('severity', sa.String(20), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('resolved', sa.Boolean(), nullable=False, default=False),
        sa.Column('resolution', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), onupdate=sa.text('NOW()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['preference_id_1'], ['user_preferences.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['preference_id_2'], ['user_preferences.id'], ondelete='CASCADE'),
    )
    op.create_index('idx_preference_conflicts_user_id', 'preference_conflicts', ['user_id'])

    # Points of Interest table
    op.create_table(
        'points_of_interest',
        sa.Column('id', pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('external_id', sa.String(255), nullable=True, unique=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('categories', pg.ARRAY(sa.String(100)), nullable=False, default=[]),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('city', sa.String(100), nullable=True),
        sa.Column('country', sa.String(100), nullable=True),
        sa.Column('latitude', sa.NUMERIC(10, 8), nullable=False),
        sa.Column('longitude', sa.NUMERIC(11, 8), nullable=False),
        sa.Column('embedding', embedding_type, nullable=True),
        sa.Column('rating', sa.NUMERIC(3, 2), nullable=True),
        sa.Column('price_level', sa.Integer(), nullable=True),
        sa.Column('review_count', sa.Integer(), nullable=True),
        sa.Column('popularity_score', sa.Float(), nullable=True),
        sa.Column('opening_hours', pg.JSONB(), nullable=True),
        sa.Column('phone', sa.String(50), nullable=True),
        sa.Column('website', sa.String(500), nullable=True),
        sa.Column('email', sa.String(255), nullable=True),
        sa.Column('images', pg.JSONB(), nullable=False, default=[]),
        sa.Column('social_signals', pg.JSONB(), nullable=False, default={}),
        sa.Column('is_verified', sa.Boolean(), nullable=False, default=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('source', sa.String(50), nullable=True),
        sa.Column('last_verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), onupdate=sa.text('NOW()'), nullable=False),
    )
    op.create_index('idx_poi_external_id', 'points_of_interest', ['external_id'], unique=True)
    op.create_index('idx_poi_name', 'points_of_interest', ['name'])
    op.create_index('idx_poi_city', 'points_of_interest', ['city'])
    op.create_index('idx_poi_country', 'points_of_interest', ['country'])
    op.create_index('idx_poi_is_active', 'points_of_interest', ['is_active'])

    # POI search index
    op.create_table(
        'poi_search_index',
        sa.Column('id', pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('poi_id', pg.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column('search_vector', sa.Text(), nullable=False),
        sa.Column('category_vector', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), onupdate=sa.text('NOW()'), nullable=False),
        sa.ForeignKeyConstraint(['poi_id'], ['points_of_interest.id'], ondelete='CASCADE'),
    )
    op.create_index('idx_poi_search_index_poi_id', 'poi_search_index', ['poi_id'])

    # Itineraries table
    op.create_table(
        'itineraries',
        sa.Column('id', pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', pg.UUID(as_uuid=True), nullable=False),
        sa.Column('title', sa.String(255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, default='draft'),
        sa.Column('start_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('end_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('total_duration_minutes', sa.Integer(), nullable=True),
        sa.Column('start_location', sa.String(255), nullable=True),
        sa.Column('end_location', sa.String(255), nullable=True),
        sa.Column('total_distance_km', sa.Float(), nullable=True),
        sa.Column('satisfaction_score', sa.Float(), nullable=True),
        sa.Column('optimization_version', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), onupdate=sa.text('NOW()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    )
    op.create_index('idx_itineraries_user_id', 'itineraries', ['user_id'])
    op.create_index('idx_itineraries_status', 'itineraries', ['status'])

    # Itinerary items table
    op.create_table(
        'itinerary_items',
        sa.Column('id', pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('itinerary_id', pg.UUID(as_uuid=True), nullable=False),
        sa.Column('poi_id', pg.UUID(as_uuid=True), nullable=True),
        sa.Column('sequence_order', sa.Integer(), nullable=False),
        sa.Column('estimated_duration_minutes', sa.Integer(), nullable=True),
        sa.Column('estimated_arrival_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('estimated_departure_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('actual_arrival_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('actual_departure_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('distance_from_previous_km', sa.Float(), nullable=True),
        sa.Column('travel_time_minutes', sa.Integer(), nullable=True),
        sa.Column('transport_mode', sa.String(50), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, default='planned'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('user_rating', sa.Integer(), nullable=True),
        sa.Column('user_feedback', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), onupdate=sa.text('NOW()'), nullable=False),
        sa.ForeignKeyConstraint(['itinerary_id'], ['itineraries.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['poi_id'], ['points_of_interest.id'], ondelete='SET NULL'),
    )
    op.create_index('idx_itinerary_items_itinerary_id', 'itinerary_items', ['itinerary_id'])
    op.create_index('idx_itinerary_items_sequence', 'itinerary_items', ['itinerary_id', 'sequence_order'])

    # Itinerary notes table
    op.create_table(
        'itinerary_notes',
        sa.Column('id', pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('itinerary_id', pg.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', pg.UUID(as_uuid=True), nullable=False),
        sa.Column('title', sa.String(255), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('note_type', sa.String(50), nullable=False, default='general'),
        sa.Column('location', sa.String(255), nullable=True),
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), onupdate=sa.text('NOW()'), nullable=False),
        sa.ForeignKeyConstraint(['itinerary_id'], ['itineraries.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    )
    op.create_index('idx_itinerary_notes_itinerary_id', 'itinerary_notes', ['itinerary_id'])
    op.create_index('idx_itinerary_notes_user_id', 'itinerary_notes', ['user_id'])


def downgrade() -> None:
    """Downgrade database schema by dropping all tables."""
    op.drop_table('itinerary_notes')
    op.drop_table('itinerary_items')
    op.drop_table('itineraries')
    op.drop_table('poi_search_index')
    op.drop_table('points_of_interest')
    op.drop_table('preference_conflicts')
    op.drop_table('user_preferences')
    op.drop_table('password_resets')
    op.drop_table('refresh_tokens')
    op.drop_table('users')
