-- One row per visitor per day. `who` is a hash of IP + user agent: enough to
-- tell visitors apart, not enough to identify anyone, and it needs no accounts.
CREATE TABLE IF NOT EXISTS checks (
  day  TEXT NOT NULL,          -- YYYY-MM-DD, UTC
  who  TEXT NOT NULL,          -- sha-256 of (ip + user agent + salt), first 32 hex
  n    INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (day, who)
);
