import logging
import smtplib
import ssl
from email.message import EmailMessage
from urllib.parse import urlsplit

from a11ywatch.alerts.messages import AlertMessage
from a11ywatch.core.config import settings

log = logging.getLogger(__name__)


def deliver(channel_type: str, target: str, message: AlertMessage) -> None:
    """Deliver one alert to one channel. Email is wired; webhook/slack are stubs.

    Delivery is best-effort per channel: the caller dispatches to each channel
    independently so one bad endpoint can't suppress the others.
    """
    if channel_type == "email":
        _send_email(target, message)
    elif channel_type == "webhook":
        _post_webhook(target, message)
    elif channel_type == "slack":
        _post_slack(target, message)
    else:
        log.warning("unknown alert channel type %r — dropping alert to %s", channel_type, target)


def _send_email(target: str, message: AlertMessage) -> None:
    if not settings.smtp_url:
        # No mail transport configured (e.g. dev/test): log instead of sending.
        log.info("[alert:email→%s] %s", target, message.subject)
        return
    email = EmailMessage()
    email["Subject"] = message.subject
    email["To"] = target
    email["From"] = settings.operator_alert_email or "alerts@a11ywatch.local"
    email.set_content(message.body)

    url = urlsplit(settings.smtp_url)
    host = url.hostname or "localhost"
    context = ssl.create_default_context()

    if url.scheme == "smtps":
        # Implicit TLS (conventionally port 465): TLS is negotiated at connect time.
        with smtplib.SMTP_SSL(host, url.port or 465, timeout=10, context=context) as smtp:
            _login_if_secure(smtp, url, tls_active=True)
            smtp.send_message(email)
    else:
        # Plaintext connect, then opportunistic STARTTLS upgrade (submission port 587).
        with smtplib.SMTP(host, url.port or 25, timeout=10) as smtp:
            smtp.ehlo()
            tls_active = False
            if smtp.has_extn("starttls"):
                smtp.starttls(context=context)
                smtp.ehlo()
                tls_active = True
            _login_if_secure(smtp, url, tls_active=tls_active)
            smtp.send_message(email)
    log.info("sent alert email to %s", target)


def _login_if_secure(smtp, url, *, tls_active: bool) -> None:
    """Authenticate only over an encrypted connection — never leak credentials in cleartext."""
    if not url.username:
        return
    if not tls_active:
        log.warning(
            "SMTP credentials provided but the connection is not encrypted; "
            "skipping AUTH to avoid sending them in cleartext"
        )
        return
    smtp.login(url.username, url.password or "")


def _post_webhook(target: str, message: AlertMessage) -> None:
    # Webhook delivery is a Phase-5 stub; real POST lands when a customer needs it.
    log.info("[alert:webhook→%s] %s", target, message.subject)


def _post_slack(target: str, message: AlertMessage) -> None:
    # Slack delivery is a Phase-5 stub; real POST lands when a customer needs it.
    log.info("[alert:slack→%s] %s", target, message.subject)
