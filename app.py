import asyncio
import base64
import hashlib
import hmac
import html as htmllib
import ipaddress
import json
import logging
import os
import re
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

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
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


# وب‌پس مخفی پنل: ریشه‌ی دامنه صفحه‌ی بی‌ربط می‌دهد و پنل فقط زیر این مسیر بالا می‌آید
def _clean_web_path(raw) -> str:
    value = re.sub(r"[^A-Za-z0-9_-]", "", str(raw or "").strip().strip("/"))
    return value[:48]


WEB_PATH = _clean_web_path(os.getenv("WEB_PATH", ""))
PANEL_PREFIX = ("/" + WEB_PATH) if WEB_PATH else ""
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


def get_user_by_name(name: str):
    with _db_lock, db() as conn:
        return rowdict(conn.execute("SELECT * FROM users WHERE lower(name)=lower(?) ORDER BY created_at DESC LIMIT 1", (name,)).fetchone())


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
        "subscription_url": "https://" + primary + "/s/" + user["sub_token"],
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
    if not name:
        raise HTTPException(400, "name is required")
    if get_user_by_name(name):
        raise HTTPException(409, "username already exists")
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
    if "name" in body:
        new_name = str(body["name"]).strip()[:80]
        other = get_user_by_name(new_name)
        if other and other["id"] != user_id:
            raise HTTPException(409, "username already exists")
        updates["name"] = new_name
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


FAKE_HTML = r"""
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow,noarchive,nosnippet">
<title>Fern &amp; Fig — plant notes</title>
<style>
:root{--ink:#26372b;--soft:#6d7f70;--line:#e2eae1;--leaf:#4f8a5b;--cream:#fbfdf9}
*{box-sizing:border-box}
body{margin:0;background:var(--cream);color:var(--ink);font:16px/1.75 Georgia,'Times New Roman',serif;padding:48px 20px}
.wrap{max-width:640px;margin:auto}
.mark{width:46px;height:46px;border-radius:14px;background:#eaf4ea;display:grid;place-items:center;margin-bottom:22px}
h1{font-size:28px;margin:0 0 6px;letter-spacing:.2px}
.sub{color:var(--soft);font-size:14px;margin:0 0 30px}
h2{font-size:18px;margin:34px 0 8px}
p{margin:0 0 14px}
ul{margin:0 0 14px;padding-inline-start:20px}
li{margin-bottom:6px}
.note{border-inline-start:3px solid var(--leaf);background:#f3f8f2;padding:12px 16px;border-radius:0 10px 10px 0;color:#3d5844;font-size:15px}
footer{margin-top:40px;padding-top:18px;border-top:1px solid var(--line);color:var(--soft);font-size:13px}
</style>
</head>
<body>
<div class="wrap">
  <div class="mark"><svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#4f8a5b" stroke-width="1.6" stroke-linecap="round"><path d="M12 21c0-6 3-11 8-13-1 8-4 12-8 13Z"/><path d="M12 21C8 20 5 16 4 8c5 2 8 7 8 13Z"/><path d="M12 21v-5"/></svg></div>
  <h1>Fern &amp; Fig</h1>
  <p class="sub">A small notebook about houseplants, soil mixes and slow mornings.</p>

  <p>This page is a personal archive of watering notes. Nothing here is automated, nothing is for sale, and there is no newsletter to sign up for.</p>

  <h2>Watering rhythm</h2>
  <ul>
    <li>Fiddle leaf fig — every 9 days, room temperature water.</li>
    <li>Boston fern — misted twice a week, never soaked.</li>
    <li>Pothos — whenever the top inch of soil turns dry.</li>
    <li>Snake plant — once a month, less in winter.</li>
  </ul>

  <h2>Soil mix that worked</h2>
  <p>Four parts coco coir, two parts perlite, one part worm castings and a handful of pine bark. It drains fast and the ferns stopped sulking after two weeks.</p>

  <div class="note">Note to self: repot the monstera before spring, and stop buying pots that have no drainage hole.</div>

  <h2>Light notes</h2>
  <p>The east window carries soft morning light until about eleven. Anything that browns at the tips gets moved one meter back, and it usually recovers within a month.</p>

  <footer>Kept as a private garden journal. Last tidy-up: this spring.</footer>
</div>
</body>
</html>
"""


SUB_HTML = r"""
<!doctype html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="robots" content="noindex,nofollow,noarchive,nosnippet">
<meta name="theme-color" content="#f2f8f1">
<title>__NAME__ · اشتراک</title>
<style>
*{box-sizing:border-box}
:root{
 --ink:#1f3226;--soft:#65806e;--line:#dfeade;--white:#fff;
 --leaf:#3f8f57;--leaf2:#6bbd7d;--leaf-soft:#eaf5ea;--gold:#c98a2e;--rose:#c9564b;
 --r:20px;--sh:0 1px 2px rgba(31,50,38,.05),0 12px 32px rgba(31,50,38,.07)
}
html,body{margin:0;padding:0}
body{
 font:15px/1.8 -apple-system,BlinkMacSystemFont,"Segoe UI",Vazirmatn,Tahoma,sans-serif;
 color:var(--ink);min-height:100vh;padding:22px 14px 40px;
 background:
  radial-gradient(760px 420px at 90% -10%,#e7f4e6 0,transparent 70%),
  radial-gradient(620px 380px at 5% 8%,#f0f8ee 0,transparent 65%),
  linear-gradient(180deg,#f7fbf6,#f2f8f1 55%,#eef6ee);
}
.wrap{max-width:660px;margin:auto}
.card{background:var(--white);border:1px solid var(--line);border-radius:var(--r);box-shadow:var(--sh);padding:22px;margin-bottom:16px}
header.card{display:flex;align-items:center;gap:14px}
.logo{width:52px;height:52px;flex:0 0 52px;border-radius:16px;background:linear-gradient(150deg,#eaf5ea,#d9eedb);display:grid;place-items:center}
.who{flex:1;min-width:0}
h1{font-size:20px;margin:0 0 3px;font-weight:800;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.who p{margin:0;color:var(--soft);font-size:13px}
.chip{flex:0 0 auto;font-size:12px;font-weight:700;padding:7px 13px;border-radius:999px;background:var(--leaf-soft);color:#2e6c41;border:1px solid #cfe7d2}
.chip.warn{background:#fdf5e6;color:#8a5c14;border-color:#f0e0be}
.chip.off{background:#fdeeec;color:#a83a30;border-color:#f2cfcb}
.hero{display:flex;gap:20px;align-items:center;flex-wrap:wrap}
.ring{--p:0;width:132px;height:132px;flex:0 0 132px;border-radius:50%;display:grid;place-items:center;
 background:conic-gradient(var(--leaf) calc(var(--p)*1%),#eaf1e9 0)}
.ring.hot{background:conic-gradient(var(--gold) calc(var(--p)*1%),#f3ede2 0)}
.hole{width:104px;height:104px;border-radius:50%;background:var(--white);display:grid;place-items:center;text-align:center;box-shadow:inset 0 0 0 1px #edf3ec}
.hole b{display:block;font-size:26px;font-weight:800;line-height:1.2}
.hole b i{font-size:14px;font-style:normal;color:var(--soft)}
.hole small{color:var(--soft);font-size:12px}
.tiles{flex:1;min-width:230px;display:grid;grid-template-columns:1fr 1fr;gap:10px}
.tile{background:#f8fbf7;border:1px solid #e9f1e8;border-radius:14px;padding:11px 13px}
.tile small{display:block;color:var(--soft);font-size:11.5px;margin-bottom:3px}
.tile b{font-size:14.5px;font-weight:800}
.tile b i{font-style:normal;font-weight:500;color:var(--soft);font-size:12px}
.boxhead{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:12px}
h2{font-size:15.5px;margin:0;font-weight:800}
h2 span{color:var(--soft);font-weight:500;font-size:12.5px}
.btn{border:1px solid var(--leaf);background:var(--leaf);color:#fff;font:inherit;font-size:13px;font-weight:700;
 min-height:38px;padding:0 15px;border-radius:11px;cursor:pointer;transition:.15s}
.btn:active{transform:translateY(1px)}
.btn.ghost{background:#fff;color:#2e6c41;border-color:#cfe7d2}
.btn.tiny{min-height:32px;padding:0 12px;font-size:12px}
.url{direction:ltr;text-align:left;font:12.5px/1.7 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
 background:#f6faf5;border:1px dashed #d5e6d4;border-radius:12px;padding:11px 13px;word-break:break-all;color:#2c4433}
.apps{display:flex;flex-wrap:wrap;gap:8px;margin-top:14px}
.app{display:inline-flex;align-items:center;gap:7px;text-decoration:none;font-size:12.5px;font-weight:700;color:#2e6c41;
 background:#f4faf3;border:1px solid #dceadb;border-radius:11px;padding:9px 13px}
.app:active{background:#eaf5ea}
.app u{text-decoration:none;color:var(--soft);font-weight:500}
.hint{color:var(--soft);font-size:12.5px;margin:12px 0 0}
.cfg{display:flex;align-items:center;gap:11px;padding:11px 0;border-top:1px solid #f0f5ef}
.cfg:first-of-type{border-top:0}
.cfg .n{width:28px;height:28px;flex:0 0 28px;border-radius:9px;background:var(--leaf-soft);color:#2e6c41;
 display:grid;place-items:center;font-size:12.5px;font-weight:800}
.cfg .t{flex:1;min-width:0}
.cfg .t b{display:block;font-size:13.5px}
.cfg .t span{display:block;color:var(--soft);font-size:11.5px;direction:ltr;text-align:left;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
details{border:1px solid #e9f1e8;border-radius:14px;padding:0 13px;margin-bottom:9px;background:#fcfefb}
details[open]{background:#f8fbf7}
summary{cursor:pointer;font-weight:700;font-size:13.5px;padding:12px 0;list-style:none;display:flex;justify-content:space-between;align-items:center}
summary::-webkit-details-marker{display:none}
summary::after{content:"+";color:var(--leaf);font-weight:800;font-size:17px}
details[open] summary::after{content:"−"}
.steps{margin:0 0 12px;padding-inline-start:19px;color:#33503c;font-size:13px}
.steps li{margin-bottom:5px}
.muted{color:var(--soft);font-size:12.5px;margin:0}
footer{text-align:center;color:var(--soft);font-size:12px;padding:6px 4px 0;line-height:2}
.toast{position:fixed;inset-inline:0;bottom:20px;margin:auto;width:max-content;max-width:88%;
 background:#1f3226;color:#fff;font-size:13px;padding:11px 18px;border-radius:12px;
 opacity:0;transform:translateY(12px);transition:.22s;pointer-events:none;z-index:9}
.toast.on{opacity:1;transform:none}
@media(max-width:560px){
 .hero{gap:14px}.ring{width:112px;height:112px;flex:0 0 112px}.hole{width:88px;height:88px}
 .hole b{font-size:22px}.tiles{grid-template-columns:1fr 1fr;min-width:100%}.card{padding:18px}
}
@media(prefers-color-scheme:dark){
 :root{--ink:#e7f0e7;--soft:#9db3a3;--line:#28362b;--white:#16211a;--leaf-soft:#1e3324}
 body{background:linear-gradient(180deg,#111a14,#0f1712 60%,#101a13)}
 .tile,.url,.app,details{background:#182319;border-color:#28362b}
 details[open]{background:#1a2620}
 .hole{background:var(--white);box-shadow:inset 0 0 0 1px #26332a}
 .ring{background:conic-gradient(var(--leaf2) calc(var(--p)*1%),#22301f 0)}
 .btn.ghost{background:#182319;color:#9fd8ac;border-color:#2c3f30}
 .cfg{border-color:#243027}
}
</style>
</head>
<body>
<div class="wrap">

  <header class="card">
    <div class="logo">
      <svg width="27" height="27" viewBox="0 0 24 24" fill="none" stroke="#3f8f57" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
        <path d="M12 22c0-6.5 3.2-11.6 8.5-13.8C19.6 16 16.4 20.4 12 22Z"/>
        <path d="M12 22C7.6 21 4.4 16.4 3.5 8.2 8.8 10.4 12 15.5 12 22Z"/>
        <path d="M12 22v-4.4"/>
      </svg>
    </div>
    <div class="who">
      <h1>__NAME__</h1>
      <p>اشتراک شخصی · __COUNT__ سرور فعال</p>
    </div>
    <span class="chip __STATE_CLASS__">__STATE_TEXT__</span>
  </header>

  <section class="card hero">
    <div class="ring __RING_CLASS__" style="--p:__PCT_NUM__">
      <div class="hole"><b>__PCT__<i>٪</i></b><small>مصرف شده</small></div>
    </div>
    <div class="tiles">
      <div class="tile"><small>مصرف شده</small><b>__USED__</b></div>
      <div class="tile"><small>باقی‌مانده</small><b>__REMAIN__</b></div>
      <div class="tile"><small>حجم کل</small><b>__TOTAL__</b></div>
      <div class="tile"><small>__EXPIRE_LABEL__</small><b>__EXPIRE__</b></div>
      <div class="tile"><small>دستگاه متصل</small><b>__DEVICES__ <i>از __DEVICE_LIMIT__</i></b></div>
      <div class="tile"><small>اتصال لحظه‌ای</small><b>__TUNNELS__</b></div>
    </div>
  </section>

  <section class="card">
    <div class="boxhead">
      <h2>لینک اشتراک <span>یک بار وارد شود، همیشه به‌روز</span></h2>
      <button class="btn" data-copy="__SUB_URL__">کپی لینک</button>
    </div>
    <div class="url">__SUB_URL__</div>
    <div class="apps">
      <a class="app" href="hiddify://import/__SUB_URL__#__NAME_ENC__">Hiddify <u>افزودن</u></a>
      <a class="app" href="v2box://install-sub?url=__SUB_URL_ENC__&amp;name=__NAME_ENC__">V2Box <u>افزودن</u></a>
      <a class="app" href="v2rayng://install-sub?url=__SUB_URL_ENC__">v2rayNG <u>افزودن</u></a>
      <a class="app" href="streisand://import/__SUB_URL__">Streisand <u>افزودن</u></a>
      <a class="app" href="sub://__SUB_B64__">Shadowrocket <u>افزودن</u></a>
      <a class="app" href="clash://install-config?url=__SUB_URL_ENC__">Clash <u>افزودن</u></a>
      <a class="app" href="sing-box://import-remote-profile?url=__SUB_URL_ENC__">sing-box <u>افزودن</u></a>
    </div>
    <p class="hint">دکمه‌های بالا لینک را مستقیم داخل برنامه اضافه می‌کنند. اگر باز نشد، لینک را کپی کن و در برنامه گزینه‌ی «افزودن اشتراک از کلیپ‌بورد» را بزن.</p>
  </section>

  <section class="card">
    <div class="boxhead">
      <h2>کانفیگ‌های مستقیم <span>برای اتصال دستی</span></h2>
      <button class="btn ghost" id="copyAll">کپی همه</button>
    </div>
    __CONFIG_ROWS__
  </section>

  <section class="card">
    <div class="boxhead"><h2>راهنمای اتصال <span>دو دقیقه کار دارد</span></h2></div>

    <details open>
      <summary>اندروید</summary>
      <ol class="steps">
        <li>یکی از برنامه‌ها را نصب کن: <a href="https://play.google.com/store/apps/details?id=dev.hexasoftware.v2box">V2Box</a> ، <a href="https://play.google.com/store/apps/details?id=com.netmod.syna">NetMod Syna</a> ، <a href="https://github.com/2dust/v2rayNG/releases">v2rayNG</a> ، <a href="https://github.com/hiddify/hiddify-app/releases">Hiddify</a></li>
        <li>دکمه‌ی «کپی لینک» همین صفحه را بزن.</li>
        <li>در برنامه: <b>Subscription ← +</b> یا «افزودن از کلیپ‌بورد».</li>
        <li>یک بار <b>Update</b> بزن و سرور را وصل کن.</li>
      </ol>
      <p class="muted">اگر برنامه نصب است، همان دکمه‌های سبز بالا کار را در یک مرحله تمام می‌کند.</p>
    </details>

    <details>
      <summary>آیفون و آیپد</summary>
      <ol class="steps">
        <li>نصب از App Store: <a href="https://apps.apple.com/app/id6446814690">V2Box</a> ، <a href="https://apps.apple.com/app/id6450534064">Streisand</a> ، <a href="https://apps.apple.com/app/id6596777532">Hiddify</a> ، <a href="https://apps.apple.com/app/id6476628140">Karing</a> ، <a href="https://apps.apple.com/app/id932747118">Shadowrocket</a></li>
        <li>لینک اشتراک را کپی کن.</li>
        <li>در برنامه: <b>Configs ← + ← Add Subscription</b> و لینک را پیست کن.</li>
        <li>اجازه‌ی VPN را تأیید کن و وصل شو.</li>
      </ol>
    </details>

    <details>
      <summary>ویندوز</summary>
      <ol class="steps">
        <li>نصب: <a href="https://github.com/2dust/v2rayN/releases">v2rayN</a> ، <a href="https://github.com/hiddify/hiddify-app/releases">Hiddify</a> ، <a href="https://github.com/MatsuriDayo/NekoBoxForAndroid/releases">NekoBox</a></li>
        <li>لینک اشتراک را کپی کن.</li>
        <li>در v2rayN: <b>Subscription ← Subscription group setting ← Add</b> و پیست کن، بعد <b>Update subscription</b>.</li>
        <li>حالت سیستم را روی <b>Proxy</b> بگذار.</li>
      </ol>
    </details>

    <details>
      <summary>مک و لینوکس</summary>
      <ol class="steps">
        <li>نصب: <a href="https://apps.apple.com/app/id6446814690">V2Box مک</a> ، <a href="https://github.com/hiddify/hiddify-app/releases">Hiddify</a> ، <a href="https://github.com/clash-verge-rev/clash-verge-rev/releases">Clash Verge</a></li>
        <li>لینک اشتراک را کپی کن و در برنامه به عنوان Profile/Subscription اضافه کن.</li>
        <li>یک بار به‌روزرسانی بزن و سرور را انتخاب کن.</li>
      </ol>
    </details>

    <details>
      <summary>مشکل داری؟</summary>
      <ul class="steps">
        <li>اگر وصل شد ولی اینترنت نداری، یک سرور دیگر از لیست را امتحان کن.</li>
        <li>اگر حجم تمام شده یا تاریخ گذشته، همین صفحه وضعیت را نشان می‌دهد.</li>
        <li>لینک اشتراک را با کسی به اشتراک نگذار؛ تعداد دستگاه محدود است.</li>
        <li>هر چند روز یک بار در برنامه <b>Update</b> بزن تا سرورهای جدید بیایند.</li>
      </ul>
    </details>
  </section>

  <footer>
    به‌روزرسانی: __UPDATED__ · این صفحه فقط برای شماست<br>
    لینک اشتراک را جایی منتشر نکن
  </footer>
</div>

<div id="toast" class="toast"></div>
<script>
(function(){
  var t=document.getElementById('toast'),timer=null;
  function say(m){t.textContent=m;t.classList.add('on');clearTimeout(timer);timer=setTimeout(function(){t.classList.remove('on')},1900)}
  function copy(text,msg){
    if(navigator.clipboard&&navigator.clipboard.writeText){
      navigator.clipboard.writeText(text).then(function(){say(msg)},function(){fallback(text,msg)})
    }else{fallback(text,msg)}
  }
  function fallback(text,msg){
    var a=document.createElement('textarea');a.value=text;a.setAttribute('readonly','');
    a.style.position='fixed';a.style.top='-1000px';document.body.appendChild(a);a.select();
    try{document.execCommand('copy');say(msg)}catch(e){say('کپی نشد، دستی انتخاب کن')}
    document.body.removeChild(a)
  }
  document.addEventListener('click',function(e){
    var el=e.target.closest('[data-copy]');
    if(el){e.preventDefault();copy(el.getAttribute('data-copy'),'کپی شد ✓');return}
    if(e.target.id==='copyAll'){
      var all=[].map.call(document.querySelectorAll('.cfg [data-copy]'),function(x){return x.getAttribute('data-copy')});
      if(all.length){copy(all.join('\n'),'همه‌ی کانفیگ‌ها کپی شد ✓')}else{say('کانفیگی نیست')}
    }
  })
})();
</script>
</body>
</html>
"""

NOINDEX = {"x-robots-tag": "noindex, nofollow, noarchive"}
FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
JMONTHS = ("فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور", "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند")
BYTE_UNITS = ("بایت", "کیلوبایت", "مگابایت", "گیگابایت", "ترابایت")
CLIENT_UA_HINTS = (
    "v2ray", "v2box", "hiddify", "clash", "sing-box", "singbox", "shadowrocket", "streisand",
    "nekobox", "nekoray", "karing", "loon", "quantumult", "surge", "stash", "foxray", "sagernet",
    "netmod", "okhttp", "go-http-client", "curl", "wget", "python-requests", "node-fetch", "dart",
)


def fa(value) -> str:
    return str(value).translate(FA_DIGITS)


def esc(value) -> str:
    return htmllib.escape(str(value if value is not None else ""), quote=True)


def fmt_bytes(value) -> str:
    amount = float(value or 0)
    if amount <= 0:
        return fa("0") + " " + BYTE_UNITS[0]
    step = 0
    while amount >= 1024 and step < len(BYTE_UNITS) - 1:
        amount /= 1024.0
        step += 1
    if step <= 1 or amount >= 100:
        text = "%.0f" % amount
    else:
        text = ("%.2f" % amount).rstrip("0").rstrip(".")
    return fa(text) + " " + BYTE_UNITS[step]


def to_jalali(moment: datetime):
    gy, gm, gd = moment.year, moment.month, moment.day
    months = (0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334)
    gy2 = gy - 1600
    days = 365 * gy2 + (gy2 + 3) // 4 - (gy2 + 99) // 100 + (gy2 + 399) // 400
    days += months[gm - 1] + gd - 1
    if gm > 2 and ((gy % 4 == 0 and gy % 100 != 0) or gy % 400 == 0):
        days += 1
    days -= 79
    cycles = days // 12053
    days %= 12053
    jy = 979 + 33 * cycles + 4 * (days // 1461)
    days %= 1461
    if days >= 366:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        return jy, 1 + days // 31, 1 + days % 31
    return jy, 7 + (days - 186) // 30, 1 + (days - 186) % 30


def tehran_now() -> datetime:
    return datetime.fromtimestamp(time.time() + 12600, timezone.utc)


def jalali_stamp(moment: datetime) -> str:
    jy, jm, jd = to_jalali(moment)
    return fa("%d %s %d" % (jd, JMONTHS[jm - 1], jy))


def jalali_text(raw) -> str:
    if not raw:
        return "بدون انقضا"
    try:
        moment = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return "نامشخص"
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    left = int((moment - datetime.now(timezone.utc)).total_seconds() // 86400)
    stamp = jalali_stamp(datetime.fromtimestamp(moment.timestamp() + 12600, timezone.utc))
    if left < 0:
        return stamp + " · تمام شده"
    if left == 0:
        return stamp + " · امروز"
    return stamp + " · " + fa(left) + " روز مانده"


def live_devices(user: dict) -> int:
    return int(_conn_counts.get(user["id"], 0))


def wants_html(request: Request) -> bool:
    accept = str(request.headers.get("accept") or "").lower()
    agent = str(request.headers.get("user-agent") or "").lower()
    if "text/html" not in accept:
        return False
    for hint in CLIENT_UA_HINTS:
        if hint in agent:
            return False
    return "mozilla" in agent


def with_base(page: str) -> str:
    if not PANEL_PREFIX:
        return page
    out = page
    out = out.replace("fetch('/auth/", "fetch(BASE+'/auth/")
    out = out.replace("fetch('/api/", "fetch(BASE+'/api/")
    out = out.replace("api('/api/", "api(BASE+'/api/")
    out = out.replace("location='/dashboard'", "location=BASE+'/dashboard'")
    out = out.replace("location='/login'", "location=BASE+'/login'")
    out = out.replace("location.origin+'/api/", "location.origin+BASE+'/api/")
    return out.replace("<script>", "<script>var BASE=" + json.dumps(PANEL_PREFIX) + ";", 1)


def render_subscription_page(user: dict, links: list, sub_url: str) -> str:
    used = int(user.get("used_bytes") or 0)
    quota = int(user.get("quota_bytes") or 0)
    devices = live_devices(user)
    limit = int(user.get("max_connections") or 0)
    percent = min(100, int(round(used * 100.0 / quota))) if quota else 0
    allowed = user_is_allowed(user)
    if not user.get("enabled"):
        state_class, state_text = "off", "غیرفعال"
    elif not allowed:
        state_class, state_text = "off", "پایان‌یافته"
    elif quota and percent >= 85:
        state_class, state_text = "warn", "نزدیک پایان حجم"
    else:
        state_class, state_text = "", "فعال"
    rows = []
    for index, link in enumerate(links, 1):
        host = ""
        if "@" in link:
            host = link.split("@", 1)[1].split(":", 1)[0].split("?", 1)[0]
        title = host or ("سرور " + str(index))
        rows.append(
            '<div class="cfg"><div class="n">' + fa(index) + '</div><div class="t"><b>'
            + esc(title) + '</b><span>VLESS · WebSocket · TLS</span></div>'
            + '<button class="btn ghost tiny" data-copy="' + esc(link) + '">کپی</button></div>'
        )
    if not rows:
        rows.append('<p class="hint">این اشتراک فعلاً کانفیگ فعالی ندارد. با پشتیبانی در تماس باش.</p>')
    values = {
        "__NAME__": esc(user.get("name")),
        "__NAME_ENC__": quote(str(user.get("name") or ""), safe=""),
        "__COUNT__": fa(len(links)),
        "__STATE_CLASS__": state_class,
        "__STATE_TEXT__": state_text,
        "__RING_CLASS__": "hot" if (quota and percent >= 85) else "",
        "__PCT__": fa(percent),
        "__PCT_NUM__": str(percent),
        "__USED__": fmt_bytes(used),
        "__TOTAL__": fmt_bytes(quota) if quota else "نامحدود",
        "__REMAIN__": fmt_bytes(max(0, quota - used)) if quota else "نامحدود",
        "__DEVICES__": fa(devices),
        "__DEVICE_LIMIT__": fa(limit) if limit else "بی‌نهایت",
        "__TUNNELS__": fa(devices),
        "__EXPIRE_LABEL__": "اعتبار",
        "__EXPIRE__": jalali_text(user.get("expires_at")),
        "__SUB_URL__": esc(sub_url),
        "__SUB_URL_ENC__": quote(sub_url, safe=""),
        "__SUB_B64__": base64.b64encode(sub_url.encode()).decode(),
        "__CONFIG_ROWS__": "\n    ".join(rows),
        "__UPDATED__": jalali_stamp(tehran_now()) + " · " + fa(tehran_now().strftime("%H:%M")),
    }
    page = SUB_HTML
    for key in sorted(values, key=len, reverse=True):
        page = page.replace(key, values[key])
    return page


panel = APIRouter()


@app.get("/health")
async def health():
    return {"ok": True, "service": APP_NAME}


@panel.get("/health")
async def panel_health():
    return {"ok": True, "service": APP_NAME}


@app.get("/")
async def landing():
    # ریشه‌ی دامنه هیچ نشانه‌ای از پنل نمی‌دهد
    return HTMLResponse(content=FAKE_HTML, headers=NOINDEX)


@panel.get("/")
async def panel_root(request: Request):
    target = PANEL_PREFIX + ("/dashboard" if valid_session(request.cookies.get(SESSION_COOKIE)) else "/login")
    return RedirectResponse(target)


@panel.get("/login")
async def login_page():
    return HTMLResponse(content=with_base(LOGIN_HTML), headers=NOINDEX)


@panel.get("/dashboard")
async def dashboard_page(request: Request):
    if not valid_session(request.cookies.get(SESSION_COOKIE)):
        return RedirectResponse(PANEL_PREFIX + "/login")
    return HTMLResponse(content=with_base(DASHBOARD_HTML), headers=NOINDEX)


@panel.post("/auth/login")
async def login(request: Request):
    body = await request.json()
    if not hmac.compare_digest(str(body.get("password", "")), ADMIN_PASSWORD):
        await asyncio.sleep(0.6)
        raise HTTPException(401, "رمز اشتباه است")
    response = JSONResponse({"ok": True})
    response.set_cookie(SESSION_COOKIE, sign_session(int(time.time()) + SESSION_TTL), max_age=SESSION_TTL,
                        httponly=True, secure=True, samesite="strict")
    return response


@panel.post("/auth/logout")
async def logout():
    response = JSONResponse({"ok": True})
    response.delete_cookie(SESSION_COOKIE)
    return response


@panel.get("/api/admin/users")
async def admin_users(request: Request, _=Depends(require_admin)):
    primary = request_host(request)
    return [public_user(u, primary) for u in list_users()]


@panel.get("/api/admin/status")
async def admin_status(_=Depends(require_admin)):
    return {
        "active_streams": sum(_conn_counts.values()),
        "recent_events": list(_recent_events)[:30],
    }


@panel.post("/api/admin/users")
async def admin_create_user(request: Request, _=Depends(require_admin)):
    user = create_user_record(await request.json())
    return public_user(user, request_host(request))


@panel.patch("/api/admin/users/{user_id}")
async def admin_update_user(user_id: str, request: Request, _=Depends(require_admin)):
    return public_user(update_user_record(user_id, await request.json()), request_host(request))


@panel.delete("/api/admin/users/{user_id}")
async def admin_delete_user(user_id: str, _=Depends(require_admin)):
    with _db_lock, db() as conn:
        cur = conn.execute("DELETE FROM users WHERE id=?", (user_id,))
    if not cur.rowcount: raise HTTPException(404, "user not found")
    return {"ok": True}


@panel.get("/api/admin/domains")
async def admin_domains(request: Request, _=Depends(require_admin)):
    return {"primary": request_host(request), "domains": enabled_domains()}


@panel.post("/api/admin/domains")
async def admin_add_domain(request: Request, _=Depends(require_admin)):
    domain = normalized_domain((await request.json()).get("domain", ""))
    with _db_lock, db() as conn:
        conn.execute("INSERT OR REPLACE INTO domains(domain,enabled,created_at) VALUES(?,1,?)", (domain, now_iso()))
    return {"ok": True, "domain": domain}


@panel.delete("/api/admin/domains/{domain}")
async def admin_delete_domain(domain: str, _=Depends(require_admin)):
    domain = normalized_domain(domain)
    with _db_lock, db() as conn:
        conn.execute("DELETE FROM domains WHERE domain=?", (domain,))
    return {"ok": True}


@panel.get("/api/v1/users")
async def bot_list_users(request: Request, name: str | None = None, _=Depends(require_bot)):
    if name:
        user = get_user_by_name(name.strip())
        return {"user": public_user(user, request_host(request)) if user else None}
    return {"users": [public_user(u, request_host(request)) for u in list_users()]}


@panel.get("/api/v1/stats")
async def bot_stats(_=Depends(require_bot)):
    with _db_lock, db() as conn:
        row = conn.execute("SELECT COUNT(*) users, COALESCE(SUM(quota_bytes),0) allocated_bytes, COALESCE(SUM(used_bytes),0) used_bytes FROM users").fetchone()
    return {"ok": True, "users": int(row["users"]), "allocated_bytes": int(row["allocated_bytes"]), "used_bytes": int(row["used_bytes"])}


@panel.post("/api/v1/users")
async def bot_create_user(request: Request, _=Depends(require_bot)):
    user = create_user_record(await request.json())
    return {"ok": True, "user": public_user(user, request_host(request))}


@panel.get("/api/v1/users/{user_id}")
async def bot_get_user(user_id: str, request: Request, _=Depends(require_bot)):
    user = get_user(user_id)
    if not user: raise HTTPException(404, "user not found")
    return {"user": public_user(user, request_host(request))}


@panel.patch("/api/v1/users/{user_id}")
async def bot_update_user(user_id: str, request: Request, _=Depends(require_bot)):
    return {"ok": True, "user": public_user(update_user_record(user_id, await request.json()), request_host(request))}


@panel.delete("/api/v1/users/{user_id}")
async def bot_delete_user(user_id: str, _=Depends(require_bot)):
    with _db_lock, db() as conn:
        cur = conn.execute("DELETE FROM users WHERE id=?", (user_id,))
    if not cur.rowcount: raise HTTPException(404, "user not found")
    return {"ok": True}


def raw_subscription(user: dict, links: list[str], sub_url: str) -> Response:
    encoded = base64.b64encode("\n".join(links).encode())
    expire = 0
    if user.get("expires_at"):
        try:
            moment = datetime.fromisoformat(str(user["expires_at"]).replace("Z", "+00:00"))
            if moment.tzinfo is None:
                moment = moment.replace(tzinfo=timezone.utc)
            expire = int(moment.timestamp())
        except ValueError:
            expire = 0
    headers = {
        "profile-title": "base64:" + base64.b64encode(user["name"].encode()).decode(),
        "profile-update-interval": "12", "cache-control": "no-store",
        "profile-web-page-url": sub_url,
        "subscription-userinfo": f"upload=0; download={user['used_bytes']}; total={user['quota_bytes'] or 0}; expire={expire}",
    }
    return Response(encoded, media_type="text/plain; charset=utf-8", headers=headers)


def subscription_response(sub_token: str, request: Request, force_raw: bool = False):
    user = get_user_by_sub(sub_token)
    if not user:
        raise HTTPException(404, "subscription unavailable")
    primary = request_host(request)
    links = [make_vless_link(user, d) for d in enabled_domains(primary)] if user_is_allowed(user) else []
    sub_url = "https://" + primary + "/s/" + user["sub_token"]
    if not force_raw and wants_html(request):
        page = render_subscription_page(user, links, sub_url)
        return HTMLResponse(content=page, headers=NOINDEX)
    if not links:
        raise HTTPException(404, "subscription unavailable")
    return raw_subscription(user, links, sub_url)


@app.get("/s/{sub_token}")
async def subscription_smart(sub_token: str, request: Request, raw: int = 0):
    return subscription_response(sub_token, request, force_raw=bool(raw))


@app.get("/s/{sub_token}/raw")
async def subscription_plain(sub_token: str, request: Request):
    return subscription_response(sub_token, request, force_raw=True)


@app.get("/sub/{sub_token}")
async def subscription(sub_token: str, request: Request):
    return subscription_response(sub_token, request, force_raw=True)


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


def _is_api_path(path: str) -> bool:
    for marker in ("/api/", "/auth/", "/s/", "/sub/"):
        if marker in path:
            return True
    return False


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    if exc.status_code == 404 and not _is_api_path(request.url.path):
        return HTMLResponse(content=FAKE_HTML, status_code=404, headers=NOINDEX)
    return JSONResponse({"ok": False, "error": exc.detail}, status_code=exc.status_code)


app.include_router(panel, prefix=PANEL_PREFIX)
if PANEL_PREFIX:
    app.add_api_route(PANEL_PREFIX, panel_root, methods=["GET"])


# هر مسیر ناشناس همان صفحه‌ی بی‌ربط را می‌دهد؛ نه خطای لو دهنده، نه ردیرکت به لاگین
@app.get("/{full_path:path}")
async def unknown_page(full_path: str):
    return HTMLResponse(content=FAKE_HTML, status_code=404, headers=NOINDEX)
