"""Mantém a suíte independente de um banco externo ou arquivo .env local."""

import os

os.environ.setdefault("DATABASE_URL", "sqlite://")
