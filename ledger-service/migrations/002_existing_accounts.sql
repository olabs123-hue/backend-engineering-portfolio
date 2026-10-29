-- Legacy upgrade: run ONLY after reconciling historic opening balances.
-- Existing balances cannot be assumed to be opening balances after transfers.
ALTER TABLE accounts ADD COLUMN IF NOT EXISTS opening_balance BIGINT;
-- Backfill each account opening balance from trusted opening records or:
-- opening_balance = current balance - SUM(all historical journal movements).
-- Review values before enforcing NOT NULL.
