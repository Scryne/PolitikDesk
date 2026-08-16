-- 0013_promise_radar.sql — Siyasi Vaat Takip Radarı ve Taahhüt Tablosu (Spec v3.5 §5, §12.5)

CREATE TABLE IF NOT EXISTS promise_tracker (
    id SERIAL PRIMARY KEY,
    claim_id INTEGER NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    actor_name VARCHAR(255) NOT NULL,
    actor_canonical VARCHAR(255),
    promise_text TEXT NOT NULL,
    target_period VARCHAR(64),
    target_date DATE,
    status VARCHAR(32) NOT NULL DEFAULT 'pending'
        CONSTRAINT chk_promise_status CHECK (status IN ('pending', 'fulfilled', 'contradicted', 'expired')),
    fulfilled_at TIMESTAMPTZ,
    fulfilling_event_id INTEGER REFERENCES events(id) ON DELETE SET NULL,
    contradicting_event_id INTEGER REFERENCES events(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_promise_tracker_claim ON promise_tracker(claim_id);
CREATE INDEX IF NOT EXISTS idx_promise_tracker_actor ON promise_tracker(actor_canonical);
CREATE INDEX IF NOT EXISTS idx_promise_tracker_status ON promise_tracker(status);
CREATE INDEX IF NOT EXISTS idx_promise_tracker_target_date ON promise_tracker(target_date);
