"""Kimlik doğrulama arayüzü ve oturum yönetimi (F1 / I01).

Kullanıcı arayüzüne tarayıcıdan güvenli giriş yapılabilmesi için oturum sayfası.
"""

from __future__ import annotations

import secrets
from urllib.parse import unquote

from fastapi import APIRouter, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse

from politikdesk import __version__
from politikdesk.config import get_settings
from politikdesk.web.ui import esc, icon
from politikdesk.web.ui.css import stylesheet
from politikdesk.web.ui.nonce import nonce_attr

router = APIRouter(tags=["auth"])


def _render_login_page(
    error: str = "",
    next_url: str = "/feed",
) -> str:
    css = stylesheet()
    theme_boot = (
        "(function(){try{var t=localStorage.getItem('pd-theme');"
        "if(t==='dark'||t==='light')document.documentElement.dataset.theme=t;}"
        "catch(e){}})()"
    )

    error_box = ""
    if error:
        error_box = f"""
        <div class="login-alert" role="alert">
            <span class="login-alert-icon">{icon('warning', 16)}</span>
            <span>{esc(error)}</span>
        </div>
        """

    clean_next = esc(next_url) if next_url and next_url.startswith("/") else "/feed"

    return f"""<!doctype html>
<html lang="tr" data-theme="dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Giriş Yap — PolitikDesk</title>
<link rel="icon" type="image/svg+xml" href="/static/favicon.svg">
<link rel="manifest" href="/static/manifest.webmanifest">
<script{nonce_attr()}>{theme_boot}</script>
<style>{css}</style>
<style>
.login-wrap {{
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-4);
  background: var(--color-bg);
}}
.login-card {{
  width: 100%;
  max-width: 420px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  padding: var(--space-6);
}}
.login-brand {{
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-2);
}}
.login-logo {{
  width: 36px;
  height: 36px;
  border-radius: var(--radius-md);
  background: var(--color-accent);
  color: var(--color-fg-on-accent);
  display: flex;
  align-items: center;
  justify-content: center;
}}
.login-title {{
  font-size: var(--text-xl);
  font-weight: var(--weight-bold);
  color: var(--color-fg);
  margin: 0;
}}
.login-sub {{
  color: var(--color-fg-muted);
  font-size: var(--text-sm);
  margin-bottom: var(--space-5);
}}
.login-alert {{
  background: var(--color-surface-sunken);
  border: 1px solid var(--color-border-strong);
  color: var(--color-fg);
  padding: var(--space-3);
  border-radius: var(--radius-md);
  margin-bottom: var(--space-4);
  font-size: var(--text-sm);
  display: flex;
  align-items: center;
  gap: var(--space-2);
}}
.login-alert-icon {{
  display: flex;
  align-items: center;
  color: var(--color-fg-muted);
}}
.login-field {{
  margin-bottom: var(--space-4);
}}
.login-label {{
  display: block;
  font-size: var(--text-xs);
  font-weight: var(--weight-semibold);
  color: var(--color-fg-muted);
  margin-bottom: var(--space-2);
}}
.login-input {{
  width: 100%;
  padding: var(--space-3);
  font-size: var(--text-sm);
  font-family: var(--font-mono);
  background: var(--color-surface-sunken);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-md);
  color: var(--color-fg);
  box-sizing: border-box;
}}
.login-input:focus {{
  outline: none;
  border-color: var(--color-accent);
  box-shadow: 0 0 0 2px var(--color-border-strong);
}}
.login-btn {{
  width: 100%;
  padding: var(--space-3);
  background: var(--color-accent);
  color: var(--color-fg-on-accent);
  border: none;
  border-radius: var(--radius-md);
  font-size: var(--text-sm);
  font-weight: var(--weight-semibold);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  transition: opacity var(--motion-fast);
}}
.login-btn:hover {{
  opacity: 0.92;
}}
.login-foot {{
  margin-top: var(--space-5);
  padding-top: var(--space-4);
  border-top: 1px solid var(--color-border);
  font-size: var(--text-xs);
  color: var(--color-fg-subtle);
  display: flex;
  align-items: center;
  justify-content: space-between;
}}
</style>
</head>
<body>
<main class="login-wrap">
  <div class="login-card">
    <div class="login-brand">
      <div class="login-logo">{icon('shield', 20)}</div>
      <h1 class="login-title">PolitikDesk</h1>
    </div>
    <div class="login-sub">Editoryal Çalışma Masası — Oturum Aç</div>
    {error_box}
    <form method="post" action="/login">
      <input type="hidden" name="next" value="{clean_next}">
      <div class="login-field">
        <label class="login-label" for="token">Güvenlik Belirteci (PD_API_TOKEN)</label>
        <input class="login-input" type="password" id="token" name="token" placeholder="pd_sec_token_..." required autofocus autocomplete="current-password">
      </div>
      <button class="login-btn" type="submit">
        <span>Giriş Yap →</span>
      </button>
    </form>
    <div class="login-foot">
      <span>Kanıt Temelli Editoryal Masa</span>
      <span class="mono">v{__version__}</span>
    </div>
  </div>
</main>
</body>
</html>"""


@router.get("/login", response_model=None)
def login_get(request: Request, next: str = "/feed", token: str | None = None) -> Response:
    target_next = unquote(next) if next and next.startswith("/") else "/feed"
    settings = get_settings()
    configured_token = settings.api_token

    # Token ayarlı değilse direkt hedefe git
    if not configured_token:
        return RedirectResponse(url=target_next, status_code=303)

    # URL parametresi veya çerezde geçerli token varsa direkt yönlendir
    provided = token or request.cookies.get("pd_token") or request.cookies.get("token")
    if provided and secrets.compare_digest(provided.strip(), configured_token):
        response = RedirectResponse(url=target_next, status_code=303)
        response.set_cookie(
            key="pd_token",
            value=configured_token,
            httponly=True,
            samesite="lax",
            secure=request.url.scheme == "https",
            max_age=30 * 86400,
            path="/",
        )
        return response

    html = _render_login_page(next_url=target_next)
    return HTMLResponse(content=html)


@router.post("/login", response_model=None)
async def login_post(request: Request) -> Response:
    body_bytes = await request.body()
    from urllib.parse import parse_qs

    form_data = parse_qs(body_bytes.decode("utf-8", errors="replace"))
    token = form_data.get("token", [""])[0].strip()
    raw_next = form_data.get("next", ["/feed"])[0].strip()
    target_next = unquote(raw_next) if raw_next and raw_next.startswith("/") else "/feed"

    settings = get_settings()
    configured_token = settings.api_token

    if not configured_token:
        return RedirectResponse(url=target_next, status_code=303)

    if token and secrets.compare_digest(token, configured_token):
        response = RedirectResponse(url=target_next, status_code=303)
        response.set_cookie(
            key="pd_token",
            value=configured_token,
            httponly=True,
            samesite="lax",
            secure=request.url.scheme == "https",
            max_age=30 * 86400,
            path="/",
        )
        return response

    html = _render_login_page(
        error="Girilen güvenlik belirteci geçersiz. Lütfen doğru PD_API_TOKEN değerini girin.",
        next_url=target_next,
    )
    return HTMLResponse(content=html, status_code=401)


@router.get("/logout", response_model=None)
def logout_get() -> RedirectResponse:
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("pd_token", path="/")
    response.delete_cookie("token", path="/")
    return response
