"""
FundLens authentication and per-user portfolio storage (Supabase).

Configure in Streamlit secrets:
  SUPABASE_URL, SUPABASE_ANON_KEY
Optional: AUTH_REDIRECT_URL (password reset redirect; defaults to Site URL)
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any

_SESSION_TIMEOUT_SEC = 30 * 60  # 30 minutes idle logout

import pandas as pd
import streamlit as st

try:
    from supabase import Client, create_client
except ImportError:
    Client = Any  # type: ignore[misc, assignment]
    create_client = None  # type: ignore[misc, assignment]

_USER_ID_MIN = 8
_USER_ID_RE = re.compile(r"^[a-zA-Z0-9_]+$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PASSWORD_MIN = 8

_PORTFOLIO_GATED_PAGES = frozenset({
    "portfolio_hub",
    "portfolio_upload",
    "portfolio_xray",
    "portfolio_track",
})

_VALID_RETURN_PAGES = frozenset({
    "home",
    "analyse_funds",
    "category",
    "explorer",
    "compare",
    "stock_explorer",
    "overlap_drilldown",
    "portfolio_hub",
    "portfolio_upload",
    "portfolio_xray",
    "portfolio_track",
    "account",
})

_AUTH_DISK_DIR = Path(__file__).resolve().parent / ".streamlit" / "auth_sessions"
_BIND_THROTTLE_SEC = 90
_TOKEN_REFRESH_THROTTLE_SEC = 120

_AUTH_STATE_KEYS = (
    "fl_auth_access_token",
    "fl_auth_refresh_token",
    "fl_auth_uid",
    "fl_auth_user_id",
    "fl_auth_email",
    "fl_auth_last_active",
)
_AUTH_BACKUP_KEY = "_fl_auth_backup"


def portfolio_gated_pages() -> frozenset[str]:
    return _PORTFOLIO_GATED_PAGES


def _normalize_user_id(raw: str) -> str:
    return (raw or "").strip().lower()


def validate_user_id(raw: str) -> str | None:
    uid = _normalize_user_id(raw)
    if len(uid) < _USER_ID_MIN:
        return f"User ID must be at least {_USER_ID_MIN} characters."
    if not _USER_ID_RE.match(uid):
        return "User ID may only contain letters, numbers, and underscores."
    return None


def validate_email(raw: str) -> str | None:
    em = (raw or "").strip().lower()
    if not em or not _EMAIL_RE.match(em):
        return "Enter a valid email address."
    return None


def validate_password(raw: str) -> str | None:
    if len(raw or "") < _PASSWORD_MIN:
        return f"Password must be at least {_PASSWORD_MIN} characters."
    return None


def supabase_configured() -> bool:
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_ANON_KEY"]
        return bool(url and key)
    except Exception:
        return bool(os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_ANON_KEY"))


def _get_secrets() -> tuple[str, str] | None:
    try:
        return str(st.secrets["SUPABASE_URL"]).strip(), str(st.secrets["SUPABASE_ANON_KEY"]).strip()
    except Exception:
        url = os.getenv("SUPABASE_URL", "").strip()
        key = os.getenv("SUPABASE_ANON_KEY", "").strip()
        return (url, key) if url and key else None


def _streamlit_session_id() -> str:
    try:
        from streamlit.runtime.scriptrunner.script_run_context import get_script_run_ctx

        ctx = get_script_run_ctx()
        if ctx is not None and getattr(ctx, "session_id", None):
            return str(ctx.session_id)
    except Exception:
        pass
    return "default"


def get_client() -> Client | None:
    """One Supabase client per Streamlit browser session (not process-global cache)."""
    cfg = _get_secrets()
    if not cfg or create_client is None:
        return None
    cache_key = "_fl_supabase_client"
    client = st.session_state.get(cache_key)
    if client is None:
        client = create_client(cfg[0], cfg[1])
        st.session_state[cache_key] = client
    return client


def _redirect_url() -> str:
    try:
        u = st.secrets.get("AUTH_REDIRECT_URL", "")
        if u:
            return str(u).strip()
    except Exception:
        pass
    return os.getenv("AUTH_REDIRECT_URL", "http://localhost:8501").strip()


def has_auth_tokens() -> bool:
    return bool(
        st.session_state.get("fl_auth_access_token")
        and st.session_state.get("fl_auth_refresh_token")
    )


def is_logged_in() -> bool:
    _restore_from_backup()
    return bool(
        st.session_state.get("fl_auth_uid")
        and st.session_state.get("fl_auth_user_id")
        and has_auth_tokens()
    )


def _has_local_auth() -> bool:
    return is_logged_in()


def current_user_id() -> str | None:
    return st.session_state.get("fl_auth_user_id")


def current_email() -> str | None:
    return st.session_state.get("fl_auth_email")


def auth_return_page() -> str:
    p = st.session_state.get("_auth_return_page", "home")
    return p if p in _VALID_RETURN_PAGES else "home"


def set_auth_return_page(page: str) -> None:
    if page in _VALID_RETURN_PAGES:
        st.session_state["_auth_return_page"] = page


def is_return_page(page: str) -> bool:
    return page in _VALID_RETURN_PAGES


def persist_auth_snapshot() -> None:
    """Save auth keys to session backup + disk (survives URL navigation)."""
    _backup_auth_state()


def touch_activity() -> None:
    st.session_state.fl_auth_last_active = time.time()


def _store_session(client: Client, session: Any, *, user_id: str, email: str) -> None:
    _persist_tokens_from_session(session)
    st.session_state.fl_auth_uid = session.user.id
    st.session_state.fl_auth_user_id = user_id
    st.session_state.fl_auth_email = email
    touch_activity()
    _backup_auth_state()
    try:
        if session.access_token and session.refresh_token:
            client.auth.set_session(session.access_token, session.refresh_token)
    except Exception:
        pass


def _auth_disk_path() -> Path:
    _AUTH_DISK_DIR.mkdir(parents=True, exist_ok=True)
    return _AUTH_DISK_DIR / f"{_streamlit_session_id()}.json"


def _save_auth_disk() -> None:
    snap = {k: st.session_state.get(k) for k in (*_AUTH_STATE_KEYS, _AUTH_BACKUP_KEY)}
    snap = {k: v for k, v in snap.items() if v}
    if snap.get("fl_auth_access_token") and snap.get("fl_auth_refresh_token"):
        try:
            _auth_disk_path().write_text(json.dumps(snap), encoding="utf-8")
        except Exception:
            pass


def _load_auth_disk() -> None:
    path = _auth_disk_path()
    if not path.is_file():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return
    if not isinstance(data, dict):
        return
    for key, val in data.items():
        if val and not st.session_state.get(key):
            st.session_state[key] = val


def _backup_auth_state() -> None:
    snap = {k: st.session_state[k] for k in _AUTH_STATE_KEYS if st.session_state.get(k)}
    if snap.get("fl_auth_access_token") and snap.get("fl_auth_refresh_token"):
        st.session_state[_AUTH_BACKUP_KEY] = snap
        _save_auth_disk()


def _restore_from_backup() -> None:
    bak = st.session_state.get(_AUTH_BACKUP_KEY)
    if not isinstance(bak, dict):
        return
    for key in _AUTH_STATE_KEYS:
        val = bak.get(key)
        if val and not st.session_state.get(key):
            st.session_state[key] = val


def _clear_auth_state() -> None:
    for key in (*_AUTH_STATE_KEYS, _AUTH_BACKUP_KEY, "_fl_supabase_client", "_fl_auth_last_bind"):
        st.session_state.pop(key, None)
    try:
        path = _auth_disk_path()
        if path.is_file():
            path.unlink()
    except Exception:
        pass


def clear_portfolio_session_state() -> None:
    st.session_state.pop("portfolio_df", None)
    st.session_state.pop("portfolio_page_mode", None)
    st.session_state.pop("_portfolio_edit_type", None)
    st.session_state.pop("portfolio_staged_df", None)
    st.session_state.pop("fl_portfolio_fund_list", None)
    st.session_state.pop("fl_editor_rows", None)
    st.session_state.pop("manual_fund_select", None)
    st.session_state.pop("fl_portfolio_cache_warmed", None)
    for key in list(st.session_state.keys()):
        if key in ("portfolio_entry_mode",) or key.startswith(
            ("m_amt_", "m_units_", "m_nav_", "m_acct_", "m_date_", "m_plan_")
        ):
            del st.session_state[key]


def _persist_tokens_from_session(session: Any) -> None:
    """Never overwrite stored tokens with empty values (Supabase may omit refresh_token)."""
    if not session:
        return
    access = getattr(session, "access_token", None)
    refresh = getattr(session, "refresh_token", None)
    if access:
        st.session_state.fl_auth_access_token = access
    if refresh:
        st.session_state.fl_auth_refresh_token = refresh
    if getattr(session, "user", None):
        st.session_state.fl_auth_uid = session.user.id
        if not st.session_state.get("fl_auth_email"):
            st.session_state.fl_auth_email = session.user.email or ""
    if access and refresh:
        _backup_auth_state()


def _is_jwt_expired_error(ex: Exception) -> bool:
    msg = str(ex).lower()
    return "jwt expired" in msg or "pgrst303" in msg


def _apply_access_to_client(client: Client, access: str) -> None:
    try:
        client.postgrest.auth(access)
    except Exception:
        pass


def _refresh_supabase_session(client: Client) -> bool:
    """Exchange refresh token for a new access token (fixes JWT expired / PGRST303)."""
    refresh = st.session_state.get("fl_auth_refresh_token")
    if not refresh:
        return False
    try:
        res = client.auth.refresh_session(refresh)
        if res.session:
            _persist_tokens_from_session(res.session)
            _apply_access_to_client(client, res.session.access_token)
            _save_auth_disk()
            st.session_state["_fl_token_refreshed_at"] = time.time()
            return True
    except Exception:
        pass
    return False


def _try_bind_supabase_client(client: Client, access: str, refresh: str) -> None:
    """Best-effort Supabase bind; never clears Streamlit auth session on failure."""
    try:
        res = client.auth.set_session(access, refresh)
        if res.session:
            _persist_tokens_from_session(res.session)
            _apply_access_to_client(client, res.session.access_token)
            return
    except Exception:
        pass
    _refresh_supabase_session(client)


def _sync_supabase_auth(client: Client, *, force_refresh: bool = False) -> bool:
    """Attach a valid JWT to PostgREST (refresh at most once per ~2 min unless forced)."""
    refresh = st.session_state.get("fl_auth_refresh_token")
    if not refresh:
        return False
    access = st.session_state.get("fl_auth_access_token")
    last_refresh = float(st.session_state.get("_fl_token_refreshed_at") or 0)
    token_fresh = (time.time() - last_refresh) < _TOKEN_REFRESH_THROTTLE_SEC

    if force_refresh or not token_fresh:
        if _refresh_supabase_session(client):
            return True
    elif access:
        _apply_access_to_client(client, access)
        return True

    if access:
        _try_bind_supabase_client(client, access, refresh)
        access = st.session_state.get("fl_auth_access_token") or access
        _apply_access_to_client(client, access)
        return bool(access)
    return False


def refresh_auth_session() -> bool:
    """Public: force-refresh Supabase JWT (e.g. Retry on Manage portfolio)."""
    client = get_client()
    if client is None or not has_auth_tokens():
        return False
    ok = _sync_supabase_auth(client, force_refresh=True)
    if ok:
        _invalidate_family_cache()
    return ok


def _effective_auth_uid(client: Client) -> str | None:
    """auth.users.id from JWT — must match owner_user_id / user_id in RLS."""
    uid = st.session_state.get("fl_auth_uid")
    if uid:
        return str(uid)
    _sync_supabase_auth(client)
    uid = st.session_state.get("fl_auth_uid")
    return str(uid) if uid else None


def _recover_profile_from_supabase(client: Client) -> None:
    """Fill missing user_id/email from Supabase when tokens are still in session_state."""
    if st.session_state.get("fl_auth_user_id") and st.session_state.get("fl_auth_uid"):
        return

    access = st.session_state.get("fl_auth_access_token")
    if access and not st.session_state.get("fl_auth_uid"):
        try:
            res = client.auth.get_user(access)
            user = getattr(res, "user", None)
            if user:
                st.session_state.fl_auth_uid = user.id
                if not st.session_state.get("fl_auth_email"):
                    st.session_state.fl_auth_email = user.email or ""
                meta = getattr(user, "user_metadata", None) or {}
                if isinstance(meta, dict) and meta.get("user_id"):
                    st.session_state.fl_auth_user_id = _normalize_user_id(
                        str(meta["user_id"])
                    )
        except Exception:
            pass

    uid = st.session_state.get("fl_auth_uid")
    if uid and not st.session_state.get("fl_auth_user_id"):
        try:
            row = (
                client.table("profiles")
                .select("user_id,email")
                .eq("id", uid)
                .limit(1)
                .execute()
            )
            if row.data:
                data = row.data[0]
                if data.get("user_id"):
                    st.session_state.fl_auth_user_id = _normalize_user_id(
                        str(data["user_id"])
                    )
                if data.get("email") and not st.session_state.get("fl_auth_email"):
                    st.session_state.fl_auth_email = data["email"]
        except Exception:
            pass


def init_auth() -> None:
    """
    Restore Supabase session from Streamlit state on every rerun.
    Never clears tokens on bind failure — only idle timeout or explicit logout.
    """
    _load_auth_disk()
    _restore_from_backup()
    access = st.session_state.get("fl_auth_access_token")
    refresh = st.session_state.get("fl_auth_refresh_token")

    if not access or not refresh:
        _restore_from_backup()
        _load_auth_disk()
        access = st.session_state.get("fl_auth_access_token")
        refresh = st.session_state.get("fl_auth_refresh_token")
    if not access or not refresh:
        if st.session_state.get("fl_auth_uid"):
            _clear_auth_state()
        return

    last = st.session_state.get("fl_auth_last_active")
    if last is not None and (time.time() - last) > _SESSION_TIMEOUT_SEC:
        logout()
        return

    touch_activity()
    client = get_client()
    if client is not None:
        last_bind = float(st.session_state.get("_fl_auth_last_bind") or 0)
        if time.time() - last_bind > _BIND_THROTTLE_SEC:
            _refresh_supabase_session(client)
            st.session_state["_fl_auth_last_bind"] = time.time()
        _recover_profile_from_supabase(client)
    if has_auth_tokens():
        _backup_auth_state()


def restore_session() -> None:
    """Portfolio helpers: restore keys only — avoid extra Supabase refresh on every widget rerun."""
    _restore_from_backup()


def logout() -> None:
    client = get_client()
    if client is not None:
        try:
            client.auth.sign_out()
        except Exception:
            pass
    _clear_auth_state()
    clear_portfolio_session_state()


_SCHEMA_SETUP_MSG = (
    "Database setup is missing. In Supabase Dashboard → SQL → New query, "
    "paste and run the full script from `supabase/schema.sql`, then try again."
)


def _is_schema_missing_error(ex: Exception) -> bool:
    msg = str(ex).lower()
    return "get_email_for_user_id" in msg or "pgrst202" in msg or "schema cache" in msg


def _user_id_taken(client: Client, uid: str) -> bool:
    try:
        avail = client.rpc("is_user_id_available", {"p_user_id": uid}).execute().data
        return avail is False
    except Exception:
        return False


def _upsert_profile_row(client: Client, auth_id: str, uid: str, email: str) -> tuple[bool, str]:
    """Create/update profiles row (requires active auth session)."""
    try:
        client.rpc(
            "upsert_profile",
            {"p_id": auth_id, "p_user_id": uid, "p_email": email},
        ).execute()
        return True, ""
    except Exception as ex:
        if _is_schema_missing_error(ex) or "upsert_profile" in str(ex).lower():
            try:
                client.table("profiles").insert(
                    {"id": auth_id, "user_id": uid, "email": email}
                ).execute()
                return True, ""
            except Exception as ex2:
                err = str(_auth_error_message(ex2) or ex2).lower()
                if "duplicate" in err or "23505" in err:
                    return True, ""
                return False, _auth_error_message(ex2) or str(ex2)
        err = str(_auth_error_message(ex) or ex).lower()
        if "duplicate" in err or "23505" in err:
            return True, ""
        return False, _auth_error_message(ex) or str(ex)


def _rpc_email_for_user_id(client: Client, user_id: str) -> str | None:
    try:
        res = client.rpc("get_email_for_user_id", {"p_user_id": user_id}).execute()
    except Exception as ex:
        if _is_schema_missing_error(ex):
            raise RuntimeError(_SCHEMA_SETUP_MSG) from ex
        raise
    data = res.data
    if isinstance(data, str) and data:
        return data
    if isinstance(data, list) and data:
        return str(data[0]) if data[0] else None
    return None


def login(user_id_raw: str, password: str) -> tuple[bool, str]:
    err = validate_user_id(user_id_raw)
    if err:
        return False, err
    pw_err = validate_password(password)
    if pw_err:
        return False, pw_err

    client = get_client()
    if client is None:
        return False, "Sign-in is not configured. Add Supabase secrets to the app."

    uid = _normalize_user_id(user_id_raw)
    try:
        email = _rpc_email_for_user_id(client, uid)
    except RuntimeError as ex:
        return False, str(ex)
    except Exception as ex:
        if _is_schema_missing_error(ex):
            return False, _SCHEMA_SETUP_MSG
        return False, _auth_error_message(ex) or "Sign-in failed."

    if not email:
        return False, "User ID or password is incorrect."

    try:
        res = client.auth.sign_in_with_password({"email": email, "password": password})
    except Exception as ex:
        return False, _auth_error_message(ex) or "User ID or password is incorrect."

    if not res.session:
        return False, "Sign-in failed. Please try again."

    _store_session(client, res.session, user_id=uid, email=email)
    _upsert_profile_row(client, res.session.user.id, uid, email)
    return True, ""


def register(user_id_raw: str, email_raw: str, password: str) -> tuple[bool, str]:
    uid_err = validate_user_id(user_id_raw)
    if uid_err:
        return False, uid_err
    em_err = validate_email(email_raw)
    if em_err:
        return False, em_err
    pw_err = validate_password(password)
    if pw_err:
        return False, pw_err

    client = get_client()
    if client is None:
        return False, "Registration is not configured. Add Supabase secrets to the app."

    uid = _normalize_user_id(user_id_raw)
    email = (email_raw or "").strip().lower()

    try:
        avail_uid = client.rpc("is_user_id_available", {"p_user_id": uid}).execute().data
        if avail_uid is False:
            return False, "This User ID is already taken."
        avail_em = client.rpc("is_email_available", {"p_email": email}).execute().data
        if avail_em is False:
            return False, "This email is already registered."
    except Exception as ex:
        if _is_schema_missing_error(ex):
            return False, _SCHEMA_SETUP_MSG

    try:
        res = client.auth.sign_up(
            {
                "email": email,
                "password": password,
                "options": {"data": {"user_id": uid}},
            }
        )
    except Exception as ex:
        return False, _auth_error_message(ex) or "Registration failed."

    if not res.user:
        return False, "Registration failed. Please try again."

    if not res.session:
        if _user_id_taken(client, uid):
            return (
                False,
                "Account created. Your User ID is saved. "
                "Confirm the email Supabase sent (check spam), then use **Sign in**. "
                "For instant access without email: turn off **Confirm email** under "
                "Authentication → Providers → Email.",
            )
        return (
            False,
            "Auth user was created but your User ID was not saved. "
            "In Supabase SQL Editor, run the trigger section at the end of `supabase/schema.sql` "
            "(or the full file again), then delete the user under Authentication → Users "
            "and register again.",
        )

    _store_session(client, res.session, user_id=uid, email=email)
    ok, err = _upsert_profile_row(client, res.user.id, uid, email)
    if not ok:
        logout()
        return False, f"Could not save profile: {err}"

    return True, ""


def reset_password_by_user_id(user_id_raw: str) -> tuple[bool, str]:
    err = validate_user_id(user_id_raw)
    if err:
        return False, err
    client = get_client()
    if client is None:
        return False, "Password reset is not configured."

    uid = _normalize_user_id(user_id_raw)
    email = _rpc_email_for_user_id(client, uid)
    if not email:
        return False, "User ID not found."

    try:
        client.auth.reset_password_for_email(
            email, {"redirect_to": _redirect_url()}
        )
    except Exception as ex:
        return False, _auth_error_message(ex) or "Could not send reset email."

    return True, "If that User ID exists, a reset link was sent to the registered email."


def reset_password_by_email(email_raw: str) -> tuple[bool, str]:
    err = validate_email(email_raw)
    if err:
        return False, err
    client = get_client()
    if client is None:
        return False, "Password reset is not configured."
    email = (email_raw or "").strip().lower()
    try:
        client.auth.reset_password_for_email(
            email, {"redirect_to": _redirect_url()}
        )
    except Exception as ex:
        return False, _auth_error_message(ex) or "Could not send reset email."
    return True, "If that email is registered, a reset link was sent."


def request_password_reset_for_current_user() -> tuple[bool, str]:
    email = current_email()
    if not email:
        return False, "Not signed in."
    return reset_password_by_email(email)


def _auth_error_message(ex: Exception) -> str:
    msg = str(ex)
    if hasattr(ex, "message"):
        msg = str(getattr(ex, "message", msg))
    if "already registered" in msg.lower() or "already been registered" in msg.lower():
        return "This email is already registered."
    if "invalid login" in msg.lower() or "invalid credentials" in msg.lower():
        return "User ID or password is incorrect."
    return msg[:200] if msg else ""


def _require_client() -> Client | None:
    """Supabase client for portfolio CRUD; always re-binds JWT so RLS sees auth.uid()."""
    _restore_from_backup()
    if not has_auth_tokens():
        return None
    client = get_client()
    if client is None:
        st.session_state.fl_family_last_error = "Supabase is not configured (check .streamlit/secrets.toml)."
        return None
    _sync_supabase_auth(client)
    if not st.session_state.get("fl_auth_uid") or not st.session_state.get("fl_auth_user_id"):
        _recover_profile_from_supabase(client)
    if not is_logged_in():
        st.session_state.fl_family_last_error = "Sign-in session is incomplete. Try logging out and back in."
        return None
    st.session_state.pop("fl_family_last_error", None)
    return client


_DEFAULT_FAMILY_MEMBER_NAME = "Me"
_MAX_FAMILY_MEMBERS = 20


def _format_saved_at(saved_at: str) -> str:
    ts = pd.to_datetime(saved_at)
    try:
        return ts.strftime("%-d %b %Y, %-I:%M %p")
    except ValueError:
        return ts.strftime("%d %b %Y, %I:%M %p")


def _family_api_error_message(ex: Exception) -> str:
    msg = str(ex).lower()
    if _is_jwt_expired_error(ex):
        return "Your sign-in session expired. Click Retry below or log out and sign in again."
    if "row-level security" in msg or "42501" in msg:
        return (
            "Database blocked family accounts. Run supabase/fix_family_members_rls.sql "
            "in Supabase SQL Editor, then log out and back in."
        )
    if "family_members" in msg and ("does not exist" in msg or "pgrst205" in msg):
        return (
            "Family accounts table is missing. Run supabase/migrate_family_members_f1.sql "
            "in Supabase SQL Editor."
        )
    return f"Could not load family accounts: {str(ex)[:160]}"


def _list_family_members_raw(client: Client, owner_uid: str | None = None) -> list[dict[str, Any]]:
    """List caller's family members (RLS-scoped; no extra owner filter)."""
    st.session_state.fl_family_list_ok = False
    for attempt in range(2):
        try:
            res = (
                client.table("family_members")
                .select("id, account_name, sort_order, created_at")
                .order("sort_order")
                .order("created_at")
                .execute()
            )
            st.session_state.fl_family_list_ok = True
            st.session_state.pop("fl_family_last_error", None)
            return list(res.data or [])
        except Exception as ex:
            if attempt == 0 and _is_jwt_expired_error(ex) and _refresh_supabase_session(client):
                continue
            st.session_state.fl_family_last_error = _family_api_error_message(ex)
            return []
    return []


def _create_family_member_raw(
    client: Client, owner_uid: str, account_name: str, sort_order: int = 0
) -> str | None:
    uid = _effective_auth_uid(client) or owner_uid
    try:
        res = (
            client.table("family_members")
            .insert(
                {
                    "owner_user_id": uid,
                    "account_name": account_name.strip(),
                    "sort_order": sort_order,
                }
            )
            .execute()
        )
        if res.data:
            st.session_state.pop("fl_family_last_error", None)
            _invalidate_family_cache()
            return str(res.data[0]["id"])
    except Exception as ex:
        msg = str(ex).lower()
        if "row-level security" in msg or "42501" in msg:
            st.session_state.fl_family_last_error = (
                "Could not create account — database permissions. Run "
                "supabase/fix_family_members_rls.sql in Supabase SQL Editor, then log out and back in."
            )
        else:
            st.session_state.fl_family_last_error = (
                f"Could not create family account: {str(ex)[:160]}"
            )
    return None


def _migrate_legacy_portfolio(client: Client, owner_uid: str, member_id: str) -> None:
    """Attach pre-F1 portfolio row (family_member_id null) to the given member."""
    try:
        legacy = (
            client.table("portfolios")
            .select("id")
            .eq("user_id", owner_uid)
            .is_("family_member_id", "null")
            .limit(1)
            .execute()
        )
        if legacy.data:
            client.table("portfolios").update({"family_member_id": member_id}).eq(
                "id", legacy.data[0]["id"]
            ).execute()
    except Exception:
        pass


def _invalidate_family_cache() -> None:
    for key in (
        "fl_family_members_list",
        "fl_portfolios_index",
        "fl_family_setup_done",
        "fl_members_with_portfolio",
    ):
        st.session_state.pop(key, None)


def _invalidate_portfolio_cache() -> None:
    st.session_state.pop("fl_portfolios_index", None)
    st.session_state.pop("fl_members_with_portfolio", None)


def _get_portfolios_index(client: Client) -> dict[str, dict[str, Any]]:
    """One Supabase round-trip: all portfolios for the logged-in user (RLS-scoped)."""
    cached = st.session_state.get("fl_portfolios_index")
    if isinstance(cached, dict):
        return cached
    index: dict[str, dict[str, Any]] = {}
    for attempt in range(2):
        try:
            res = (
                client.table("portfolios")
                .select("id, saved_at, records, columns, family_member_id, user_id")
                .execute()
            )
            for row in res.data or []:
                fid = row.get("family_member_id")
                if fid:
                    index[str(fid)] = row
                elif "__legacy__" not in index:
                    index["__legacy__"] = row
            st.session_state.fl_portfolios_index = index
            return index
        except Exception as ex:
            if attempt == 0 and _is_jwt_expired_error(ex) and _refresh_supabase_session(client):
                continue
            break
    st.session_state.fl_portfolios_index = index
    return index


def member_ids_with_portfolio() -> set[str]:
    """Family member IDs that have at least one saved fund (uses cached portfolio index)."""
    cached = st.session_state.get("fl_members_with_portfolio")
    if isinstance(cached, set):
        return cached
    client = _require_client()
    if client is None:
        return set()
    ids: set[str] = set()
    for mid, row in _get_portfolios_index(client).items():
        if mid == "__legacy__":
            continue
        records = row.get("records") or []
        if records:
            ids.add(mid)
    st.session_state.fl_members_with_portfolio = ids
    return ids


def preload_portfolio_cache() -> None:
    """Warm session caches for Manage portfolio (call once per page render)."""
    client = _require_client()
    if client is None:
        return
    _get_portfolios_index(client)
    member_ids_with_portfolio()


def _default_member_id_from_list(members: list[dict[str, Any]]) -> str | None:
    if not members:
        return None
    for m in members:
        if str(m.get("account_name", "")).lower() == _DEFAULT_FAMILY_MEMBER_NAME.lower():
            return str(m["id"])
    return str(members[0]["id"])


def _fetch_portfolio_row(
    client: Client, owner_uid: str, member_id: str, *, migrate_legacy: bool = True
) -> dict[str, Any] | None:
    """Load portfolio row for a family member (cached index first, then legacy migrate)."""
    mid = str(member_id)
    row = _get_portfolios_index(client).get(mid)
    if row:
        return row

    if not migrate_legacy or not owner_uid:
        return None

    members = st.session_state.get("fl_family_members_list")
    if not members:
        members = _list_family_members_raw(client, owner_uid)
    default_id = _default_member_id_from_list(members or [])
    if not default_id or mid != str(default_id):
        return None

    legacy = _get_portfolios_index(client).get("__legacy__")
    if legacy:
        _migrate_legacy_portfolio(client, owner_uid, mid)
        _invalidate_portfolio_cache()
        return _get_portfolios_index(client).get(mid) or legacy
    return None


def ensure_family_setup() -> None:
    """Migrate legacy portfolio; create default 'Me' only when user has zero accounts."""
    if st.session_state.get("fl_family_setup_done"):
        return
    client = _require_client()
    if client is None:
        return
    uid = _effective_auth_uid(client) or st.session_state.fl_auth_uid
    if uid:
        st.session_state.fl_auth_uid = uid
    members = _list_family_members_raw(client, uid)
    list_ok = st.session_state.get("fl_family_list_ok", False)
    if list_ok and not members:
        me_id = _create_family_member_raw(client, uid or "", _DEFAULT_FAMILY_MEMBER_NAME, 0)
        if me_id:
            members = _list_family_members_raw(client, uid)
            _invalidate_family_cache()
    st.session_state.fl_family_members_list = members
    if members:
        default_id = _default_member_id_from_list(members)
        if default_id:
            _migrate_legacy_portfolio(client, uid, default_id)
            _invalidate_portfolio_cache()
        if not st.session_state.get("fl_active_family_member_id"):
            st.session_state.fl_active_family_member_id = default_id
    st.session_state.fl_family_setup_done = True


def list_family_members(*, force_reload: bool = False) -> list[dict[str, Any]]:
    if force_reload:
        _invalidate_family_cache()
    cached = st.session_state.get("fl_family_members_list")
    if isinstance(cached, list) and not force_reload:
        return cached
    client = _require_client()
    if client is None:
        return []
    ensure_family_setup()
    return list(st.session_state.get("fl_family_members_list") or [])


def get_default_family_member_id() -> str | None:
    ensure_family_setup()
    members = list_family_members()
    if not members:
        return None
    for m in members:
        if str(m.get("account_name", "")).lower() == _DEFAULT_FAMILY_MEMBER_NAME.lower():
            return str(m["id"])
    return str(members[0]["id"])


def get_active_family_member_id() -> str | None:
    """Primary member for single-account edit; first selected on Manage page."""
    ensure_family_setup()
    selected = get_selected_family_member_ids()
    if len(selected) == 1:
        return selected[0]
    mid = st.session_state.get("fl_active_family_member_id")
    if mid:
        return str(mid)
    return get_default_family_member_id()


def get_selected_family_member_ids() -> list[str]:
    """Manage-page account selection (one, many, or all)."""
    ensure_family_setup()
    members = list_family_members()
    all_ids = [str(m["id"]) for m in members]
    if not all_ids:
        return []
    raw = st.session_state.get("fl_selected_family_member_ids")
    if isinstance(raw, list) and raw:
        valid = [str(mid) for mid in raw if str(mid) in all_ids]
        if valid:
            return valid
    with_pf = member_ids_with_portfolio()
    if with_pf:
        return [mid for mid in all_ids if mid in with_pf]
    default = get_default_family_member_id()
    return [default] if default else [all_ids[0]]


def set_selected_family_member_ids(member_ids: list[str]) -> None:
    """Persist Manage-page selection and sync active member for edit/save."""
    members = list_family_members()
    all_ids = {str(m["id"]) for m in members}
    valid = [str(mid) for mid in (member_ids or []) if str(mid) in all_ids]
    if not valid and members:
        valid = [str(members[0]["id"])]
    st.session_state.fl_selected_family_member_ids = valid
    if valid:
        st.session_state.fl_active_family_member_id = valid[0]


def selected_member_labels() -> list[str]:
    return [family_member_name(mid) for mid in get_selected_family_member_ids()]


def family_member_name(member_id: str | None = None) -> str:
    mid = member_id or get_active_family_member_id() or get_default_family_member_id()
    if not mid:
        return _DEFAULT_FAMILY_MEMBER_NAME
    for m in list_family_members():
        if str(m.get("id")) == str(mid):
            return str(m.get("account_name", _DEFAULT_FAMILY_MEMBER_NAME))
    return _DEFAULT_FAMILY_MEMBER_NAME


def _validate_family_member_name(name: str, *, exclude_member_id: str | None = None) -> str | None:
    """Return error message, or None if valid."""
    label = (name or "").strip()
    if len(label) < 1:
        return "Enter a name for this family member."
    if len(label) > 40:
        return "Name must be 40 characters or fewer."
    client = _require_client()
    if client is None:
        return "Sign in to manage family members."
    uid = st.session_state.fl_auth_uid
    for m in _list_family_members_raw(client, uid):
        if exclude_member_id and str(m.get("id")) == str(exclude_member_id):
            continue
        if str(m.get("account_name", "")).lower() == label.lower():
            return "A family member with this name already exists."
    return None


def create_family_member(account_name: str) -> tuple[bool, str]:
    name = (account_name or "").strip()
    err = _validate_family_member_name(name)
    if err:
        return False, err
    client = _require_client()
    if client is None:
        return False, "Sign in to add family members."
    ensure_family_setup()
    uid = st.session_state.fl_auth_uid
    existing = _list_family_members_raw(client, uid)
    if len(existing) >= _MAX_FAMILY_MEMBERS:
        return False, f"You can add up to {_MAX_FAMILY_MEMBERS} family members."
    new_id = _create_family_member_raw(client, uid, name, len(existing))
    if not new_id:
        return False, "Could not add family member. Run supabase/migrate_family_members_f1.sql if this is a new install."
    st.session_state.fl_active_family_member_id = new_id
    st.session_state.fl_selected_family_member_ids = [new_id]
    st.session_state.pop("fl_manage_member_multiselect", None)
    st.session_state.portfolio_page_mode = "entry"
    st.session_state.pop("_portfolio_edit_type", None)
    return True, ""


def rename_family_member(member_id: str, account_name: str) -> tuple[bool, str]:
    mid = str(member_id or "").strip()
    name = (account_name or "").strip()
    if not mid:
        return False, "No family member selected."
    err = _validate_family_member_name(name, exclude_member_id=mid)
    if err:
        return False, err
    client = _require_client()
    if client is None:
        return False, "Sign in to rename family members."
    uid = st.session_state.fl_auth_uid
    try:
        res = (
            client.table("family_members")
            .update({"account_name": name})
            .eq("id", mid)
            .eq("owner_user_id", uid)
            .execute()
        )
        if not res.data:
            return False, "Family member not found."
        _invalidate_family_cache()
        return True, ""
    except Exception:
        return False, "Could not rename family member."


def delete_family_member(member_id: str) -> tuple[bool, str]:
    mid = str(member_id or "").strip()
    if not mid:
        return False, "No family member selected."
    client = _require_client()
    if client is None:
        return False, "Sign in to remove family members."
    uid = st.session_state.fl_auth_uid
    existing = _list_family_members_raw(client, uid)
    if len(existing) <= 1:
        return False, "You must keep at least one family member."
    if not any(str(m.get("id")) == mid for m in existing):
        return False, "Family member not found."
    try:
        client.table("family_members").delete().eq("id", mid).eq("owner_user_id", uid).execute()
    except Exception:
        return False, "Could not remove family member."
    _invalidate_family_cache()
    remaining = [m for m in existing if str(m.get("id")) != mid]
    sel = [str(x) for x in (st.session_state.get("fl_selected_family_member_ids") or [])]
    sel = [x for x in sel if x != mid]
    if not sel and remaining:
        sel = [str(remaining[0]["id"])]
    st.session_state.fl_selected_family_member_ids = sel
    if str(st.session_state.get("fl_active_family_member_id", "")) == mid:
        st.session_state.fl_active_family_member_id = str(remaining[0]["id"])
        st.session_state.pop("portfolio_df", None)
        _has = portfolio_meta(str(remaining[0]["id"])) is not None
        st.session_state.portfolio_page_mode = "view" if _has else "entry"
    st.session_state.pop("fl_manage_member_multiselect", None)
    return True, ""


def _resolve_member_id(family_member_id: str | None) -> str | None:
    if family_member_id:
        return str(family_member_id)
    return get_default_family_member_id()


def save_portfolio(df: pd.DataFrame, family_member_id: str | None = None) -> bool:
    client = _require_client()
    if client is None:
        return False
    mid = _resolve_member_id(family_member_id)
    if not mid:
        return False
    uid = _effective_auth_uid(client) or st.session_state.fl_auth_uid
    payload = {
        "user_id": uid,
        "family_member_id": mid,
        "saved_at": pd.Timestamp.now().isoformat(timespec="seconds"),
        "records": df.to_dict(orient="records"),
        "columns": list(df.columns),
    }
    try:
        existing = _fetch_portfolio_row(client, uid, mid, migrate_legacy=False)
        if existing:
            client.table("portfolios").update(
                {
                    "saved_at": payload["saved_at"],
                    "records": payload["records"],
                    "columns": payload["columns"],
                }
            ).eq("id", existing["id"]).execute()
        else:
            client.table("portfolios").insert(payload).execute()
        _invalidate_portfolio_cache()
        return True
    except Exception:
        return False


def load_portfolio(family_member_id: str | None = None) -> pd.DataFrame | None:
    client = _require_client()
    if client is None:
        return None
    mid = _resolve_member_id(family_member_id)
    if not mid:
        return None
    try:
        row = _get_portfolios_index(client).get(str(mid))
        if not row:
            uid = _effective_auth_uid(client) or st.session_state.fl_auth_uid
            row = _fetch_portfolio_row(client, uid or "", mid)
        if not row:
            return None
        records = row.get("records") or []
        if not records:
            return None
        return pd.DataFrame(records, columns=row.get("columns") or None)
    except Exception:
        return None


def portfolio_meta(family_member_id: str | None = None) -> tuple[int, str] | None:
    client = _require_client()
    if client is None:
        return None
    mid = _resolve_member_id(family_member_id)
    if not mid:
        return None
    try:
        row = _get_portfolios_index(client).get(str(mid))
        if not row:
            uid = _effective_auth_uid(client) or st.session_state.fl_auth_uid
            row = _fetch_portfolio_row(client, uid or "", mid)
        if not row:
            return None
        records = row.get("records") or []
        n = len(records)
        if not n:
            return None
        return n, _format_saved_at(str(row.get("saved_at", "")))
    except Exception:
        return None


def portfolio_fund_names(family_member_id: str | None = None) -> list:
    client = _require_client()
    mid = _resolve_member_id(family_member_id)
    if client is None or not mid:
        return []
    row = _fetch_portfolio_row(
        client,
        _effective_auth_uid(client) or st.session_state.fl_auth_uid or "",
        mid,
        migrate_legacy=False,
    )
    if not row:
        return []
    records = row.get("records") or []
    if not records:
        return []
    cols = row.get("columns") or []
    fund_col = next((c for c in cols if "fund" in str(c).lower()), "fund_name")
    names: list = []
    for rec in records:
        if isinstance(rec, dict) and rec.get(fund_col):
            names.append(rec[fund_col])
    return names
