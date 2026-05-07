CREATE TABLE leads (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    assigned_user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
    sid VARCHAR(120) NOT NULL,
    display_name VARCHAR(200) NOT NULL,
    email VARCHAR(255),
    phone VARCHAR(120),
    status VARCHAR(50) NOT NULL,
    survey_slug VARCHAR(120),
    survey_progress INTEGER NOT NULL DEFAULT 0,
    last_message_preview VARCHAR(500),
    last_message_at TIMESTAMPTZ,
    takeover_active BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uk_leads_org_sid UNIQUE (organization_id, sid)
);

CREATE TABLE conversation_messages (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    lead_id BIGINT NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL,
    text TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE lead_events (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    sid VARCHAR(120) NOT NULL,
    event_type VARCHAR(120) NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_leads_org_last_message_at ON leads(organization_id, last_message_at DESC);
CREATE INDEX idx_leads_org_status ON leads(organization_id, status);
CREATE INDEX idx_messages_lead_created_at ON conversation_messages(lead_id, created_at ASC, id ASC);
CREATE INDEX idx_messages_org_lead ON conversation_messages(organization_id, lead_id);
CREATE INDEX idx_lead_events_org_sid_id ON lead_events(organization_id, sid, id);
CREATE INDEX idx_lead_events_org_id ON lead_events(organization_id, id);
