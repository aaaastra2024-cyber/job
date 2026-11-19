"""所有数据库访问只经过这里。本机默认 SQLite，线上把 DATABASE_URL 换成 Supabase 的 PostgreSQL 地址。

只用两种数据库都支持的基础 SQL；档案和报告整条存成 JSON 文本。
"""
import datetime as dt
import hashlib
import hmac
import json
import os
import secrets
import uuid

from sqlalchemy import create_engine, text

SCHEMA = [
    "CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, pw_hash TEXT NOT NULL, salt TEXT NOT NULL, created_at TEXT)",
    "CREATE TABLE IF NOT EXISTS profiles (username TEXT PRIMARY KEY, data TEXT NOT NULL, updated_at TEXT)",
    "CREATE TABLE IF NOT EXISTS reports (id TEXT PRIMARY KEY, username TEXT NOT NULL, data TEXT NOT NULL, created_at TEXT)",
    "CREATE TABLE IF NOT EXISTS usage (username TEXT, day TEXT, count INTEGER, PRIMARY KEY (username, day))",
    "CREATE TABLE IF NOT EXISTS events (username TEXT, name TEXT, at TEXT)",
]


def _now():
    return dt.datetime.now().isoformat(timespec="seconds")


class Store:
    def __init__(self, url=None):
        url = url or os.environ.get("DATABASE_URL") or "sqlite:///data/app.db"
        # Supabase 给的地址以 postgresql:// 开头；新版 SQLAlchemy 默认找 psycopg 3，这里固定用 requirements 里的 psycopg2
        for prefix in ("postgresql://", "postgres://"):
            if url.startswith(prefix):
                url = "postgresql+psycopg2://" + url[len(prefix):]
        self.engine = create_engine(url, pool_pre_ping=True)
        with self.engine.begin() as c:
            for s in SCHEMA:
                c.execute(text(s))
            if self.engine.dialect.name == "postgresql":
                # Supabase 会把 public 表自动开放给它的网页 API；开启行级安全且不写策略，等于关掉这条路。
                # 本程序以表所有者身份连接，不受影响。
                for t in ("users", "profiles", "reports", "usage", "events"):
                    c.execute(text(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY"))

    def _exec(self, sql, **kw):
        with self.engine.begin() as c:
            return c.execute(text(sql), kw)

    def _rows(self, sql, **kw):
        with self.engine.connect() as c:
            return c.execute(text(sql), kw).fetchall()

    # 账号 ------------------------------------------------------------
    @staticmethod
    def _hash(pw, salt):
        return hashlib.scrypt(pw.encode(), salt=bytes.fromhex(salt), n=2**14, r=8, p=1).hex()

    def register(self, username, pw, invite, valid_invites):
        username, invite = (username or "").strip(), (invite or "").strip()  # 复制粘贴常带空格
        if invite not in valid_invites:
            return "邀请码不正确"
        if not (2 <= len(username) <= 20):
            return "用户名需 2 到 20 个字符"
        if len(pw) < 8:
            return "密码至少 8 位"
        if self._rows("SELECT 1 FROM users WHERE username=:u", u=username):
            return "用户名已被占用"
        salt = secrets.token_hex(16)
        self._exec("INSERT INTO users VALUES (:u, :h, :s, :t)", u=username, h=self._hash(pw, salt), s=salt, t=_now())
        return None

    def login(self, username, pw):
        username = (username or "").strip()
        rows = self._rows("SELECT pw_hash, salt FROM users WHERE username=:u", u=username)
        return bool(rows) and hmac.compare_digest(rows[0][0], self._hash(pw, rows[0][1]))

    def delete_user(self, username):
        for t in ("users", "profiles", "reports", "usage", "events"):
            self._exec(f"DELETE FROM {t} WHERE username=:u", u=username)

    # 档案 ------------------------------------------------------------
    def get_profile(self, username):
        rows = self._rows("SELECT data FROM profiles WHERE username=:u", u=username)
        return json.loads(rows[0][0]) if rows else None

    def save_profile(self, username, profile):
        self._exec("INSERT INTO profiles VALUES (:u, :d, :t) ON CONFLICT (username) DO UPDATE SET data=:d, updated_at=:t",
                   u=username, d=json.dumps(profile, ensure_ascii=False), t=_now())

    # 报告（投递看板的状态也存在报告的 application 字段里）----------------
    def save_report(self, username, report):
        report.setdefault("id", uuid.uuid4().hex)
        report.setdefault("created_at", _now())
        self._exec("INSERT INTO reports VALUES (:i, :u, :d, :t) ON CONFLICT (id) DO UPDATE SET data=:d",
                   i=report["id"], u=username, d=json.dumps(report, ensure_ascii=False), t=report["created_at"])
        return report["id"]

    def list_reports(self, username):
        rows = self._rows("SELECT data FROM reports WHERE username=:u ORDER BY created_at DESC", u=username)
        return [json.loads(r[0]) for r in rows]

    def delete_report(self, username, rid):
        self._exec("DELETE FROM reports WHERE id=:i AND username=:u", i=rid, u=username)

    # 用量与埋点 --------------------------------------------------------
    def used_today(self, username):
        rows = self._rows("SELECT count FROM usage WHERE username=:u AND day=:d", u=username, d=dt.date.today().isoformat())
        return rows[0][0] if rows else 0

    def add_usage(self, username):
        self._exec("INSERT INTO usage VALUES (:u, :d, 1) ON CONFLICT (username, day) DO UPDATE SET count=usage.count+1",
                   u=username, d=dt.date.today().isoformat())

    def log_event(self, username, name):
        self._exec("INSERT INTO events VALUES (:u, :n, :t)", u=username, n=name, t=_now())

    def export_user(self, username):
        return {"profile": self.get_profile(username), "reports": self.list_reports(username), "exported_at": _now()}
