CREATE TABLE IF NOT EXISTS live_sessions (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    manager_user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
    sid VARCHAR(120) NOT NULL,
    manager_display_name VARCHAR(200) NOT NULL,
    provider VARCHAR(50) NOT NULL DEFAULT 'livekit',
    status VARCHAR(50) NOT NULL,
    room_name VARCHAR(200),
    stage_message VARCHAR(500),
    started_at TIMESTAMPTZ,
    live_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_live_sessions_org_sid_created ON live_sessions(organization_id, sid, created_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_live_sessions_org_status ON live_sessions(organization_id, status);
