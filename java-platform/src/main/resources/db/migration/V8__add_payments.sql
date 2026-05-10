CREATE TABLE organization_payment_settings (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL UNIQUE REFERENCES organizations(id) ON DELETE CASCADE,
    provider VARCHAR(32) NOT NULL DEFAULT 'stripe',
    mode VARCHAR(32) NOT NULL DEFAULT 'stripe_connect_standard',
    payments_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    default_currency VARCHAR(8) NOT NULL DEFAULT 'EUR',
    stripe_account_id VARCHAR(64),
    stripe_connect_status VARCHAR(24) NOT NULL DEFAULT 'not_connected',
    stripe_onboarding_complete BOOLEAN NOT NULL DEFAULT FALSE,
    stripe_details_submitted BOOLEAN NOT NULL DEFAULT FALSE,
    stripe_charges_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    stripe_payouts_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    stripe_access_token TEXT,
    stripe_refresh_token TEXT,
    stripe_publishable_key VARCHAR(255),
    stripe_scope VARCHAR(64),
    stripe_livemode BOOLEAN NOT NULL DEFAULT FALSE,
    stripe_oauth_state VARCHAR(160),
    stripe_last_error TEXT,
    last_synced_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_org_payment_settings_provider CHECK (provider IN ('stripe')),
    CONSTRAINT chk_org_payment_settings_mode CHECK (mode IN ('stripe_connect_standard')),
    CONSTRAINT chk_org_payment_settings_status CHECK (stripe_connect_status IN ('not_connected', 'pending', 'connected', 'restricted', 'error'))
);

CREATE INDEX idx_org_payment_settings_stripe_account_id ON organization_payment_settings(stripe_account_id);
CREATE INDEX idx_org_payment_settings_stripe_oauth_state ON organization_payment_settings(stripe_oauth_state);

CREATE TABLE payment_requests (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    sid VARCHAR(64) NOT NULL,
    created_by_user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
    provider VARCHAR(32) NOT NULL DEFAULT 'mock',
    provider_payment_id VARCHAR(160),
    provider_session_id VARCHAR(160),
    public_token VARCHAR(64) NOT NULL UNIQUE,
    amount_cents INTEGER NOT NULL,
    currency VARCHAR(8) NOT NULL DEFAULT 'EUR',
    purpose VARCHAR(160) NOT NULL DEFAULT 'Payment request',
    note TEXT NOT NULL DEFAULT '',
    status VARCHAR(16) NOT NULL DEFAULT 'sent',
    payment_url TEXT NOT NULL,
    expires_at TIMESTAMPTZ,
    paid_at TIMESTAMPTZ,
    provider_payload JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_payment_requests_status CHECK (status IN ('draft', 'sent', 'paid', 'failed', 'expired', 'cancelled')),
    CONSTRAINT chk_payment_requests_amount_positive CHECK (amount_cents > 0)
);

CREATE INDEX idx_payment_requests_org_sid_created ON payment_requests(organization_id, sid, created_at);
CREATE INDEX idx_payment_requests_org_status ON payment_requests(organization_id, status);
CREATE INDEX idx_payment_requests_public_token ON payment_requests(public_token);
