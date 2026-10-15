"""Pure-ASGI SecurityMiddleware: строгие заголовки на КАЖДЫЙ ответ (включая 4xx/5xx и ошибки CORS).

Подключать ВНУТРИ CORSMiddleware, но снаружи роутеров:
    app.add_middleware(SecurityMiddleware, hsts=settings.is_prod)
"""
from __future__ import annotations

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

# API отдаёт только JSON: запрещаем всё. SPA-CSP живёт в nginx (см. nginx/tenable.conf).
API_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"

_STATIC: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-site",
    "X-Permitted-Cross-Domain-Policies": "none",
    "Content-Security-Policy": API_CSP,
}
HSTS = "max-age=63072000; includeSubDomains; preload"  # preload — только если ВСЕ поддомены на HTTPS


class SecurityMiddleware:
    def __init__(self, app: ASGIApp, *, hsts: bool = True, csp: str = API_CSP) -> None:
        self.app = app
        self.headers = {**_STATIC, "Content-Security-Policy": csp}
        if hsts:
            self.headers["Strict-Transport-Security"] = HSTS

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                h = MutableHeaders(scope=message)
                for k, v in self.headers.items():
                    h[k] = v  # перезаписываем: роутер не должен ослаблять политику
                # Токены/ответы с авторизацией не кэшируем ни браузером, ни прокси.
                if "cache-control" not in h:
                    h["Cache-Control"] = "no-store"
                if "server" in h:
                    del h["server"]
            await send(message)

        await self.app(scope, receive, send_wrapper)
