-- Applied at startup by api and worker (idempotent).
CREATE TABLE IF NOT EXISTS jobs (
    id              uuid PRIMARY KEY,
    status          text NOT NULL DEFAULT 'queued',
    progress        int  NOT NULL DEFAULT 0,
    request         jsonb NOT NULL,
    request_hash    text NOT NULL,
    kind            text NOT NULL DEFAULT 'generate',   -- generate | regenerate
    parent_job_id   uuid REFERENCES jobs(id),
    correlation_id  text,
    callback_url    text,
    attempts        int  NOT NULL DEFAULT 0,
    locked_by       text,
    heartbeat_at    timestamptz,
    created_at      timestamptz NOT NULL DEFAULT now(),
    started_at      timestamptz,
    finished_at     timestamptz,
    warnings        jsonb NOT NULL DEFAULT '[]'::jsonb,
    result          jsonb,
    error           jsonb
);
CREATE INDEX IF NOT EXISTS jobs_status_created ON jobs (status, created_at);

CREATE TABLE IF NOT EXISTS idempotency (
    key           text NOT NULL,
    route         text NOT NULL,
    request_hash  text NOT NULL,
    job_id        uuid NOT NULL REFERENCES jobs(id),
    created_at    timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (key, route)
);

CREATE TABLE IF NOT EXISTS uploads (
    id            uuid PRIMARY KEY,
    s3_key        text NOT NULL,
    filename      text,
    size_bytes    bigint NOT NULL,
    created_at    timestamptz NOT NULL DEFAULT now()
);
