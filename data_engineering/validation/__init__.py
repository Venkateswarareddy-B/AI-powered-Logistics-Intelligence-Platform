"""YottaFlex data validation package.

Entry point: python -m data_engineering.validation

Validators are modular and composable. Each inherits from BaseValidator
and returns a list of ValidationResult objects. The pipeline orchestrator
(pipeline.py) runs all validators in order, persists DataQualityIssue rows,
and updates validation_summary.json.

Anomalies are NEVER silently deleted — they are labelled and preserved.
"""
