"""add_phase8_enterprise_whitelabel

Revision ID: 13abc5fb58f2
Revises: ebfd6d5685a5
Create Date: 2026-06-11 23:15:44.251766

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '13abc5fb58f2'
down_revision: Union[str, Sequence[str], None] = 'ebfd6d5685a5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create agencies table
    op.execute("""
        CREATE TABLE IF NOT EXISTS public.agencies (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(255) NOT NULL,
            custom_domain VARCHAR(255) UNIQUE,
            logo_url TEXT,
            brand_color_primary VARCHAR(7) DEFAULT '#1e3a8a',
            brand_color_secondary VARCHAR(7) DEFAULT '#10b981',
            support_email VARCHAR(255),
            stripe_wholesale_customer_id VARCHAR(255),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
        );
    """)

    # 2. Create clinic_groups table
    op.execute("""
        CREATE TABLE IF NOT EXISTS public.clinic_groups (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(255) NOT NULL,
            owner_email VARCHAR(255) NOT NULL UNIQUE,
            stripe_customer_id VARCHAR(255),
            stripe_subscription_id VARCHAR(255),
            stripe_subscription_status VARCHAR(50) DEFAULT 'trialing',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
        );
    """)

    # 3. Add group_id and agency_id to clinics table
    op.execute("ALTER TABLE public.clinics ADD COLUMN IF NOT EXISTS group_id UUID REFERENCES public.clinic_groups(id) ON DELETE SET NULL;")
    op.execute("ALTER TABLE public.clinics ADD COLUMN IF NOT EXISTS agency_id UUID REFERENCES public.agencies(id) ON DELETE SET NULL;")

    # 4. Create global_patient_identity table
    op.execute("""
        CREATE TABLE IF NOT EXISTS public.global_patient_identity (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            group_id UUID NOT NULL REFERENCES public.clinic_groups(id) ON DELETE CASCADE,
            first_name_hash VARCHAR(64) NOT NULL,
            last_name_hash VARCHAR(64) NOT NULL,
            phone_hash VARCHAR(64) NOT NULL,
            dob_hash VARCHAR(64) NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_global_identity_hashes ON public.global_patient_identity(group_id, phone_hash, dob_hash);")

    # 5. Add global_identity_id and language_preference to patients table
    op.execute("ALTER TABLE public.patients ADD COLUMN IF NOT EXISTS global_identity_id UUID REFERENCES public.global_patient_identity(id) ON DELETE SET NULL;")
    op.execute("ALTER TABLE public.patients ADD COLUMN IF NOT EXISTS language_preference VARCHAR(10) DEFAULT 'en';")

    # 6. Create ehr_integrations table
    op.execute("""
        CREATE TABLE IF NOT EXISTS public.ehr_integrations (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            clinic_id UUID NOT NULL REFERENCES public.clinics(id) ON DELETE CASCADE,
            provider_name VARCHAR(50) NOT NULL,
            client_id TEXT,
            client_secret TEXT,
            access_token TEXT,
            refresh_token TEXT,
            fhir_endpoint TEXT,
            webhook_secret TEXT,
            provider_clinic_id VARCHAR(255),
            sync_frequency VARCHAR(50) DEFAULT 'realtime',
            sync_enabled BOOLEAN DEFAULT TRUE,
            is_active BOOLEAN DEFAULT TRUE,
            settings JSONB DEFAULT '{}'::jsonb,
            last_synced_at TIMESTAMP WITH TIME ZONE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
            UNIQUE(clinic_id, provider_name)
        );
    """)

    # 7. Create ehr_resource_mappings table
    op.execute("""
        CREATE TABLE IF NOT EXISTS public.ehr_resource_mappings (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            clinic_id UUID NOT NULL REFERENCES public.clinics(id) ON DELETE CASCADE,
            provider_name VARCHAR(50),
            local_resource_type VARCHAR(50) NOT NULL,
            local_resource_id UUID NOT NULL,
            ehr_resource_id VARCHAR(255) NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
            UNIQUE(clinic_id, local_resource_type, local_resource_id)
        );
    """)

    # 8. Create agent_configs table
    op.execute("""
        CREATE TABLE IF NOT EXISTS public.agent_configs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            clinic_id UUID NOT NULL REFERENCES public.clinics(id) ON DELETE CASCADE UNIQUE,
            retell_agent_id VARCHAR(255) NOT NULL,
            greeting_message TEXT NOT NULL,
            custom_system_prompt TEXT NOT NULL,
            voice_id VARCHAR(100) DEFAULT '11labs-rachel',
            language VARCHAR(10) DEFAULT 'en-US',
            emergency_forward_phone VARCHAR(15),
            faq_data JSONB DEFAULT '{}'::jsonb,
            ab_test_active BOOLEAN DEFAULT FALSE,
            script_a TEXT,
            script_b TEXT,
            compiled_prompt TEXT,
            retell_llm_id VARCHAR(255),
            retell_synced_at TIMESTAMP WITH TIME ZONE,
            retell_sync_status VARCHAR(50) DEFAULT 'not_synced',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
        );
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.agent_configs CASCADE;")
    op.execute("DROP TABLE IF EXISTS public.ehr_resource_mappings CASCADE;")
    op.execute("DROP TABLE IF EXISTS public.ehr_integrations CASCADE;")
    op.execute("ALTER TABLE public.patients DROP COLUMN IF EXISTS global_identity_id;")
    op.execute("ALTER TABLE public.patients DROP COLUMN IF EXISTS language_preference;")
    op.execute("DROP TABLE IF EXISTS public.global_patient_identity CASCADE;")
    op.execute("ALTER TABLE public.clinics DROP COLUMN IF EXISTS group_id;")
    op.execute("ALTER TABLE public.clinics DROP COLUMN IF EXISTS agency_id;")
    op.execute("DROP TABLE IF EXISTS public.clinic_groups CASCADE;")
    op.execute("DROP TABLE IF EXISTS public.agencies CASCADE;")
