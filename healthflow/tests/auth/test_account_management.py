"""Account management tests — Mailer + require_admin + change-password +
forgot-password + reset-password + admin force-unlock + promote_admin CLI.
"""
import logging
from unittest.mock import MagicMock

import pytest


# ── Mailer ───────────────────────────────────────────────────────────────────


def test_console_mailer_logs_email_body(caplog):
    """ConsoleMailer.send writes the email body at INFO with to= and subject= markers."""
    from healthflow.email.mailer import ConsoleMailer

    mailer = ConsoleMailer()
    with caplog.at_level(logging.INFO, logger="healthflow.email.mailer"):
        mailer.send(
            to="alice@example.com",
            subject="Reset your password",
            text_body="Click here: https://test/reset?token=abc",
            html_body="<a href=\"https://test/reset?token=abc\">Click</a>",
        )

    messages = [r.getMessage() for r in caplog.records]
    assert any("to=alice@example.com" in m for m in messages)
    assert any("subject=Reset your password" in m for m in messages)
    assert any("https://test/reset?token=abc" in m for m in messages)


def test_get_mailer_returns_console_when_provider_is_console(monkeypatch):
    """EMAIL_PROVIDER=console → ConsoleMailer."""
    from healthflow.email import mailer as mailer_module
    from healthflow.email.mailer import ConsoleMailer

    monkeypatch.setenv("EMAIL_PROVIDER", "console")
    monkeypatch.setattr(mailer_module, "_INSTANCE", None)

    assert isinstance(mailer_module.get_mailer(), ConsoleMailer)


def test_get_mailer_builds_ses_when_provider_is_ses(monkeypatch):
    """EMAIL_PROVIDER=ses + EMAIL_FROM_ADDRESS → SesMailer wrapping the boto3 client."""
    from healthflow.email import mailer as mailer_module
    from healthflow.email.mailer import SesMailer

    fake_client = MagicMock()
    monkeypatch.setenv("EMAIL_PROVIDER", "ses")
    monkeypatch.setenv("EMAIL_FROM_ADDRESS", "noreply@healthflow.test")
    monkeypatch.setattr(mailer_module, "_INSTANCE", None)
    # Stub boto3.client so we don't need real AWS credentials.
    monkeypatch.setattr(
        "boto3.client", lambda service_name: fake_client if service_name == "ses" else None
    )

    instance = mailer_module.get_mailer()
    assert isinstance(instance, SesMailer)
    assert instance._client is fake_client
    assert instance._from == "noreply@healthflow.test"


def test_get_mailer_raises_when_ses_provider_missing_from_address(monkeypatch):
    """EMAIL_PROVIDER=ses without EMAIL_FROM_ADDRESS → RuntimeError."""
    from healthflow.email import mailer as mailer_module

    monkeypatch.setenv("EMAIL_PROVIDER", "ses")
    monkeypatch.delenv("EMAIL_FROM_ADDRESS", raising=False)
    monkeypatch.setattr(mailer_module, "_INSTANCE", None)

    with pytest.raises(RuntimeError, match="EMAIL_FROM_ADDRESS is required"):
        mailer_module.get_mailer()


# ── Templates ────────────────────────────────────────────────────────────────


def test_render_password_reset_returns_subject_text_html():
    """render_password_reset returns (subject, text_body, html_body) with the reset URL."""
    from healthflow.email.templates import render_password_reset

    subject, text, html = render_password_reset(
        email="alice@example.com",
        reset_url="https://app.example.com/reset-password?token=abc.def.ghi",
    )

    assert subject == "Reset your HealthFlow password"
    assert "https://app.example.com/reset-password?token=abc.def.ghi" in text
    assert "https://app.example.com/reset-password?token=abc.def.ghi" in html
    assert "<a href=" in html
