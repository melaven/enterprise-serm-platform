# Правки в существующем коде

## app/core/security.py  (get_auth_context читает cookie; JWKS-outage -> 503)
```diff
-from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
-from jwt import PyJWKClient, PyJWTError
+from fastapi import Request
+from jwt import PyJWKClient, PyJWTError
+from jwt.exceptions import PyJWKClientConnectionError
+from app.core.cookie_auth import token_from_request
@@
-async def get_auth_context(creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)], settings: ...):
-    if creds is None:
-        raise _unauthorized("Missing bearer token")
+async def get_auth_context(request: Request, settings: ...):
+    token = token_from_request(request)
+    if token is None:
+        raise _unauthorized("Not authenticated")
     try:
-        claims = await run_in_threadpool(_decode, creds.credentials, settings)
+        claims = await run_in_threadpool(_decode, token, settings)
+    except PyJWKClientConnectionError as exc:       # падение JWKS != невалидный токен
+        raise HTTPException(503, "Auth keys unavailable") from exc
     except PyJWTError as exc:
```
Также: `algorithms=["HS256"]` только если задан `supabase_jwt_secret`; в prod предпочитать JWKS (ES256).

## app/main.py
```python
app.add_middleware(SecurityMiddleware, hsts=settings.is_prod)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins_list,  # НИКОГДА "*" с credentials
                   allow_credentials=True, allow_methods=["GET","POST","PUT","PATCH","DELETE"],
                   allow_headers=["Content-Type","X-CSRF-Token","X-Correlation-ID"], max_age=600)
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None) if settings.is_prod else FastAPI()
app.include_router(cookie_auth.router)
# глобальный CSRF на мутации:
app = FastAPI(dependencies=[Depends(require_csrf)])   # login/refresh сами исключены: login без cookie-сессии
```
Порядок: Security (внутри) -> CORS (самый внешний) -> tracing. login не требует CSRF (нет сессии; защита — SameSite + Origin-проверка в nginx).
Settings: добавить `csrf_secret: SecretStr (>=32 байт)`, `supabase_anon_key`, `cors_origins_list`.

## Frontend (redesign/src/lib/api/client.ts)
```ts
const api = axios.create({ baseURL, withCredentials: true });     // cookie уходят сами
function csrf(): string | undefined {
  return document.cookie.split('; ').find(c => c.startsWith('tn_csrf='))?.slice(8);
}
api.interceptors.request.use(cfg => {
  if (!['get','head','options'].includes((cfg.method ?? 'get').toLowerCase())) {
    const t = csrf(); if (t) cfg.headers.set('X-CSRF-Token', t);
  }
  return cfg;                                                      // Authorization больше НЕ ставим
});
// 401 -> один single-flight POST /auth/refresh, затем повтор запроса; при провале -> session.clear() + /login
```
Удалить любое хранение токена в localStorage/Zustand persist (`partialize` без токенов) — в сторе только `user`, `companyId`, `role`.
