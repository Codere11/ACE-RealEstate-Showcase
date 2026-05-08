ALTER TABLE leads
    ADD COLUMN qualifier_profile JSONB,
    ADD COLUMN qualifier_missing_fields JSONB,
    ADD COLUMN qualification_score INTEGER,
    ADD COLUMN qualification_band VARCHAR(16),
    ADD COLUMN confidence_overall DOUBLE PRECISION,
    ADD COLUMN qualification_reasoning TEXT,
    ADD COLUMN takeover_eligible BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN video_offer_eligible BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX idx_leads_org_band ON leads(organization_id, qualification_band);
