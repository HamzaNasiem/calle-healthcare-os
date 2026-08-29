CREATE TABLE prior_auth_requests (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    appointment_id UUID,
    patient_id UUID,
    provider_id UUID,
    created_by_user_id UUID,
    insurance_provider_name VARCHAR,
    insurance_prior_auth_phone VARCHAR,
    patient_member_id_encrypted BYTEA,
    patient_group_number_encrypted BYTEA,
    cpt_code VARCHAR,
    cpt_description TEXT,
    icd10_code VARCHAR,
    icd10_description TEXT,
    urgency VARCHAR DEFAULT 'standard',
    requested_service_date DATE,
    calle_task_id VARCHAR,
    call_status VARCHAR DEFAULT 'pending',
    call_started_at TIMESTAMPTZ,
    call_completed_at TIMESTAMPTZ,
    call_duration_seconds INTEGER,
    call_recording_url TEXT,
    auth_status VARCHAR,
    authorization_number_encrypted BYTEA,
    denial_reason TEXT,
    denial_code VARCHAR,
    reference_number VARCHAR,
    insurance_agent_name VARCHAR,
    expected_decision_date DATE,
    additional_info_required TEXT,
    call_summary TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_prior_auth_tenant_id ON prior_auth_requests(tenant_id);
CREATE INDEX idx_prior_auth_patient_id ON prior_auth_requests(patient_id);
CREATE INDEX idx_prior_auth_call_status ON prior_auth_requests(call_status);
