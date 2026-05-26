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

_PORTFOLIO_GATED_PAGES = frozenset({"portfolio_upload", "portfolio_xray"})

_VALID_RETURN_PAGES = frozenset({
    "home",
    "analyse_funds",
    "category",
    "explorer",
    "compare",
    "stock_explorer",
    "overlap_drilldown",
    "portfolio_upload",
    "portfolio_xray",
    "account",
})

_AUTH_DISK_DIR = Path(__file__).resolve().parent / ".streamlit" / "auth_sessions"
_BIND_THROTTLE_SEC = 90

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
    for key in list(st.session_state.keys()):
        if key in ("manual_fund_select", "portfolio_entry_mode") or key.startswith(
            ("m_amt_", "m_units_")
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


def _try_bind_supabase_client(client: Client, access: str, refresh: str) -> None:
    """Best-effort Supabase bind; never clears Streamlit auth session on failure."""
    try:
        res = client.auth.set_session(access, refresh)
        if res.session:
            _persist_tokens_from_session(res.session)
            return
    except Exception:
        pass
    try:
        res = client.auth.refresh_session(refresh)
        if res.session:
            _persist_tokens_from_session(res.session)
            try:
                client.auth.set_session(
                    res.session.access_token, res.session.refresh_token
                )
            except Exception:
                pass
    except Exception:
        pass


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
            _try_bind_supabase_client(client, access, refresh)
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
    """Supabase client for portfolio CRUD; relies on main() init_auth for JWT bind."""
    _restore_from_backup()
    if not has_auth_tokens():
        return None
    client = get_client()
    if client is None:
        return None
    if not st.session_state.get("fl_auth_uid") or not st.session_state.get("fl_auth_user_id"):
        _recover_profile_from_supabase(client)
    if not is_logged_in():
        return None
    return client


def save_portfolio(df: pd.DataFrame) -> bool:
    client = _require_client()
    if client is None:
        return False
    uid = st.session_state.fl_auth_uid
    payload = {
        "user_id": uid,
        "saved_at": pd.Timestamp.now().isoformat(timespec="seconds"),
        "records": df.to_dict(orient="records"),
        "columns": list(df.columns),
    }
    try:
        existing = (
            client.table("portfolios")
            .select("id")
            .eq("user_id", uid)
            .limit(1)
            .execute()
        )
        if existing.data:
            client.table("portfolios").update(
                {
                    "saved_at": payload["saved_at"],
                    "records": payload["records"],
                    "columns": payload["columns"],
                }
            ).eq("user_id", uid).execute()
        else:
            client.table("portfolios").insert(payload).execute()
        return True
    except Exception:
        return False


def load_portfolio() -> pd.DataFrame | None:
    client = _require_client()
    if client is None:
        return None
    try:
        res = (
            client.table("portfolios")
            .select("records, columns")
            .eq("user_id", st.session_state.fl_auth_uid)
            .limit(1)
            .execute()
        )
        if not res.data:
            return None
        row = res.data[0]
        records = row.get("records") or []
        if not records:
            return None
        return pd.DataFrame(records, columns=row.get("columns") or None)
    except Exception:
        return None


def portfolio_meta() -> tuple[int, str] | None:
    client = _require_client()
    if client is None:
        return None
    try:
        res = (
            client.table("portfolios")
            .select("saved_at, records")
            .eq("user_id", st.session_state.fl_auth_uid)
            .limit(1)
            .execute()
        )
        if not res.data:
            return None
        row = res.data[0]
        records = row.get("records") or []
        n = len(records)
        saved_at = row.get("saved_at", "")
        ts = pd.to_datetime(saved_at)
        try:
            human = ts.strftime("%-d %b %Y, %-I:%M %p")
        except ValueError:
            human = ts.strftime("%d %b %Y, %I:%M %p")
        return n, human
    except Exception:
        return None


def portfolio_fund_names() -> list:
    df = load_portfolio()
    if df is None or df.empty:
        return []
    fund_col = next((c for c in df.columns if "fund" in c.lower()), None)
    return df[fund_col].dropna().tolist() if fund_col else []
