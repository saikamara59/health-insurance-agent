"""Re-use the shared HealthFlow test fixtures (client, db_session, etc.).

The package-colocated tests sit outside `healthflow/tests/`, so they don't
inherit `healthflow/tests/conftest.py` via pytest's normal discovery.
Importing it as a module gets both the env-var bootstrap (JWT_SECRET,
PHI_ENCRYPTION_KEY, EMAIL_PROVIDER, FRONTEND_BASE_URL) and the fixtures.
"""
from healthflow.tests.conftest import *  # noqa: F401, F403
