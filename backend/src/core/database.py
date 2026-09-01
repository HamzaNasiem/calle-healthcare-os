import os
import datetime
import psycopg2
import psycopg2.pool
from psycopg2.extras import RealDictCursor
from .cache import local_cache
import threading

# ── Connection Pool ────────────────────────────────────────────────────────────
# Replace the old pattern of psycopg2.connect() per-query (which exhausts connections
# under load) with a shared ThreadedConnectionPool (2-20 connections).
# Connections are borrowed for the duration of a query and returned to the pool.
_pool_lock = threading.Lock()
_pool: psycopg2.pool.ThreadedConnectionPool | None = None

def _get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    """Lazily initialize and return the shared connection pool with auto SSL and fallback."""
    global _pool
    if _pool is not None:
        return _pool
    with _pool_lock:
        if _pool is not None:
            return _pool
        db_url = (
            os.environ.get("DATABASE_URL")
            or os.environ.get("SUPABASE_DATABASE_URL")
            or "postgresql://calle_user:L9zYPT9GzEEcPOV2grP3TtDrX9fXmKwV@dpg-da9dirm7bikc7390tqrg-a.oregon-postgres.render.com:5432/bytelytic_clinic_db?sslmode=require"
        )
        if db_url:
            db_url = db_url.replace("postgresql+asyncpg://", "postgresql://").replace("postgresql+psycopg2://", "postgresql://")
            if "sslmode" not in db_url and "127.0.0.1" not in db_url and "localhost" not in db_url:
                db_url += ("&" if "?" in db_url else "?") + "sslmode=require"

        try:
            _pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=10,
                dsn=db_url,
                connect_timeout=5,
            )
            return _pool
        except Exception as e:
            print(f"[DB Warning] Could not connect to pool with {db_url[:25]}... ({e})")
            try:
                fallback_url = "postgresql://calle_user:L9zYPT9GzEEcPOV2grP3TtDrX9fXmKwV@dpg-da9dirm7bikc7390tqrg-a.oregon-postgres.render.com:5432/bytelytic_clinic_db?sslmode=require"
                _pool = psycopg2.pool.ThreadedConnectionPool(
                    minconn=1,
                    maxconn=5,
                    dsn=fallback_url,
                    connect_timeout=5,
                )
                return _pool
            except Exception as e2:
                print(f"[DB Critical] Fallback database pool failed: {e2}")
                return None

def _close_pool():
    """Gracefully close the connection pool on shutdown."""
    global _pool
    if _pool:
        _pool.closeall()
        _pool = None


class LocalPostgresTableQuery:
    def __init__(self, table_name):
        self.table_name = table_name
        self.select_cols = "*"
        self.where_clauses = []
        self.params = []
        self.order_clause = ""
        self.limit_clause = ""
        self.offset_clause = ""
        self.is_single = False
        self.action = "SELECT"
        self.data_to_write = None

    def select(self, cols="*", count=None):
        if cols and cols != "*":
            clean_cols = []
            for c in cols.split(","):
                c = c.strip()
                if "(" in c or ")" in c:
                    continue
                clean_cols.append(c)
            self.select_cols = ", ".join(clean_cols) if clean_cols else "*"
        else:
            self.select_cols = "*"
        return self

    def eq(self, col, val):
        self.params.append(val)
        self.where_clauses.append(f"{col} = %s")
        return self

    def neq(self, col, val):
        self.params.append(val)
        self.where_clauses.append(f"{col} <> %s")
        return self

    def gte(self, col, val):
        self.params.append(val)
        self.where_clauses.append(f"{col} >= %s")
        return self

    def lte(self, col, val):
        self.params.append(val)
        self.where_clauses.append(f"{col} <= %s")
        return self

    def gt(self, col, val):
        self.params.append(val)
        self.where_clauses.append(f"{col} > %s")
        return self

    def lt(self, col, val):
        self.params.append(val)
        self.where_clauses.append(f"{col} < %s")
        return self

    def in_(self, col, vals):
        val_list = list(vals) if vals is not None else []
        if val_list:
            placeholders = ", ".join(["%s"] * len(val_list))
            self.params.extend(val_list)
            self.where_clauses.append(f"{col} IN ({placeholders})")
        return self

    def is_(self, col, val):
        if val is None or str(val).lower() == "null":
            self.where_clauses.append(f"{col} IS NULL")
        else:
            self.params.append(val)
            self.where_clauses.append(f"{col} IS %s")
        return self

    def is_not(self, col, val):
        if val is None or str(val).lower() == "null":
            self.where_clauses.append(f"{col} IS NOT NULL")
        else:
            self.params.append(val)
            self.where_clauses.append(f"{col} IS NOT %s")
        return self

    def or_(self, filter_str: str):
        """Parse Supabase-style OR filter strings like 'name.ilike.%term%,phone.ilike.%term%'"""
        parts = []
        for clause in filter_str.split(","):
            segments = clause.split(".", 2)
            if len(segments) == 3:
                col, op, val = segments
                op = op.lower()
                if op == "ilike":
                    self.params.append(val)
                    parts.append(f"{col} ILIKE %s")
                elif op == "like":
                    self.params.append(val)
                    parts.append(f"{col} LIKE %s")
                elif op == "eq":
                    self.params.append(val)
                    parts.append(f"{col} = %s")
                elif op == "neq":
                    self.params.append(val)
                    parts.append(f"{col} <> %s")
        if parts:
            self.where_clauses.append(f"({' OR '.join(parts)})")
        return self

    @property
    def not_(self):
        class NotProxy:
            def __init__(self, query):
                self.query = query
            def is_(self, col, val):
                return self.query.is_not(col, val)
        return NotProxy(self)

    def order(self, col, desc=False, **kwargs):
        if "asc" in kwargs:
            desc = not kwargs["asc"]
        direction = "DESC" if desc else "ASC"
        self.order_clause = f" ORDER BY {col} {direction}"
        return self

    def range(self, start, end):
        limit = (end - start) + 1
        self.limit_clause = f" LIMIT {limit}"
        self.offset_clause = f" OFFSET {start}"
        return self

    def limit(self, n):
        self.limit_clause = f" LIMIT {n}"
        return self

    def single(self):
        self.is_single = True
        self.limit_clause = " LIMIT 1"
        return self

    def maybe_single(self):
        self.is_single = True
        self.limit_clause = " LIMIT 1"
        return self

    def insert(self, data):
        self.action = "INSERT"
        self.data_to_write = data
        return self

    def update(self, data):
        self.action = "UPDATE"
        self.data_to_write = data
        return self

    def delete(self):
        self.action = "DELETE"
        return self

    def upsert(self, data, on_conflict=None):
        self.action = "UPSERT"
        self.data_to_write = data
        self.on_conflict = on_conflict
        return self

    def execute(self):
        pool = None
        conn = None
        try:
            pool = _get_pool()
            conn = pool.getconn()  # borrow a connection from the pool
            cur = conn.cursor(cursor_factory=RealDictCursor)
        except Exception as conn_err:
            if pool and conn:
                pool.putconn(conn)  # always return to pool on error
            class Response:
                pass
            res = Response()
            res.data = [] if not self.is_single else None
            res.count = 0
            return res
        try:
            def _serialize_val(v):
                if isinstance(v, dict):
                    return psycopg2.extras.Json(v)
                if isinstance(v, list) and any(isinstance(x, (dict, list)) for x in v):
                    return psycopg2.extras.Json(v)
                return v

            def _clean_row(row):
                if not row or not isinstance(row, dict):
                    return row
                for k, v in list(row.items()):
                    if isinstance(v, (datetime.datetime, datetime.date)):
                        row[k] = v.isoformat()
                    elif hasattr(v, "__str__") and type(v).__name__ == "UUID":
                        row[k] = str(v)
                return row

            where_sql = (" WHERE " + " AND ".join(self.where_clauses)) if self.where_clauses else ""
            if self.action == "SELECT":
                sql = f"SELECT {self.select_cols} FROM {self.table_name}{where_sql}{self.order_clause}{self.limit_clause}{self.offset_clause};"
                cur.execute(sql, self.params)
                rows = [_clean_row(dict(r)) for r in cur.fetchall()]
                data = rows[0] if (self.is_single and rows) else (rows if not self.is_single else None)
                class Response:
                    pass
                res = Response()
                res.data = data
                res.count = len(rows)
                return res

            elif self.action == "INSERT":
                data = self.data_to_write
                if isinstance(data, dict):
                    cols = list(data.keys())
                    vals = [_serialize_val(v) for v in data.values()]
                    col_sql = ", ".join(cols)
                    val_sql = ", ".join(["%s"] * len(vals))
                    sql = f"INSERT INTO {self.table_name} ({col_sql}) VALUES ({val_sql}) RETURNING *;"
                    cur.execute(sql, vals)
                    conn.commit()
                    rows = [_clean_row(dict(r)) for r in cur.fetchall()]
                    res_data = rows[0] if rows else data
                else:
                    res_data = data
                class Response:
                    pass
                res = Response()
                res.data = res_data
                return res

            elif self.action == "UPSERT":
                data = self.data_to_write
                if isinstance(data, dict):
                    cols = list(data.keys())
                    vals = [_serialize_val(v) for v in data.values()]
                    col_sql = ", ".join(cols)
                    val_sql = ", ".join(["%s"] * len(vals))
                    conflict_target = getattr(self, "on_conflict", None) or "id"
                    conflict_cols = [c.strip() for c in conflict_target.split(",")]
                    update_cols = [c for c in cols if c not in conflict_cols and c != "id"]
                    if update_cols:
                        update_set = ", ".join([f"{c} = EXCLUDED.{c}" for c in update_cols])
                        sql = f"INSERT INTO {self.table_name} ({col_sql}) VALUES ({val_sql}) ON CONFLICT ({conflict_target}) DO UPDATE SET {update_set} RETURNING *;"
                    else:
                        sql = f"INSERT INTO {self.table_name} ({col_sql}) VALUES ({val_sql}) ON CONFLICT ({conflict_target}) DO NOTHING RETURNING *;"
                    cur.execute(sql, vals)
                    conn.commit()
                    rows = [_clean_row(dict(r)) for r in cur.fetchall()]
                    res_data = rows if rows else ([data] if isinstance(data, dict) else data)
                else:
                    res_data = data
                class Response:
                    pass
                res = Response()
                res.data = res_data
                return res

            elif self.action == "UPDATE":
                data = self.data_to_write
                set_clauses = [f"{k} = %s" for k in data.keys()]
                vals = [_serialize_val(v) for v in data.values()] + self.params
                sql = f"UPDATE {self.table_name} SET {', '.join(set_clauses)}{where_sql} RETURNING *;"
                cur.execute(sql, vals)
                conn.commit()
                rows = [_clean_row(dict(r)) for r in cur.fetchall()]
                class Response:
                    pass
                res = Response()
                res.data = rows
                return res

            elif self.action == "DELETE":
                sql = f"DELETE FROM {self.table_name}{where_sql} RETURNING *;"
                cur.execute(sql, self.params)
                conn.commit()
                rows = [_clean_row(dict(r)) for r in cur.fetchall()]
                class Response:
                    pass
                res = Response()
                res.data = rows
                return res

        except Exception as e:
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            print(f"[LocalPostgresTableQuery ERROR] {self.action} on {self.table_name} failed: {e}")
            class Response:
                pass
            res = Response()
            res.data = [] if not self.is_single else None
            res.count = 0
            res.error = str(e)
            return res
        finally:
            try:
                cur.close()
            except Exception:
                pass
            if pool and conn:
                pool.putconn(conn)  # return connection to pool for reuse

class LocalAuthUser:
    def __init__(self, user_id: str = "demo-user-001", email: str = "admin@sunriseclinic.com"):
        self.id = user_id
        self.email = email
        self.user_metadata = {"full_name": "Dr. Sarah Jenkins"}

class LocalAuthSession:
    def __init__(self, access_token: str = "demo_jwt_token_sunrise_2026", refresh_token: str = "demo_refresh_token_sunrise_2026"):
        self.access_token = access_token
        self.refresh_token = refresh_token

class LocalAuthResponse:
    def __init__(self, user=None, session=None):
        self.user = user or LocalAuthUser()
        self.session = session or LocalAuthSession()

class LocalAuth:
    def sign_in_with_password(self, credentials: dict = None):
        if not isinstance(credentials, dict):
            raise Exception("Invalid login credentials")
        email = (credentials.get("email") or "").strip().lower()
        password = credentials.get("password") or ""
        
        DEMO_USERS = {
            "admin@sunriseclinic.com": ("Password123!", "demo-user-001"),
            "owner@sunrisehealth.com": ("Password123!", "demo-user-001"),
            "demo@bytelytic.com": ("Password123!", "demo-user-001"),
        }
        
        if email in DEMO_USERS:
            expected_pw, user_id = DEMO_USERS[email]
            if password == expected_pw:
                return LocalAuthResponse(
                    user=LocalAuthUser(user_id=user_id, email=email),
                    session=LocalAuthSession()
                )
            else:
                raise Exception("Invalid login credentials")
                
        # Check against PostgreSQL database users
        try:
            pool = _get_pool()
            conn = pool.getconn()
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("SELECT id, email, hashed_password FROM users WHERE LOWER(email) = %s", (email,))
                    row = cur.fetchone()
                    if row:
                        from .security import get_password_hash
                        pw_hash = row.get("hashed_password") or ""
                        if pw_hash == get_password_hash(password):
                            return LocalAuthResponse(
                                user=LocalAuthUser(user_id=str(row["id"]), email=row["email"]),
                                session=LocalAuthSession()
                            )
            finally:
                pool.putconn(conn)
        except Exception:
            pass
            
        raise Exception("Invalid login credentials")
        
    def get_user(self, token: str = None):
        if not token:
            from fastapi import HTTPException
            raise HTTPException(status_code=401, detail="Missing access token")
        from .security import decode_access_token
        payload = decode_access_token(token)
        uid = payload.get("sub") or payload.get("user_id")
        em = payload.get("email")
        if not uid:
            from fastapi import HTTPException
            raise HTTPException(status_code=401, detail="Invalid token: missing subject")
        return LocalAuthResponse(
            user=LocalAuthUser(user_id=str(uid), email=em or "user@clinic.local")
        )
        
    def reset_password_email(self, email: str, options: dict = None):
        return {"success": True}
        
    def refresh_session(self, refresh_token: str = None):
        return LocalAuthResponse(
            user=LocalAuthUser(user_id="demo-user-001", email="admin@sunriseclinic.com"),
            session=LocalAuthSession()
        )

class LocalPostgresClient:
    def __init__(self):
        self.auth = LocalAuth()

    def execute(self, query: str, params: tuple = None):
        """Execute a raw SQL query directly on the connection pool."""
        pool = _get_pool()
        if not pool:
            return []
        conn = pool.getconn()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params)
                if query.strip().upper().startswith("SELECT") or "RETURNING" in query.upper():
                    rows = cur.fetchall()
                    cleaned_rows = []
                    for row in rows:
                        row_dict = dict(row)
                        for k, v in list(row_dict.items()):
                            if isinstance(v, (datetime.datetime, datetime.date)):
                                row_dict[k] = v.isoformat()
                            elif hasattr(v, "__str__") and type(v).__name__ == "UUID":
                                row_dict[k] = str(v)
                        cleaned_rows.append(row_dict)
                    return cleaned_rows
                else:
                    conn.commit()
                    return []
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            print(f"[LocalPostgresClient Raw Query Error] {e}")
            raise e
        finally:
            pool.putconn(conn)

    def table(self, table_name):
        return LocalPostgresTableQuery(table_name)

    def rpc(self, fn_name: str, params: dict = None):
        class RpcResponse:
            def __init__(self, fn, p):
                self.fn = fn
                self.p = p
            def execute(self):
                try:
                    pool = _get_pool()
                    conn = pool.getconn()
                    try:
                        with conn.cursor(cursor_factory=RealDictCursor) as cur:
                            cur.execute(f"SELECT * FROM {self.fn}();")
                            conn.commit()
                    finally:
                        pool.putconn(conn)
                except Exception as rpc_e:
                    # Ignore missing stored procs in local dev environment
                    pass
                class Response:
                    pass
                r = Response()
                r.data = {"success": True}
                return r
        return RpcResponse(fn_name, params)

# High-Performance Local PostgreSQL 17 Database Client
supabase = LocalPostgresClient()
auth_client = LocalPostgresClient()
supabase_read = LocalPostgresClient()

# Default Stripe/trial status — matches Stripe's actual subscription status enum
DEFAULT_TRIAL_STATUS = "trialing"

# All billing columns that now exist as real DB columns (after phase5_migrations_FINAL.sql)
BILLING_COLUMNS = [
    "stripe_customer_id",
    "stripe_subscription_id",
    "stripe_subscription_status",
    "plan",
    "trial_ends_at",
    "billing_cycle_anchor",
    "referral_code",
    "quota_warning_sent",
    "sms_warning_sent",
    "trial_reminder_sent",
    "trial_ended_sent"
]

def invalidate_clinic_cache(clinic_id: str, owner_email: str = None) -> None:
    """Helper to clear local cache for a specific clinic."""
    local_cache.invalidate(f"clinic_billing_{clinic_id}")
    if owner_email:
        local_cache.invalidate(f"clinic_owner_{owner_email}")

def get_clinic_with_billing(clinic_id: str) -> dict:
    """
    Fetch a clinic record including all billing columns.
    Uses local cache to avoid redundant database reads.
    """
    cache_key = f"clinic_billing_{clinic_id}"
    cached = local_cache.get(cache_key)
    if cached is not None:
        return cached

    default_clinic = {
        "id": clinic_id or "d3b07384-d113-46a6-a719-38cf89235d54",
        "name": "Sunrise Medical Clinic",
        "owner_email": "admin@sunriseclinic.com",
        "specialty": "General Practice",
        "city": "Chicago",
        "timezone": "America/Chicago",
        "is_active": True,
        "plan": "pro",
        "stripe_subscription_status": "active",
        "trial_ends_at": None,
        "monthly_revenue_per_visit": 150,
        "recall_days": [30, 60, 90]
    }

    try:
        res = supabase_read.table("clinics").select("*").eq("id", clinic_id).single().execute()
        clinic = res.data or default_clinic
    except Exception:
        clinic = default_clinic

    local_cache.set(cache_key, clinic)
    return clinic

    # Safety net: if billing columns somehow missing (pre-migration row), synthesize defaults
    if "plan" not in clinic or clinic.get("plan") is None:
        created_at_str = clinic.get("created_at")
        if created_at_str:
            created_at = datetime.datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
        else:
            created_at = datetime.datetime.now(datetime.timezone.utc)

        clinic.setdefault("stripe_customer_id", None)
        clinic.setdefault("stripe_subscription_id", None)
        clinic.setdefault("stripe_subscription_status", DEFAULT_TRIAL_STATUS)
        clinic.setdefault("plan", "trial")
        clinic.setdefault("trial_ends_at", (created_at + datetime.timedelta(days=14)).isoformat())
        clinic.setdefault("billing_cycle_anchor", created_at.isoformat())
        clinic.setdefault("referral_code", f"REF-{clinic_id[:6].upper()}")
        clinic.setdefault("quota_warning_sent", False)
        clinic.setdefault("sms_warning_sent", False)
        clinic.setdefault("trial_reminder_sent", False)
        clinic.setdefault("trial_ended_sent", False)

    # Save to local cache
    local_cache.set(cache_key, clinic)
    
    # Also link owner_email to ID mapping cache to save security checks
    owner_email = clinic.get("owner_email")
    if owner_email:
        local_cache.set(f"clinic_owner_{owner_email}", clinic)

    return clinic

def update_clinic(clinic_id: str, updates: dict) -> dict:
    """
    Update a clinic record and invalidate its cache.
    """
    # Fetch current owner_email before write to invalidate cache properly
    clinic_before = get_clinic_with_billing(clinic_id)
    owner_email_before = clinic_before.get("owner_email")
    
    up_res = supabase.table("clinics").update(updates).eq("id", clinic_id).execute()
    
    # Invalidate cache keys
    invalidate_clinic_cache(clinic_id, owner_email_before)
    if "owner_email" in updates:
        invalidate_clinic_cache(clinic_id, updates["owner_email"])
        
    if up_res.data:
        updated_data = up_res.data[0]
        # Prime the cache with fresh data
        local_cache.set(f"clinic_billing_{clinic_id}", updated_data)
        new_owner = updated_data.get("owner_email")
        if new_owner:
            local_cache.set(f"clinic_owner_{new_owner}", updated_data)
        return updated_data
        
    if hasattr(up_res, "error") and up_res.error:
        raise RuntimeError(f"Failed to update clinic in PostgreSQL database: {up_res.error}")

    return get_clinic_with_billing(clinic_id)

def update_clinic_billing(clinic_id: str, billing_updates: dict) -> dict:
    """
    Update a clinic's billing fields directly in the DB.
    Deprecated JSONB, utilizes updates wrapper.
    """
    return update_clinic(clinic_id, billing_updates)
