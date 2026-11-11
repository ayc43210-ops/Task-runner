Idempotency keys expire based on job creation time, not completion time.

Leases under about 2 seconds aren’t reliable, because SQLite timestamps have one-second resolution.