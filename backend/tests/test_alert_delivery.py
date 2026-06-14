from a11ywatch.alerts import delivery
from a11ywatch.alerts.messages import AlertMessage
from a11ywatch.core.config import settings

MSG = AlertMessage(subject="s", body="b")


def _install_fakes(monkeypatch, *, starttls_supported=True):
    """Replace smtplib.SMTP / SMTP_SSL with recorders; return the list of instances created."""
    created = []

    class FakeSMTP:
        kind = "plain"

        def __init__(self, host, port, timeout=None, context=None):
            self.host = host
            self.port = port
            self.context = context
            self.started_tls = False
            self.logged_in = None
            self.sent = None
            self._starttls = starttls_supported
            created.append(self)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def ehlo(self):
            pass

        def has_extn(self, name):
            return name == "starttls" and self._starttls

        def starttls(self, context=None):
            self.started_tls = True

        def login(self, user, password):
            self.logged_in = (user, password)

        def send_message(self, message):
            self.sent = message

    class FakeSMTPSSL(FakeSMTP):
        kind = "ssl"

    monkeypatch.setattr(delivery.smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(delivery.smtplib, "SMTP_SSL", FakeSMTPSSL)
    return created


def test_smtps_uses_implicit_tls_and_logs_in(monkeypatch):
    monkeypatch.setattr(settings, "smtp_url", "smtps://user:pass@mail.test:465")
    created = _install_fakes(monkeypatch)
    delivery.deliver("email", "to@example.com", MSG)
    assert len(created) == 1
    smtp = created[0]
    assert smtp.kind == "ssl"  # implicit TLS, not STARTTLS-on-plaintext
    assert smtp.port == 465
    assert smtp.started_tls is False  # SMTP_SSL is already encrypted; never STARTTLS
    assert smtp.logged_in == ("user", "pass")
    assert smtp.sent is not None


def test_starttls_submission_upgrades_then_logs_in(monkeypatch):
    monkeypatch.setattr(settings, "smtp_url", "smtp://user:pass@mail.test:587")
    created = _install_fakes(monkeypatch, starttls_supported=True)
    delivery.deliver("email", "to@example.com", MSG)
    smtp = created[0]
    assert smtp.kind == "plain"
    assert smtp.started_tls is True  # upgraded before authenticating
    assert smtp.logged_in == ("user", "pass")
    assert smtp.sent is not None


def test_plaintext_relay_never_sends_credentials(monkeypatch):
    # No implicit TLS and the server does not advertise STARTTLS: credentials must NOT
    # travel in cleartext. We still deliver (unauthenticated relay), but never log in.
    monkeypatch.setattr(settings, "smtp_url", "smtp://user:pass@mail.test:25")
    created = _install_fakes(monkeypatch, starttls_supported=False)
    delivery.deliver("email", "to@example.com", MSG)
    smtp = created[0]
    assert smtp.started_tls is False
    assert smtp.logged_in is None
    assert smtp.sent is not None


def test_no_smtp_url_does_not_connect(monkeypatch):
    monkeypatch.setattr(settings, "smtp_url", "")
    created = _install_fakes(monkeypatch)
    delivery.deliver("email", "to@example.com", MSG)
    assert created == []
