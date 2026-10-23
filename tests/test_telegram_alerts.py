import asyncio
import sys
import types

if "structlog" not in sys.modules:
    try:
        import structlog  # noqa: F401
    except ImportError:

        class _L:
            def __init__(self):
                self.events = []

            def __getattr__(self, name):
                return lambda event, **kw: self.events.append((name, event, kw))

        _shared = _L()
        m = types.ModuleType("structlog")
        m.get_logger = lambda *_a, **_k: _shared
        sys.modules["structlog"] = m
if "httpx" not in sys.modules:
    try:
        import httpx  # noqa: F401
    except ImportError:
        h = types.ModuleType("httpx")
        h.AsyncClient = object
        sys.modules["httpx"] = h

import pytest

from app.core import notifications, telegram

TOKEN = "123456:SECRET-TOKEN"


class Resp:
    def __init__(self, code):
        self.status_code = code


class Client:
    def __init__(self, code=200, exc=None):
        self.code, self.exc, self.calls = code, exc, []

    async def post(self, url, json):
        self.calls.append((url, json))
        if self.exc:
            raise self.exc
        return Resp(self.code)


@pytest.fixture(autouse=True)
def _token(monkeypatch):
    monkeypatch.setattr(telegram, "_token", lambda: TOKEN)


def run(c):
    return asyncio.run(c)


def test_success_payload():
    c = Client()
    assert run(telegram.send_telegram_alert("hi", "-100123", client=c)) is True
    url, body = c.calls[0]
    assert url == f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    assert body["chat_id"] == "-100123" and body["parse_mode"] == "HTML"


@pytest.mark.parametrize("code", [400, 401, 403, 429, 500])
def test_http_errors_return_false(code):
    assert run(telegram.send_telegram_alert("hi", "42", client=Client(code))) is False


def test_network_error_never_raises_and_token_not_logged(capsys):
    class Boom(Exception):
        pass

    c = Client(exc=Boom(f"GET https://api.telegram.org/bot{TOKEN}/sendMessage failed"))
    assert run(telegram.send_telegram_alert("hi", "42", client=c)) is False
    assert (
        TOKEN not in repr(getattr(telegram.log, "events", ""))
        and TOKEN not in capsys.readouterr().out
    )


def test_timeout_is_swallowed():
    assert (
        run(
            telegram.send_telegram_alert(
                "hi", "42", client=Client(exc=asyncio.TimeoutError())
            )
        )
        is False
    )


@pytest.mark.parametrize("bad", ["", "abc", "12 34", "@ab", "1; DROP", "http://x"])
def test_bad_chat_id_not_sent(bad):
    c = Client()
    assert (
        run(telegram.send_telegram_alert("hi", bad, client=c)) is False and not c.calls
    )


def test_no_token_disables(monkeypatch):
    monkeypatch.setattr(telegram, "_token", lambda: None)
    c = Client()
    assert (
        run(telegram.send_telegram_alert("hi", "42", client=c)) is False and not c.calls
    )


def test_long_message_truncated():
    c = Client()
    run(telegram.send_telegram_alert("x" * 10_000, "42", client=c))
    assert len(c.calls[0][1]["text"]) == 4096


def test_message_format_and_escaping():
    m = notifications.build_telegram_message("<b>ООО</b> & Ко", "yandex", 5)
    assert (
        m.startswith("🚨")
        and "&lt;b&gt;ООО&lt;/b&gt; &amp; Ко" in m
        and "yandex" in m
        and "5/5" in m
    )


# --- notifications
def _patch_tg(monkeypatch, result=True, exc=None):
    sent = []

    async def fake(message, chat_id):
        sent.append((message, chat_id))
        if exc:
            raise exc
        return result

    monkeypatch.setattr(notifications, "send_telegram_alert", fake)
    return sent


def _kw(**over):
    base = dict(
        company_name="Acme",
        company_meta_config={"telegram_chat_id": "-1001"},
        platform="google",
        threat_level=5,
        review_id="r1",
    )
    base.update(over)
    return base


def test_below_threshold_sends_nothing(monkeypatch):
    sent = _patch_tg(monkeypatch)
    assert (
        run(notifications.check_and_notify_critical_threat(**_kw(threat_level=3)))
        is False
        and not sent
    )


def test_no_chat_id_skips_telegram_but_email_goes(monkeypatch):
    sent, emails = _patch_tg(monkeypatch), []

    async def email(**kw):
        emails.append(kw)

    assert run(
        notifications.check_and_notify_critical_threat(
            **_kw(company_meta_config={}), email_notifier=email
        )
    )
    assert not sent and len(emails) == 1


def test_telegram_and_email_run_in_parallel(monkeypatch):
    order = []

    async def fake_tg(message, chat_id):
        order.append("tg_start")
        await asyncio.sleep(0.05)
        order.append("tg_end")
        return True

    async def email(**kw):
        order.append("email_start")
        await asyncio.sleep(0.05)
        order.append("email_end")

    monkeypatch.setattr(notifications, "send_telegram_alert", fake_tg)
    run(notifications.check_and_notify_critical_threat(**_kw(), email_notifier=email))
    assert order.index("tg_start") < order.index("email_end") and order.index(
        "email_start"
    ) < order.index("tg_end")


def test_telegram_failure_does_not_break_pipeline(monkeypatch):
    _patch_tg(monkeypatch, exc=RuntimeError("boom"))
    assert run(notifications.check_and_notify_critical_threat(**_kw())) is True
    _patch_tg(monkeypatch, result=False)
    assert run(notifications.check_and_notify_critical_threat(**_kw())) is True


def test_email_failure_propagates_but_telegram_still_sent(monkeypatch):
    sent = _patch_tg(monkeypatch)

    async def email(**kw):
        raise ConnectionError("smtp down")

    with pytest.raises(ConnectionError):
        run(
            notifications.check_and_notify_critical_threat(
                **_kw(), email_notifier=email
            )
        )
    assert len(sent) == 1
