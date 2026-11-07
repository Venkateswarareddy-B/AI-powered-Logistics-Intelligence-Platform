"""YottaFlex ETL pipeline orchestration package.

Entry point: python -m data_engineering.pipelines [options]

Architecture: Bronze → Silver → Gold
  Bronze  — raw data stamped with ingestion metadata; no transformations.
  Silver  — deduplicated, type-corrected, anomaly-flagged data.
  Gold    — business-ready aggregates and ML feature rows.

Anomalies are NEVER deleted — they flow through with is_anomaly=True
flags so downstream ML can exclude them via explicit filters.
"""
