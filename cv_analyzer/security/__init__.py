"""Security boundary modules.

- ``validate_upload`` — magic-byte/size/zip-safety checks before parsing
- ``redact``        — PII stripping before any text reaches an LLM
- ``rate_limit``    — per-session throttle in front of every LLM call
"""
