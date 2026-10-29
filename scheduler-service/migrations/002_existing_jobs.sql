ALTER TABLE jobs ADD COLUMN IF NOT EXISTS claim_token TEXT;
CREATE INDEX IF NOT EXISTS jobs_expired ON jobs(lease_until) WHERE status='running';
