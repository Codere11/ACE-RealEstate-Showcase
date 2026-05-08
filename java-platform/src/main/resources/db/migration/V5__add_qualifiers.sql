CREATE TABLE qualifiers (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name VARCHAR(160) NOT NULL,
    slug VARCHAR(80) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    system_prompt TEXT NOT NULL DEFAULT '',
    assistant_style VARCHAR(255) NOT NULL DEFAULT 'friendly, concise, consultative',
    goal_definition TEXT NOT NULL DEFAULT '',
    field_schema JSONB,
    required_fields JSONB,
    scoring_rules JSONB,
    band_thresholds JSONB,
    confidence_thresholds JSONB,
    takeover_rules JSONB,
    video_offer_rules JSONB,
    rag_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    knowledge_source_ids JSONB,
    max_clarifying_questions INTEGER NOT NULL DEFAULT 3,
    contact_capture_policy VARCHAR(64) NOT NULL DEFAULT 'when_high_intent_or_explicit',
    version INTEGER NOT NULL DEFAULT 1,
    version_notes TEXT NOT NULL DEFAULT '',
    published_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uk_qualifiers_org_slug UNIQUE (organization_id, slug)
);

CREATE INDEX idx_qualifiers_org_updated ON qualifiers(organization_id, updated_at DESC);
CREATE INDEX idx_qualifiers_org_status ON qualifiers(organization_id, status);
