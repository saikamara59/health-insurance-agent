"""Re-use the shared HealthFlow test fixtures (client, db_session, etc.).

Forensics tests sit outside `healthflow/tests/`, so they don't inherit
that directory's conftest via pytest's normal discovery. Importing the
shared conftest as a module gets both the env-var bootstrap and the
fixtures.
"""
from healthflow.tests.conftest import *  # noqa: F401, F403
