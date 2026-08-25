import asyncio
import base64
import hashlib
import hmac
import ipaddress
import json
import logging
import os
import secrets
import socket
import sqlite3
import time
import uuid as uuidlib
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from urllib.parse import quote
from collections import deque

from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse, Response

APP_NAME = "Railway Private Panel"
LOGIN_HTML = '<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ورود | پنل خصوصی</title><style>:root{--ink:#2c2c2b;--muted:#7d7a75;--line:#e6e5e3;--soft:#f9f8f7;--blue:#2783de;--red:#e56458}*{box-sizing:border-box}body{margin:0;font-family:Tahoma,Arial,sans-serif;background:#fff;color:var(--ink);min-height:100vh;display:grid;place-items:center;padding:24px}.card{width:min(420px,100%);border:1px solid var(--line);border-radius:12px;padding:32px;box-shadow:0 1px 2px #0000000d,0 4px 12px #0000000a}.mark{width:48px;height:48px;border-radius:10px;background:#e5f2fc;color:var(--blue);display:grid;place-items:center;font-size:24px;font-weight:700}h1{font-size:26px;margin:20px 0 8px}p{color:var(--muted);line-height:1.7;margin:0 0 24px}label{display:block;font-weight:700;margin-bottom:8px}input,button{width:100%;min-height:48px;border-radius:8px;font:inherit}input{border:1px solid var(--line);padding:0 14px;outline:none}input:focus{border-color:var(--blue);box-shadow:0 0 0 3px #e5f2fc}button{margin-top:16px;border:0;background:var(--blue);color:#fff;font-weight:700;cursor:pointer}button:disabled{opacity:.6}.err{min-height:24px;color:var(--red);font-size:14px;margin-top:12px}</style></head><body><main class="card"><div class="mark">R</div><h1>ورود به پنل خصوصی</h1><p>این صفحه فقط برای مدیر است. ربات از کلید API جداگانه استفاده می\u200cکند.</p><form id="f"><label for="pw">رمز مدیریت</label><input id="pw" type="password" autocomplete="current-password" required autofocus><button id="btn">ورود</button><div id="err" class="err" role="alert"></div></form></main><script>f.onsubmit=async e=>{e.preventDefault();btn.disabled=true;err.textContent=\'\';try{let r=await fetch(\'/auth/login\',{method:\'POST\',headers:{\'content-type\':\'application/json\'},body:JSON.stringify({password:pw.value})});let j=await r.json();if(!r.ok)throw Error(j.error||\'خطا\');location=\'/dashboard\'}catch(x){err.textContent=x.message}finally{btn.disabled=false}}</script></body></html>'
DASHBOARD_HTML = '<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>مرکز مدیریت کاربران</title><style>:root{--bg:#f6f7f9;--card:#fff;--ink:#202124;--muted:#6f7379;--line:#e3e5e8;--blue:#2783de;--blue2:#e8f2fd;--green:#2f9563;--green2:#e8f4ed;--amber:#c87722;--red:#d9534f;--red2:#fcebea;--shadow:0 1px 2px #0000000d,0 8px 24px #00000008}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font-family:Tahoma,Arial,sans-serif;min-height:100vh}button,input{font:inherit}.shell{max-width:1180px;margin:auto;padding:24px}.top{display:flex;justify-content:space-between;align-items:center;gap:16px;margin-bottom:24px}.brand{display:flex;align-items:center;gap:13px}.logo{width:48px;height:48px;border-radius:12px;background:linear-gradient(145deg,#2783de,#5e9fe8);color:#fff;display:grid;place-items:center;font-size:22px;font-weight:900;box-shadow:var(--shadow)}h1{font-size:23px;margin:0}.subtitle{color:var(--muted);font-size:13px;margin-top:5px}.topActions{display:flex;gap:8px}.btn{min-height:44px;border:1px solid var(--line);border-radius:9px;background:var(--card);color:var(--ink);padding:0 15px;font-weight:700;cursor:pointer}.btn:hover{border-color:#c8ccd1}.primary{background:var(--blue);border-color:var(--blue);color:#fff}.danger{color:var(--red)}.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:18px}.metric{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px;box-shadow:var(--shadow)}.metric small{color:var(--muted);font-size:13px}.metric strong{display:block;font-size:25px;margin-top:10px}.toolbar,.panel{background:var(--card);border:1px solid var(--line);border-radius:12px;box-shadow:var(--shadow)}.toolbar{padding:14px;display:flex;gap:10px;align-items:center;margin-bottom:16px}.search{flex:1;min-height:44px;border:1px solid var(--line);border-radius:9px;padding:0 14px;outline:none}.search:focus,.field input:focus{border-color:var(--blue);box-shadow:0 0 0 3px var(--blue2)}.panel{padding:18px;margin-bottom:16px}.panelTitle{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:15px}.panelTitle h2{font-size:17px;margin:0}.muted{color:var(--muted)}.users{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.user{border:1px solid var(--line);border-radius:12px;padding:17px;background:#fff}.userTop{display:flex;justify-content:space-between;gap:10px;align-items:flex-start}.userName{font-size:17px;font-weight:800}.uid{font:12px Consolas,monospace;color:var(--muted);margin-top:5px}.tag{display:inline-flex;align-items:center;gap:5px;padding:5px 9px;border-radius:999px;background:var(--green2);color:var(--green);font-size:12px}.tag.off{background:var(--red2);color:var(--red)}.facts{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:15px 0}.fact{background:var(--bg);border-radius:8px;padding:10px}.fact small{display:block;color:var(--muted);font-size:11px;margin-bottom:5px}.fact b{font-size:13px}.progress{height:7px;border-radius:99px;background:#edf0f2;overflow:hidden;margin:8px 0}.progress span{display:block;height:100%;background:linear-gradient(90deg,#2783de,#72bc8f);border-radius:99px}.usageText{display:flex;justify-content:space-between;color:var(--muted);font-size:12px}.actions{display:flex;flex-wrap:wrap;gap:7px;margin-top:15px}.mini{min-height:37px;border:1px solid var(--line);border-radius:8px;background:#fff;padding:0 10px;cursor:pointer;font-size:13px}.mini:hover{background:var(--bg)}.empty{text-align:center;padding:48px 16px;color:var(--muted)}.domains{display:flex;gap:9px}.domains input{flex:1;min-height:44px;border:1px solid var(--line);border-radius:9px;padding:0 13px}.chips{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}.chip{border:1px solid var(--line);background:var(--bg);border-radius:8px;padding:8px 10px;font-size:12px}.events{max-height:220px;overflow:auto}.event{display:flex;gap:10px;padding:9px 0;border-bottom:1px solid var(--line);font-size:12px}.event time{color:var(--muted);direction:ltr}.ok{color:var(--green)}.warn{color:var(--amber)}.error{color:var(--red)}dialog{border:0;border-radius:14px;padding:0;width:min(560px,calc(100% - 28px));box-shadow:0 24px 80px #0004}dialog::backdrop{background:#1118}.modal{padding:22px}.modalHead{display:flex;align-items:center;justify-content:space-between;margin-bottom:20px}.modalHead h2{margin:0;font-size:19px}.x{width:40px;height:40px;border:0;background:var(--bg);border-radius:8px;cursor:pointer}.formGrid{display:grid;grid-template-columns:1fr 1fr;gap:13px}.field label{display:block;font-size:12px;font-weight:700;margin-bottom:7px}.field input{width:100%;height:44px;border:1px solid var(--line);border-radius:8px;padding:0 11px;outline:none}.wide{grid-column:1/-1}.modalActions{display:flex;justify-content:flex-end;gap:8px;margin-top:20px}.toast{position:fixed;left:22px;bottom:22px;background:#202124;color:#fff;padding:12px 16px;border-radius:9px;opacity:0;transform:translateY(10px);transition:.2s;pointer-events:none;z-index:10}.toast.show{opacity:1;transform:none}@media(max-width:850px){.metrics{grid-template-columns:1fr 1fr}.users{grid-template-columns:1fr}.toolbar{flex-wrap:wrap}.search{flex-basis:100%}}@media(max-width:520px){.shell{padding:16px}.top{align-items:flex-start}.topActions .btn:first-child{display:none}.metrics{grid-template-columns:1fr 1fr}.metric{padding:14px}.facts{grid-template-columns:1fr 1fr}.formGrid{grid-template-columns:1fr}.wide{grid-column:auto}.domains{flex-direction:column}}@media(prefers-color-scheme:dark){:root{--bg:#191919;--card:#202020;--ink:#fff;--muted:#ffffffa6;--line:#ffffff2e;--blue:#5e9fe8;--blue2:#5e9fe824;--green:#72bc8f;--green2:#72bc8f20;--red:#e97366;--red2:#e9736620;--shadow:none}.user,.btn,.mini,.search,.domains input,.field input{background:#202020;color:#fff}.fact,.chip,.x{background:#292929}.progress{background:#383836}}</style></head><body><main class="shell"><header class="top"><div class="brand"><div class="logo">R</div><div><h1>مرکز مدیریت کاربران</h1><div class="subtitle">پنل خصوصی Railway · VLESS WebSocket TLS</div></div></div><div class="topActions"><button class="btn" onclick="loadAll()">به\u200cروزرسانی</button><button class="btn" onclick="logout()">خروج</button></div></header><section class="metrics"><article class="metric"><small>کل کاربران</small><strong id="mTotal">—</strong></article><article class="metric"><small>کاربران فعال</small><strong id="mActive">—</strong></article><article class="metric"><small>تونل\u200cهای زنده</small><strong id="mStreams">—</strong></article><article class="metric"><small>مصرف ثبت\u200cشده</small><strong id="mUsage">—</strong></article></section><section class="toolbar"><input id="search" class="search" placeholder="جست\u200cوجوی نام یا UUID…"><button class="btn primary" onclick="openCreate()">+ ساخت کاربر</button><button class="btn" onclick="copyBotDoc()">راهنمای ربات</button></section><section class="panel"><div class="panelTitle"><h2>کاربران</h2><span id="resultCount" class="muted"></span></div><div id="users" class="users"></div><div id="empty" class="empty" hidden>هنوز کاربری ساخته نشده است.</div></section><details class="panel"><summary><b>دامنه\u200cهای جایگزین</b> <span class="muted">(اختیاری)</span></summary><div style="margin-top:15px" class="domains"><input id="domain" dir="ltr" placeholder="vpn.example.com"><button class="btn" onclick="addDomain()">افزودن دامنه</button></div><div id="domainChips" class="chips"></div></details><details class="panel"><summary><b>گزارش اتصال</b> <span class="muted">برای عیب\u200cیابی</span></summary><div id="events" class="events" style="margin-top:12px"></div></details></main><dialog id="editor"><form id="userForm" class="modal"><div class="modalHead"><h2 id="modalTitle">ساخت کاربر</h2><button type="button" class="x" onclick="editor.close()">×</button></div><div class="formGrid"><div class="field wide"><label>نام کاربر</label><input id="fName" required maxlength="80"></div><div class="field"><label>حجم به گیگابایت؛ ۰ نامحدود</label><input id="fQuota" type="number" min="0" step="1" value="20"></div><div class="field"><label>تعداد دستگاه؛ ۰ نامحدود</label><input id="fDevices" type="number" min="0" max="20" value="0"></div><div class="field wide"><label>تاریخ انقضا؛ خالی یعنی بدون انقضا</label><input id="fExpiry" type="date"></div></div><div class="modalActions"><button type="button" class="btn" onclick="editor.close()">لغو</button><button class="btn primary">ذخیره و کپی ساب</button></div></form></dialog><div id="toast" class="toast"></div><script>let allUsers=[],editingId=null;const $=id=>document.getElementById(id);const fmt=n=>{if(!n)return\'0 B\';const u=[\'B\',\'KB\',\'MB\',\'GB\',\'TB\'];let i=Math.min(4,Math.floor(Math.log(n)/Math.log(1024)));return(n/1024**i).toFixed(i>1?1:0)+\' \'+u[i]};const esc=v=>{let e=document.createElement(\'span\');e.textContent=String(v??\'\');return e.innerHTML};function note(m){$(\'toast\').textContent=m;$(\'toast\').classList.add(\'show\');setTimeout(()=>$(\'toast\').classList.remove(\'show\'),2300)}async function api(url,opt={}){let r=await fetch(url,{...opt,headers:{\'content-type\':\'application/json\',...(opt.headers||{})}});if(r.status===401){location=\'/login\';throw Error(\'ورود لازم است\')}let j=await r.json();if(!r.ok)throw Error(j.error||\'خطا\');return j}function pct(u){return u.quota_bytes?Math.min(100,Math.round(100*u.used_bytes/u.quota_bytes)):0}function render(){let q=$(\'search\').value.trim().toLowerCase(),list=allUsers.filter(u=>!q||u.name.toLowerCase().includes(q)||u.id.includes(q));$(\'resultCount\').textContent=list.length+\' مورد\';$(\'empty\').hidden=list.length>0;$(\'users\').innerHTML=list.map(u=>`<article class="user"><div class="userTop"><div><div class="userName">${esc(u.name)}</div><div class="uid">${u.id}</div></div><span class="tag ${u.enabled?\'\':\'off\'}">${u.enabled?\'● فعال\':\'● خاموش\'}</span></div><div class="facts"><div class="fact"><small>تونل زنده</small><b>${u.active_connections||0}</b></div><div class="fact"><small>دستگاه مجاز</small><b>${u.max_connections||\'نامحدود\'}</b></div><div class="fact"><small>انقضا</small><b>${u.expires_at?new Date(u.expires_at).toLocaleDateString(\'fa-IR\'):\'ندارد\'}</b></div></div><div class="usageText"><span>${fmt(u.used_bytes)}</span><span>${u.quota_bytes?fmt(u.quota_bytes):\'نامحدود\'}</span></div><div class="progress"><span style="width:${pct(u)}%"></span></div><div class="actions"><button class="mini" data-act="sub" data-id="${u.id}">کپی ساب</button><button class="mini" data-act="direct" data-id="${u.id}">لینک مستقیم</button><button class="mini" data-act="edit" data-id="${u.id}">ویرایش</button><button class="mini" data-act="toggle" data-id="${u.id}">${u.enabled?\'خاموش\':\'روشن\'}</button><button class="mini" data-act="reset" data-id="${u.id}">صفرکردن مصرف</button><button class="mini danger" data-act="delete" data-id="${u.id}">حذف</button></div></article>`).join(\'\')}async function loadAll(){let [users,status]=await Promise.all([api(\'/api/admin/users\'),api(\'/api/admin/status\')]);allUsers=users;$(\'mTotal\').textContent=users.length;$(\'mActive\').textContent=users.filter(u=>u.enabled).length;$(\'mStreams\').textContent=status.active_streams;$(\'mUsage\').textContent=fmt(users.reduce((a,u)=>a+u.used_bytes,0));render();renderEvents(status.recent_events);await loadDomains()}function renderEvents(items){$(\'events\').innerHTML=items.length?items.map(e=>`<div class="event"><time>${new Date(e.time).toLocaleTimeString(\'fa-IR\')}</time><span class="${e.level===\'warning\'?\'warn\':e.level}">${esc(e.message)}</span><code>${esc((e.user_id||\'\').slice(0,8))}</code></div>`).join(\'\'):\'<div class="empty">هنوز رویدادی ثبت نشده است.</div>\'}function openCreate(){editingId=null;$(\'modalTitle\').textContent=\'ساخت کاربر\';$(\'fName\').value=\'\';$(\'fQuota\').value=20;$(\'fDevices\').value=0;$(\'fExpiry\').value=\'\';editor.showModal()}function openEdit(u){editingId=u.id;$(\'modalTitle\').textContent=\'ویرایش \'+u.name;$(\'fName\').value=u.name;$(\'fQuota\').value=u.quota_bytes?Math.round(u.quota_bytes/1024**3):0;$(\'fDevices\').value=u.max_connections||0;$(\'fExpiry\').value=u.expires_at?u.expires_at.slice(0,10):\'\';editor.showModal()}$(\'userForm\').onsubmit=async e=>{e.preventDefault();let body={name:$(\'fName\').value,quota_gb:+$(\'fQuota\').value,max_connections:+$(\'fDevices\').value,expires_at:$(\'fExpiry\').value?new Date($(\'fExpiry\').value+\'T23:59:59Z\').toISOString():null};let u=editingId?await api(\'/api/admin/users/\'+editingId,{method:\'PATCH\',body:JSON.stringify(body)}):await api(\'/api/admin/users\',{method:\'POST\',body:JSON.stringify(body)});await navigator.clipboard.writeText(u.subscription_url);editor.close();note(\'ذخیره شد و لینک ساب کپی شد\');await loadAll()};$(\'users\').onclick=async e=>{let b=e.target.closest(\'button\');if(!b)return;let u=allUsers.find(x=>x.id===b.dataset.id),a=b.dataset.act;if(a===\'sub\'){await navigator.clipboard.writeText(u.subscription_url);note(\'ساب کپی شد\')}if(a===\'direct\'){await navigator.clipboard.writeText(u.links[0]);note(\'لینک مستقیم کپی شد\')}if(a===\'edit\')openEdit(u);if(a===\'toggle\'){await api(\'/api/admin/users/\'+u.id,{method:\'PATCH\',body:JSON.stringify({enabled:!u.enabled})});await loadAll()}if(a===\'reset\'){if(confirm(\'مصرف این کاربر صفر شود؟\')){await api(\'/api/admin/users/\'+u.id,{method:\'PATCH\',body:JSON.stringify({reset_usage:true})});await loadAll()}}if(a===\'delete\'){if(confirm(\'کاربر حذف شود؟ لینک او فوراً قطع می\u200cشود.\')){await api(\'/api/admin/users/\'+u.id,{method:\'DELETE\'});await loadAll()}}};$(\'search\').oninput=render;async function loadDomains(){let d=await api(\'/api/admin/domains\');$(\'domainChips\').innerHTML=`<span class="chip">اصلی: ${esc(d.primary)}</span>`+d.domains.map(x=>`<span class="chip">${esc(x)} <button data-domain="${esc(x)}">×</button></span>`).join(\'\')}async function addDomain(){if(!$(\'domain\').value)return;await api(\'/api/admin/domains\',{method:\'POST\',body:JSON.stringify({domain:$(\'domain\').value})});$(\'domain\').value=\'\';await loadDomains()}$(\'domainChips\').onclick=async e=>{let d=e.target.dataset.domain;if(d){await api(\'/api/admin/domains/\'+encodeURIComponent(d),{method:\'DELETE\'});await loadDomains()}};function copyBotDoc(){navigator.clipboard.writeText(location.origin+\'/api/v1/users\');note(\'آدرس API ربات کپی شد\')}async function logout(){await fetch(\'/auth/logout\',{method:\'POST\'});location=\'/login\'}loadAll().catch(e=>note(e.message));setInterval(()=>loadAll().catch(()=>{}),10000);</script></body></html>'
DATA_DIR = Path(os.getenv("DATA_DIR", "/data"))
DB_PATH = DATA_DIR / "panel.db"
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
BOT_API_KEY = os.getenv("BOT_API_KEY", "")
SESSION_SECRET = os.getenv("SESSION_SECRET", "")
SESSION_COOKIE = "rpp_admin"
SESSION_TTL = 7 * 24 * 3600
BLOCKED_PORTS = {25, 465, 587}
RELAY_BUFFER = 256 * 1024
USAGE_BATCH = 1024 * 1024
POLICY_CHECK_INTERVAL = 3.0

_db_lock = RLock()
_conn_counts: dict[str, int] = {}
_conn_lock = asyncio.Lock()
_known_ips: dict[str, dict[str, float]] = {}
_recent_events = deque(maxlen=100)
_usage_pending: dict[str, int] = {}
_usage_lock = asyncio.Lock()
_usage_task = None
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("private-panel")


def add_event(level: str, message: str, user_id: str = "") -> None:
    item = {"time": now_iso(), "level": level, "message": message, "user_id": user_id}
    _recent_events.appendleft(item)
    getattr(logger, level if level in {"info", "warning", "error"} else "info")("%s user=%s", message, user_id[:8])


def websocket_client_ip(ws: WebSocket) -> str:
    forwarded = ws.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    real = ws.headers.get("x-real-ip")
    if real:
        return real.strip()
    return ws.client.host if ws.client else "unknown"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def init_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with _db_lock, db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            path_token TEXT NOT NULL UNIQUE,
            sub_token TEXT NOT NULL UNIQUE,
            enabled INTEGER NOT NULL DEFAULT 1,
            quota_bytes INTEGER NOT NULL DEFAULT 0,
            used_bytes INTEGER NOT NULL DEFAULT 0,
            expires_at TEXT,
            max_connections INTEGER NOT NULL DEFAULT 2,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS domains (
            domain TEXT PRIMARY KEY,
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_users_path ON users(path_token);
        CREATE INDEX IF NOT EXISTS idx_users_sub ON users(sub_token);
        """)


def validate_settings() -> None:
    problems = []
    if len(ADMIN_PASSWORD) < 12:
        problems.append("ADMIN_PASSWORD must be at least 12 characters")
    if len(BOT_API_KEY) < 24:
        problems.append("BOT_API_KEY must be at least 24 characters")
    if len(SESSION_SECRET) < 32:
        problems.append("SESSION_SECRET must be at least 32 characters")
    if problems:
        raise RuntimeError("; ".join(problems))


def rowdict(row):
    return dict(row) if row else None


def get_user_by_path(path_token: str):
    with _db_lock, db() as conn:
        return rowdict(conn.execute("SELECT * FROM users WHERE path_token=?", (path_token,)).fetchone())


def get_user(user_id: str):
    with _db_lock, db() as conn:
        return rowdict(conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone())


def get_user_by_sub(sub_token: str):
    with _db_lock, db() as conn:
        return rowdict(conn.execute("SELECT * FROM users WHERE sub_token=?", (sub_token,)).fetchone())


def list_users():
    with _db_lock, db() as conn:
        return [dict(x) for x in conn.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()]


def normalized_domain(value: str) -> str:
    value = (value or "").strip().lower()
    value = value.removeprefix("https://").removeprefix("http://").split("/")[0].split(":")[0]
    if not value or len(value) > 253 or " " in value or "." not in value:
        raise HTTPException(400, "دامنه معتبر نیست")
    allowed = set("abcdefghijklmnopqrstuvwxyz0123456789-.")
    if any(ch not in allowed for ch in value):
        raise HTTPException(400, "دامنه فقط باید شامل حروف انگلیسی، عدد، خط تیره و نقطه باشد")
    return value


def request_host(request: Request) -> str:
    raw = request.headers.get("x-forwarded-host") or request.headers.get("host") or os.getenv("RAILWAY_PUBLIC_DOMAIN", "")
    return normalized_domain(raw)


def enabled_domains(primary: str | None = None) -> list[str]:
    with _db_lock, db() as conn:
        items = [r[0] for r in conn.execute("SELECT domain FROM domains WHERE enabled=1 ORDER BY created_at").fetchall()]
    out = []
    for item in ([primary] if primary else []) + items:
        if item and item not in out:
            out.append(item)
    return out


def user_is_allowed(user: dict) -> bool:
    if not user or not user.get("enabled"):
        return False
    exp = user.get("expires_at")
    if exp:
        try:
            if datetime.fromisoformat(exp.replace("Z", "+00:00")) <= datetime.now(timezone.utc):
                return False
        except ValueError:
            return False
    quota = int(user.get("quota_bytes") or 0)
    pending = _usage_pending.get(user["id"], 0)
    if quota and int(user.get("used_bytes") or 0) + pending >= quota:
        return False
    return True


def make_vless_link(user: dict, domain: str) -> str:
    label = quote(f"{user['name']} | {domain}")
    path = quote(f"/connect/{user['path_token']}", safe="")
    return (
        f"vless://{user['id']}@{domain}:443?encryption=none&security=tls"
        f"&sni={domain}&fp=chrome&alpn=http%2F1.1&type=ws&host={domain}&path={path}#{label}"
    )


def public_user(user: dict, primary: str) -> dict:
    domains = enabled_domains(primary)
    links = [make_vless_link(user, d) for d in domains]
    return {
        "id": user["id"], "name": user["name"], "enabled": bool(user["enabled"]),
        "quota_bytes": user["quota_bytes"], "used_bytes": user["used_bytes"],
        "expires_at": user["expires_at"], "max_connections": user["max_connections"],
        "created_at": user["created_at"], "links": links,
        "active_connections": _conn_counts.get(user["id"], 0),
        "subscription_url": "https://" + primary + "/sub/" + user["sub_token"],
    }


def sign_session(expiry: int) -> str:
    payload = str(expiry)
    sig = hmac.new(SESSION_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


def valid_session(token: str | None) -> bool:
    try:
        expiry, sig = (token or "").split(".", 1)
        expected = hmac.new(SESSION_SECRET.encode(), expiry.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(sig, expected) and int(expiry) > int(time.time())
    except Exception:
        return False


def require_admin(request: Request):
    if not valid_session(request.cookies.get(SESSION_COOKIE)):
        raise HTTPException(401, "unauthorized")
    return True


def require_bot(request: Request):
    auth = request.headers.get("authorization", "")
    supplied = auth[7:] if auth.lower().startswith("bearer ") else ""
    if not hmac.compare_digest(supplied, BOT_API_KEY):
        raise HTTPException(401, "invalid bot api key")
    return True


def create_user_record(body: dict) -> dict:
    name = str(body.get("name") or "کاربر جدید").strip()[:80]
    quota_gb = max(0.0, float(body.get("quota_gb") or 0))
    quota_bytes = int(quota_gb * 1024 ** 3)
    max_connections = min(20, max(0, int(body.get("max_connections", 0))))
    expires_at = body.get("expires_at") or None
    if expires_at:
        try:
            parsed = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            expires_at = parsed.astimezone(timezone.utc).isoformat()
        except ValueError:
            raise HTTPException(400, "expires_at باید تاریخ ISO معتبر باشد")
    user_id = str(uuidlib.uuid4())
    created = now_iso()
    rec = {
        "id": user_id, "name": name, "path_token": secrets.token_urlsafe(18),
        "sub_token": secrets.token_urlsafe(24), "enabled": 1,
        "quota_bytes": quota_bytes, "used_bytes": 0, "expires_at": expires_at,
        "max_connections": max_connections, "created_at": created, "updated_at": created,
    }
    with _db_lock, db() as conn:
        conn.execute("""INSERT INTO users
        (id,name,path_token,sub_token,enabled,quota_bytes,used_bytes,expires_at,max_connections,created_at,updated_at)
        VALUES (:id,:name,:path_token,:sub_token,:enabled,:quota_bytes,:used_bytes,:expires_at,:max_connections,:created_at,:updated_at)""", rec)
    return rec


def update_user_record(user_id: str, body: dict) -> dict:
    user = get_user(user_id)
    if not user:
        raise HTTPException(404, "user not found")
    updates = {}
    if "name" in body: updates["name"] = str(body["name"]).strip()[:80]
    if "enabled" in body: updates["enabled"] = 1 if body["enabled"] else 0
    if "quota_gb" in body: updates["quota_bytes"] = int(max(0.0, float(body["quota_gb"])) * 1024 ** 3)
    if "max_connections" in body: updates["max_connections"] = min(20, max(0, int(body["max_connections"])))
    if "expires_at" in body:
        raw_expiry = body["expires_at"] or None
        if raw_expiry:
            try:
                parsed = datetime.fromisoformat(str(raw_expiry).replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                raw_expiry = parsed.astimezone(timezone.utc).isoformat()
            except ValueError:
                raise HTTPException(400, "expires_at باید تاریخ ISO معتبر باشد")
        updates["expires_at"] = raw_expiry
    if body.get("reset_usage"):
        updates["used_bytes"] = 0
        _usage_pending.pop(user_id, None)
    if body.get("rotate_links"):
        updates["path_token"] = secrets.token_urlsafe(18)
        updates["sub_token"] = secrets.token_urlsafe(24)
    updates["updated_at"] = now_iso()
    with _db_lock, db() as conn:
        sets = ",".join(f"{k}=?" for k in updates)
        conn.execute(f"UPDATE users SET {sets} WHERE id=?", (*updates.values(), user_id))
    return get_user(user_id)


async def add_usage(user_id: str, amount: int) -> None:
    async with _usage_lock:
        _usage_pending[user_id] = _usage_pending.get(user_id, 0) + amount


async def flush_usage() -> None:
    async with _usage_lock:
        pending = dict(_usage_pending)
        _usage_pending.clear()
    if pending:
        with _db_lock, db() as conn:
            conn.executemany("UPDATE users SET used_bytes=used_bytes+?, updated_at=? WHERE id=?", [(n, now_iso(), uid) for uid, n in pending.items()])


async def usage_worker() -> None:
    while True:
        await asyncio.sleep(5)
        await flush_usage()


async def destination_is_safe(host: str, port: int) -> bool:
    if port in BLOCKED_PORTS or not (1 <= port <= 65535):
        return False
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM)
        if not infos:
            return False
        for info in infos:
            ip = ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified:
                return False
        return True
    except Exception:
        return False


def parse_vless_header(data: bytes):
    if len(data) < 24 or data[0] != 0:
        raise ValueError("invalid VLESS header")
    received_uuid = str(uuidlib.UUID(bytes=data[1:17]))
    pos = 17
    addon_len = data[pos]; pos += 1
    if len(data) < pos + addon_len + 4:
        raise ValueError("short VLESS header")
    pos += addon_len
    command = data[pos]; pos += 1
    if command != 1:
        raise ValueError("only TCP command is supported")
    port = int.from_bytes(data[pos:pos+2], "big"); pos += 2
    atype = data[pos]; pos += 1
    if atype == 1:
        if len(data) < pos + 4: raise ValueError("short IPv4")
        host = str(ipaddress.IPv4Address(data[pos:pos+4])); pos += 4
    elif atype == 2:
        if len(data) < pos + 1: raise ValueError("short domain")
        length = data[pos]; pos += 1
        if len(data) < pos + length: raise ValueError("short domain")
        host = data[pos:pos+length].decode("idna"); pos += length
    elif atype == 3:
        if len(data) < pos + 16: raise ValueError("short IPv6")
        host = str(ipaddress.IPv6Address(data[pos:pos+16])); pos += 16
    else:
        raise ValueError("unknown address type")
    return received_uuid, host, port, data[pos:]


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _usage_task
    validate_settings()
    init_db()
    _usage_task = asyncio.create_task(usage_worker())
    yield
    if _usage_task:
        _usage_task.cancel()
    await flush_usage()


app = FastAPI(title=APP_NAME, docs_url=None, redoc_url=None, lifespan=lifespan)


@app.get("/health")
async def health():
    return {"ok": True, "service": APP_NAME}


@app.get("/")
async def root(request: Request):
    return RedirectResponse("/dashboard" if valid_session(request.cookies.get(SESSION_COOKIE)) else "/login")


@app.get("/login")
async def login_page():
    return HTMLResponse(content=LOGIN_HTML)


@app.get("/dashboard")
async def dashboard_page(request: Request):
    if not valid_session(request.cookies.get(SESSION_COOKIE)):
        return RedirectResponse("/login")
    return HTMLResponse(content=DASHBOARD_HTML)


@app.post("/auth/login")
async def login(request: Request):
    body = await request.json()
    if not hmac.compare_digest(str(body.get("password", "")), ADMIN_PASSWORD):
        await asyncio.sleep(0.6)
        raise HTTPException(401, "رمز اشتباه است")
    response = JSONResponse({"ok": True})
    response.set_cookie(SESSION_COOKIE, sign_session(int(time.time()) + SESSION_TTL), max_age=SESSION_TTL,
                        httponly=True, secure=True, samesite="strict")
    return response


@app.post("/auth/logout")
async def logout():
    response = JSONResponse({"ok": True})
    response.delete_cookie(SESSION_COOKIE)
    return response


@app.get("/api/admin/users")
async def admin_users(request: Request, _=Depends(require_admin)):
    primary = request_host(request)
    return [public_user(u, primary) for u in list_users()]


@app.get("/api/admin/status")
async def admin_status(_=Depends(require_admin)):
    return {
        "active_streams": sum(_conn_counts.values()),
        "recent_events": list(_recent_events)[:30],
    }


@app.post("/api/admin/users")
async def admin_create_user(request: Request, _=Depends(require_admin)):
    user = create_user_record(await request.json())
    return public_user(user, request_host(request))


@app.patch("/api/admin/users/{user_id}")
async def admin_update_user(user_id: str, request: Request, _=Depends(require_admin)):
    return public_user(update_user_record(user_id, await request.json()), request_host(request))


@app.delete("/api/admin/users/{user_id}")
async def admin_delete_user(user_id: str, _=Depends(require_admin)):
    with _db_lock, db() as conn:
        cur = conn.execute("DELETE FROM users WHERE id=?", (user_id,))
    if not cur.rowcount: raise HTTPException(404, "user not found")
    return {"ok": True}


@app.get("/api/admin/domains")
async def admin_domains(request: Request, _=Depends(require_admin)):
    return {"primary": request_host(request), "domains": enabled_domains()}


@app.post("/api/admin/domains")
async def admin_add_domain(request: Request, _=Depends(require_admin)):
    domain = normalized_domain((await request.json()).get("domain", ""))
    with _db_lock, db() as conn:
        conn.execute("INSERT OR REPLACE INTO domains(domain,enabled,created_at) VALUES(?,1,?)", (domain, now_iso()))
    return {"ok": True, "domain": domain}


@app.delete("/api/admin/domains/{domain}")
async def admin_delete_domain(domain: str, _=Depends(require_admin)):
    domain = normalized_domain(domain)
    with _db_lock, db() as conn:
        conn.execute("DELETE FROM domains WHERE domain=?", (domain,))
    return {"ok": True}


@app.get("/api/v1/users")
async def bot_list_users(request: Request, _=Depends(require_bot)):
    return {"users": [public_user(u, request_host(request)) for u in list_users()]}


@app.post("/api/v1/users")
async def bot_create_user(request: Request, _=Depends(require_bot)):
    user = create_user_record(await request.json())
    return {"ok": True, "user": public_user(user, request_host(request))}


@app.get("/api/v1/users/{user_id}")
async def bot_get_user(user_id: str, request: Request, _=Depends(require_bot)):
    user = get_user(user_id)
    if not user: raise HTTPException(404, "user not found")
    return {"user": public_user(user, request_host(request))}


@app.patch("/api/v1/users/{user_id}")
async def bot_update_user(user_id: str, request: Request, _=Depends(require_bot)):
    return {"ok": True, "user": public_user(update_user_record(user_id, await request.json()), request_host(request))}


@app.delete("/api/v1/users/{user_id}")
async def bot_delete_user(user_id: str, _=Depends(require_bot)):
    with _db_lock, db() as conn:
        cur = conn.execute("DELETE FROM users WHERE id=?", (user_id,))
    if not cur.rowcount: raise HTTPException(404, "user not found")
    return {"ok": True}


@app.get("/sub/{sub_token}")
async def subscription(sub_token: str, request: Request):
    user = get_user_by_sub(sub_token)
    if not user or not user_is_allowed(user):
        raise HTTPException(404, "subscription unavailable")
    primary = request_host(request)
    links = [make_vless_link(user, d) for d in enabled_domains(primary)]
    raw = "\n".join(links).encode()
    encoded = base64.b64encode(raw)
    headers = {
        "profile-title": "base64:" + base64.b64encode(user["name"].encode()).decode(),
        "profile-update-interval": "12", "cache-control": "no-store",
        "subscription-userinfo": f"upload=0; download={user['used_bytes']}; total={user['quota_bytes'] or 0}; expire=0",
    }
    return Response(encoded, media_type="text/plain; charset=utf-8", headers=headers)


@app.websocket("/connect/{path_token}")
async def vless_ws(ws: WebSocket, path_token: str):
    user = get_user_by_path(path_token)
    if not user or not user_is_allowed(user):
        await ws.close(code=1008)
        return
    uid = user["id"]
    client_ip = websocket_client_ip(ws)
    async with _conn_lock:
        now = time.time()
        seen = _known_ips.setdefault(uid, {})
        for old_ip, last_seen in list(seen.items()):
            if now - last_seen > 600:
                seen.pop(old_ip, None)
        limit = int(user.get("max_connections") or 0)
        if limit and client_ip not in seen and len(seen) >= limit:
            add_event("warning", f"device limit reached from {client_ip}", uid)
            await ws.close(code=1008)
            return
        seen[client_ip] = now
        _conn_counts[uid] = _conn_counts.get(uid, 0) + 1
    await ws.accept()
    add_event("info", f"websocket accepted from {client_ip}", uid)
    writer = None
    try:
        msg = await asyncio.wait_for(ws.receive(), timeout=15)
        first = msg.get("bytes") or b""
        received_uuid, host, port, payload = parse_vless_header(first)
        if not hmac.compare_digest(received_uuid, uid):
            raise ValueError("UUID mismatch")
        if not await destination_is_safe(host, port):
            raise ValueError("destination blocked")
        reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=10)
        add_event("info", f"connected to {host}:{port}", uid)
        if payload:
            writer.write(payload); await writer.drain()
        await add_usage(uid, len(first))
        # VLESS response header: version 0, no response addons. Sending it
        # immediately lets the client mark the TCP tunnel as established.
        await ws.send_bytes(b"\x00\x00")

        async def client_to_remote():
            local_usage = 0
            last_policy_check = 0.0
            try:
                while True:
                    item = await ws.receive()
                    if item["type"] == "websocket.disconnect": return
                    data = item.get("bytes") or b""
                    if not data: continue
                    now = time.monotonic()
                    if now - last_policy_check >= POLICY_CHECK_INTERVAL:
                        if not user_is_allowed(get_user(uid)): return
                        last_policy_check = now
                    writer.write(data)
                    if writer.transport.get_write_buffer_size() > 1024 * 1024:
                        await writer.drain()
                    local_usage += len(data)
                    if local_usage >= USAGE_BATCH:
                        await add_usage(uid, local_usage)
                        local_usage = 0
            finally:
                if local_usage:
                    await add_usage(uid, local_usage)

        async def remote_to_client():
            local_usage = 0
            last_policy_check = 0.0
            try:
                while True:
                    data = await reader.read(RELAY_BUFFER)
                    if not data: return
                    now = time.monotonic()
                    if now - last_policy_check >= POLICY_CHECK_INTERVAL:
                        if not user_is_allowed(get_user(uid)): return
                        last_policy_check = now
                    await ws.send_bytes(data)
                    local_usage += len(data)
                    if local_usage >= USAGE_BATCH:
                        await add_usage(uid, local_usage)
                        local_usage = 0
            finally:
                if local_usage:
                    await add_usage(uid, local_usage)

        tasks = {asyncio.create_task(client_to_remote()), asyncio.create_task(remote_to_client())}
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
    except WebSocketDisconnect:
        add_event("info", "client disconnected", uid)
    except (asyncio.TimeoutError, ValueError, OSError) as exc:
        add_event("warning", f"tunnel error: {type(exc).__name__}: {exc}", uid)
    except Exception as exc:
        add_event("error", f"unexpected tunnel error: {type(exc).__name__}: {exc}", uid)
    finally:
        if writer:
            writer.close()
            try: await writer.wait_closed()
            except Exception: pass
        async with _conn_lock:
            _conn_counts[uid] = max(0, _conn_counts.get(uid, 1) - 1)


@app.exception_handler(HTTPException)
async def http_error(_request: Request, exc: HTTPException):
    return JSONResponse({"ok": False, "error": exc.detail}, status_code=exc.status_code)
