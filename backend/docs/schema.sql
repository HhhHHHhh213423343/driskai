CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS companies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL UNIQUE,
    credit_code VARCHAR(64) UNIQUE,
    industry VARCHAR(128),
    region VARCHAR(128),
    description TEXT NOT NULL DEFAULT '',
    official_website VARCHAR(255) NOT NULL DEFAULT '',
    company_profile JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS risk_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    category VARCHAR(80) NOT NULL,
    severity VARCHAR(16) NOT NULL,
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    source_url VARCHAR(512) NOT NULL,
    source_name VARCHAR(128) NOT NULL DEFAULT '',
    occurred_at TIMESTAMPTZ,
    sentiment VARCHAR(16) NOT NULL DEFAULT 'neutral',
    extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_risk_events_company_id ON risk_events(company_id);
CREATE INDEX IF NOT EXISTS ix_risk_events_category ON risk_events(category);
CREATE INDEX IF NOT EXISTS ix_risk_events_severity ON risk_events(severity);
CREATE INDEX IF NOT EXISTS ix_risk_events_occurred_at ON risk_events(occurred_at DESC);
CREATE INDEX IF NOT EXISTS ix_risk_events_company_category_severity
    ON risk_events(company_id, category, severity);

CREATE TABLE IF NOT EXISTS analysis_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    report_type VARCHAR(80) NOT NULL,
    title VARCHAR(255) NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    model_name VARCHAR(120) NOT NULL DEFAULT 'fastgpt',
    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_analysis_reports_company_id ON analysis_reports(company_id);
CREATE INDEX IF NOT EXISTS ix_analysis_reports_report_type ON analysis_reports(report_type);
CREATE INDEX IF NOT EXISTS ix_analysis_reports_company_report_type_generated_at
    ON analysis_reports(company_id, report_type, generated_at DESC);

CREATE TABLE IF NOT EXISTS ingestion_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    status VARCHAR(24) NOT NULL DEFAULT 'running',
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    requested_company_count INTEGER NOT NULL DEFAULT 0,
    scanned_company_count INTEGER NOT NULL DEFAULT 0,
    total_raw_count INTEGER NOT NULL DEFAULT 0,
    inserted_count INTEGER NOT NULL DEFAULT 0,
    skipped_count INTEGER NOT NULL DEFAULT 0,
    source_breakdown JSONB NOT NULL DEFAULT '{}'::jsonb,
    failures JSONB NOT NULL DEFAULT '[]'::jsonb,
    summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_ingestion_runs_status ON ingestion_runs(status);
CREATE INDEX IF NOT EXISTS ix_ingestion_runs_started_at ON ingestion_runs(started_at DESC);
