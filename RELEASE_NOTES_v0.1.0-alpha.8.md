# MachiningPro AI v0.1.0-alpha.8

## CAD import pipeline

- Added bounded streaming uploads for STEP, IGES, and ASCII DXF with a strict 64 MiB limit.
- Added extension, MIME, and content-header agreement checks with fail-closed rejection.
- Added SHA-256 metadata, temporary-file cleanup, and sanitized adapter error handling.
- Added complete staged-file adapter ingestion and allowlisted HTML/JSON import summaries.
- Added targeted coverage for routing, status reporting, cleanup, byte leakage, and post-512-byte parsing.
