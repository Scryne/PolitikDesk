-- 0025_dead_letter_queue.sql
-- Celery görev hataları için Dead-Letter Queue ve otomatik onarım kütüğü

CREATE TABLE IF NOT EXISTS dead_letter_tasks (
    id SERIAL PRIMARY KEY,
    task_id VARCHAR(128) NOT NULL,
    task_name VARCHAR(128) NOT NULL,
    args JSONB NOT NULL DEFAULT '[]'::jsonb,
    kwargs JSONB NOT NULL DEFAULT '{}'::jsonb,
    exception_type VARCHAR(128) NOT NULL,
    exception_message TEXT NOT NULL,
    traceback TEXT NOT NULL,
    retry_count INT NOT NULL DEFAULT 0,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_dlq_status_created ON dead_letter_tasks(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_dlq_task_name ON dead_letter_tasks(task_name);
