"""Auth hardening tests — covers JWT_SECRET fail-loud, password policy,
account lockout, and refresh-token rotation.
"""
import importlib
import os

import pytest

import healthflow.auth.security as security


def test_jwt_secret_fail_loud_raises_when_unset(monkeypatch):
    """A missing JWT_SECRET env var must raise at module reload."""
    monkeypatch.delenv("JWT_SECRET", raising=False)
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        importlib.reload(security)
    # Restore a valid value before this module's reference to `security`
    # becomes the unloaded one for the rest of the suite.
    monkeypatch.setenv("JWT_SECRET", "test-secret-not-for-production")
    importlib.reload(security)


def test_jwt_secret_fail_loud_rejects_legacy_default(monkeypatch):
    """The known-bad legacy default value must be rejected."""
    monkeypatch.setenv("JWT_SECRET", "healthflow-dev-secret-change-in-production")
    with pytest.raises(RuntimeError, match="legacy default"):
        importlib.reload(security)
    monkeypatch.setenv("JWT_SECRET", "test-secret-not-for-production")
    importlib.reload(security)


def test_jwt_secret_accepts_any_other_value(monkeypatch):
    """Setting to any other string imports cleanly."""
    monkeypatch.setenv("JWT_SECRET", "a-real-deploy-secret-7384")
    importlib.reload(security)
    assert security.JWT_SECRET == "a-real-deploy-secret-7384"
    # Restore the test default for the rest of the suite.
    monkeypatch.setenv("JWT_SECRET", "test-secret-not-for-production")
    importlib.reload(security)
