import logging
import os
from typing import Protocol

logger = logging.getLogger(__name__)


class Mailer(Protocol):
    def send(self, to: str, subject: str, text_body: str, html_body: str) -> None: ...


class ConsoleMailer:
    """Dev/test mailer — logs the email body at INFO. No network I/O."""

    def send(self, to: str, subject: str, text_body: str, html_body: str) -> None:
        logger.info("EMAIL[to=%s, subject=%s]\n%s", to, subject, text_body)


class SesMailer:
    """Production mailer backed by AWS SES."""

    def __init__(self, client, from_address: str):
        self._client = client
        self._from = from_address

    def send(self, to: str, subject: str, text_body: str, html_body: str) -> None:
        self._client.send_email(
            Source=self._from,
            Destination={"ToAddresses": [to]},
            Message={
                "Subject": {"Data": subject},
                "Body": {
                    "Text": {"Data": text_body},
                    "Html": {"Data": html_body},
                },
            },
        )


_INSTANCE: Mailer | None = None


def get_mailer() -> Mailer:
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = _build_mailer()
    return _INSTANCE


def _build_mailer() -> Mailer:
    provider = os.getenv("EMAIL_PROVIDER", "console")
    if provider == "console":
        return ConsoleMailer()
    if provider == "ses":
        import boto3  # local import — boto3 only loaded when actually used
        from_addr = os.getenv("EMAIL_FROM_ADDRESS")
        if not from_addr:
            raise RuntimeError(
                "EMAIL_FROM_ADDRESS is required when EMAIL_PROVIDER=ses"
            )
        return SesMailer(boto3.client("ses"), from_addr)
    raise RuntimeError(f"Unknown EMAIL_PROVIDER: {provider!r}")
