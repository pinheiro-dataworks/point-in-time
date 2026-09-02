"""Point-in-Time Analytics Lab.

Demonstrates how a naive join to a dimension's *current* state silently
corrupts historical analytics, using two real, dated GICS sector
reclassifications as the dimension history.

Modules:
    config:  environment-driven settings shared by every stage
    db:      warehouse connection and SQL-script execution helpers
    ingest:  Bronze-layer loading from raw CSV
    export:  Gold-layer materialisation to Parquet for the dashboard
"""

__version__ = "1.0.0"
__author__ = "Renan Pinheiro"
