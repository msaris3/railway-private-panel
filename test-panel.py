# -*- coding: utf-8 -*-
# تست پنل بدون نیاز به نصب FastAPI — با استاب سبک
import base64
import os
import pathlib
import re
import sys
import tempfile
import types

HERE = pathlib.Path(__file__).resolve().parent.parent
TMP = tempfile.mkdtemp(prefix="rpp-test-")

os.environ["ADMIN_PASSWORD"] = "test-admin-password-000111"
os.environ["BOT_API_KEY"] = "test-bot-api-key-0001112223"
os.environ["SESSION_SECRET"] = "test-session-secret-000111222333"
os.environ["DATA_DIR"] = TMP
os.environ["WEB_PATH"] = "test873s"

FAILS = []


def check(name, cond, extra=""):
    if cond:
        print("  ok   " + name)
    else:
        FAILS.append(name)
        print("  FAIL " + name + (("  → " + str(extra)[:160]) if extra else ""))


# ============================== استاب FastAPI
class HTTPException(Exception):
    def __init__(self, status_code, detail=None):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class _Res:
    def __init__(self, content=None, status_code=200, media_type=None, headers=None, **kw):
        self.body = content
        self.status_code = status_code
        self.media_type = media_type
        self.headers = dict(headers or {})

    def set_cookie(self, *a, **k):
        pass

    def delete_cookie(self, *a, **k):
        pass


class Response(_Res):
    pass


class HTMLResponse(_Res):
    pass


class JSONResponse(_Res):
    pass


class PlainTextResponse(_Res):
    pass


class FileResponse(_Res):
    pass


class RedirectResponse(_Res):
    def __init__(self, url="", status_code=307, headers=None, **kw):
        super().__init__(content=url, status_code=status_code, headers=headers)
        self.url = url


class _Router:
    def __init__(self, *a, **kw):
        self.routes = []
        self.handlers = {}

    def _register(self, method):
        def outer(path, **kw):
            def inner(fn):
                self.routes.append((method, path, fn))
                return fn
            return inner
        return outer

    def __getattr__(self, name):
        if name in ("get", "post", "put", "patch", "delete", "head", "options", "websocket"):
            return self._register(name)
        raise AttributeError(name)

    def add_api_route(self, path, fn, methods=None, **kw):
        for method in (methods or ["GET"]):
            self.routes.append((method.lower(), path, fn))

    def include_router(self, router, prefix="", **kw):
        for method, path, fn in router.routes:
            self.routes.append((method, prefix + path, fn))

    def exception_handler(self, exc):
        def inner(fn):
            self.handlers[exc] = fn
            return fn
        return inner


class APIRouter(_Router):
    pass


class FastAPI(_Router):
    pass


class Request:
    def __init__(self, headers=None, path="/", cookies=None):
        self.headers = headers or {}
        self.cookies = cookies or {}
        self.url = types.SimpleNamespace(path=path)


class WebSocket:
    pass


class WebSocketDisconnect(Exception):
    pass


def Depends(dependency=None):
    return dependency


fastapi = types.ModuleType("fastapi")
fastapi.APIRouter = APIRouter
fastapi.Depends = Depends
fastapi.FastAPI = FastAPI
fastapi.HTTPException = HTTPException
fastapi.Request = Request
fastapi.WebSocket = WebSocket
fastapi.WebSocketDisconnect = WebSocketDisconnect

responses = types.ModuleType("fastapi.responses")
responses.FileResponse = FileResponse
responses.HTMLResponse = HTMLResponse
responses.JSONResponse = JSONResponse
responses.PlainTextResponse = PlainTextResponse
responses.RedirectResponse = RedirectResponse
responses.Response = Response
fastapi.responses = responses

sys.modules["fastapi"] = fastapi
sys.modules["fastapi.responses"] = responses
sys.path.insert(0, str(HERE))

import app as panel  # noqa: E402

print("\n── وب‌پس مخفی")
check("WEB_PATH خوانده شد", panel.WEB_PATH == "test873s", panel.WEB_PATH)
check("PANEL_PREFIX ساخته شد", panel.PANEL_PREFIX == "/test873s", panel.PANEL_PREFIX)
check("پاکسازی ورودی ساده", panel._clean_web_path("/aB9-_x/") == "aB9-_x")
check("جلوگیری از path traversal", panel._clean_web_path("../../etc/passwd") == "etcpasswd")
check("حروف غیرمجاز حذف می‌شوند", panel._clean_web_path("a b/c?d=1&<x>") == "abcd1x")
check("سقف طول ۴۸", len(panel._clean_web_path("z" * 200)) == 48)
check("خالی معنی بدون وب‌پس", panel._clean_web_path("") == "")

print("\n── مسیرها")
routes = set((m, p) for m, p, _ in panel.app.routes)
check("ریشه‌ی دامنه باز است", ("get", "/") in routes)
check("health روی ریشه ماند (ریلوی)", ("get", "/health") in routes)
check("تونل کانفیگ روی ریشه ماند", ("websocket", "/connect/{path_token}") in routes)
check("لاگین زیر وب‌پس رفت", ("get", "/test873s/login") in routes)
check("داشبورد زیر وب‌پس رفت", ("get", "/test873s/dashboard") in routes)
check("ورود زیر وب‌پس رفت", ("post", "/test873s/auth/login") in routes)
check("API ربات زیر وب‌پس رفت", ("get", "/test873s/api/v1/users") in routes)
check("API مدیر زیر وب‌پس رفت", ("get", "/test873s/api/admin/users") in routes)
check("خود وب‌پس بدون اسلش کار می‌کند", ("get", "/test873s") in routes)
check("لاگین روی ریشه دیگر نیست", ("get", "/login") not in routes)
check("داشبورد روی ریشه دیگر نیست", ("get", "/dashboard") not in routes)
check("API روی ریشه دیگر نیست", ("get", "/api/v1/users") not in routes)
check("اشتراک تازه روی ریشه", ("get", "/s/{sub_token}") in routes)
check("خروجی خام اشتراک", ("get", "/s/{sub_token}/raw") in routes)
check("مسیر قدیمی /sub حفظ شد", ("get", "/sub/{sub_token}") in routes)
check("هر مسیر ناشناس گرفته می‌شود", ("get", "/{full_path:path}") in routes)
get_paths = [p for m, p, _ in panel.app.routes if m == "get"]
check("کچ‌ال آخرین مسیر است", get_paths[-1] == "/{full_path:path}", get_paths[-1])

print("\n── صفحه‌ی پوششی ریشه")
fake = panel.FAKE_HTML
low = fake.lower()
check("صفحه‌ی پوششی ساخته شد", len(fake) > 500)
check("کلمه‌ی پنل ندارد", "پنل" not in fake)
check("نشانه‌ی لاگین ندارد", "login" not in low and "dashboard" not in low)
check("واژه‌های vpn/proxy ندارد", "vpn" not in low and "proxy" not in low and "vless" not in low)
check("از جستجوگرها پنهان می‌شود", "noindex" in low)
check("هدر noindex آماده است", "noindex" in panel.NOINDEX.get("x-robots-tag", ""))

print("\n── مسیردهی فرانت‌اند به وب‌پس")
login = panel.with_base(panel.LOGIN_HTML)
dash = panel.with_base(panel.DASHBOARD_HTML)
check("BASE تزریق شد (لاگین)", 'var BASE="/test873s";' in login)
check("BASE تزریق شد (داشبورد)", 'var BASE="/test873s";' in dash)
check("فرم ورود به مسیر درست می‌زند", "fetch(BASE+'/auth/login'" in login)
check("پس از ورود به داشبورد می‌رود", "location=BASE+'/dashboard'" in login)
check("داشبورد API را درست صدا می‌زند", "api(BASE+'/api/admin/users')" in dash)
check("خروج درست است", "fetch(BASE+'/auth/logout'" in dash)
check("مستند ربات آدرس درست می‌دهد", "location.origin+BASE+'/api/v1/users'" in dash)
check("هیچ مسیر ریشه‌ای جا نمانده", "api('/api/" not in dash and "fetch('/auth/" not in dash)

print("\n── قالب‌های عدد و تاریخ")
check("رقم فارسی", panel.fa(1234) == "۱۲۳۴")
check("صفر بایت", panel.fmt_bytes(0) == "۰ بایت")
check("مگابایت", panel.fmt_bytes(5 * 1024 ** 2) == "۵ مگابایت", panel.fmt_bytes(5 * 1024 ** 2))
check("گیگابایت کسری", panel.fmt_bytes(int(1.5 * 1024 ** 3)) == "۱.۵ گیگابایت", panel.fmt_bytes(int(1.5 * 1024 ** 3)))
check("بدون انقضا", panel.jalali_text(None) == "بدون انقضا")
check("تاریخ شمسی درست", panel.jalali_stamp(panel.datetime(2026, 9, 2, tzinfo=panel.timezone.utc)) == "۱۱ شهریور ۱۴۰۵", panel.jalali_stamp(panel.datetime(2026, 9, 2, tzinfo=panel.timezone.utc)))
check("روزشمار انقضا", "روز مانده" in panel.jalali_text("2099-01-01T00:00:00+00:00"))
check("انقضای گذشته", "تمام شده" in panel.jalali_text("2020-01-01T00:00:00+00:00"))

print("\n── تشخیص مرورگر از اپلیکیشن")
BROWSER = {"accept": "text/html,application/xhtml+xml", "user-agent": "Mozilla/5.0 (iPhone) AppleWebKit Safari", "host": "node1.cncoo.ir"}
check("مرورگر صفحه می‌گیرد", panel.wants_html(Request(headers=BROWSER)))
check("v2rayNG خام می‌گیرد", not panel.wants_html(Request(headers={"accept": "*/*", "user-agent": "v2rayNG/1.8.5"})))
check("Hiddify خام می‌گیرد", not panel.wants_html(Request(headers={"accept": "text/html", "user-agent": "Mozilla/5.0 Hiddify/2.5"})))
check("V2Box خام می‌گیرد", not panel.wants_html(Request(headers={"accept": "text/html", "user-agent": "V2Box/1.0 Mozilla"})))
check("بدون UA خام می‌گیرد", not panel.wants_html(Request(headers={})))
check("curl خام می‌گیرد", not panel.wants_html(Request(headers={"accept": "*/*", "user-agent": "curl/8.4.0"})))

print("\n── صفحه‌ی اشتراک")
USER = {
    "id": "11111111-2222-3333-4444-555555555555",
    "name": "کاربر تست",
    "path_token": "pathtoken0123456789",
    "sub_token": "subtoken9876543210",
    "enabled": 1,
    "quota_bytes": 50 * 1024 ** 3,
    "used_bytes": 12 * 1024 ** 3,
    "expires_at": "2099-01-01T00:00:00+00:00",
    "max_connections": 3,
    "created_at": "2026-01-01T00:00:00+00:00",
    "updated_at": "2026-01-01T00:00:00+00:00",
}
SUB_URL = "https://node1.cncoo.ir/s/" + USER["sub_token"]
links = [panel.make_vless_link(USER, "node1.cncoo.ir"), panel.make_vless_link(USER, "node2.cncoo.ir")]
panel._conn_counts[USER["id"]] = 2
page = panel.render_subscription_page(USER, links, SUB_URL)

left = re.findall(r"__[A-Z0-9_]+__", page)
check("هیچ جایگزینی جا نمانده", not left, left[:6])
check("نام کاربر دیده می‌شود", "کاربر تست" in page)
check("حجم مصرف‌شده درست است", "۱۲ گیگابایت" in page)
check("حجم کل درست است", "۵۰ گیگابایت" in page)
check("حجم باقی‌مانده درست است", "۳۸ گیگابایت" in page)
check("درصد مصرف محاسبه شد", "--p:24" in page, [x for x in page.split() if "--p:" in x][:2])
check("دستگاه متصل و سقف", "۲" in page and "۳" in page)
check("وضعیت فعال", "فعال" in page)
check("لینک اشتراک قابل کپی", SUB_URL in page)
check("هر دو کانفیگ لیست شد", "node1.cncoo.ir" in page and "node2.cncoo.ir" in page)
check("تعداد کانفیگ درست", page.count('data-copy="vless') == 2, page.count('data-copy="vless'))
check("دکمه‌ی Hiddify", "hiddify://import/" in page)
check("دکمه‌ی V2Box", "install-sub?url=" in page)
check("دکمه‌ی Clash", "clash://install-config?url=" in page)
check("دکمه‌ی Streisand", "streisand://import/" in page)
check("دکمه‌ی Shadowrocket", "sub://" in page)
check("راهنمای اندروید", "اندروید" in page)
check("راهنمای آیفون", "آیفون" in page or "iOS" in page)
check("لینک نصب NetMod", "com.netmod.syna" in page)
check("لینک نصب v2rayNG", "2dust/v2rayNG" in page)
check("لینک نصب V2Box", "dev.hexasoftware.v2box" in page)
check("بدون وابستگی بیرونی (CDN)", "cdn." not in page and "googleapis" not in page)
check("قالب راست‌به‌چپ", 'dir="rtl"' in page)

print("\n── حالت‌های خاص اشتراک")
blocked = dict(USER, enabled=0)
check("کاربر غیرفعال نشان داده می‌شود", "غیرفعال" in panel.render_subscription_page(blocked, [], SUB_URL))
unlimited = dict(USER, quota_bytes=0)
check("حجم نامحدود", "نامحدود" in panel.render_subscription_page(unlimited, links, SUB_URL))
nearly = dict(USER, used_bytes=48 * 1024 ** 3)
check("هشدار پایان حجم", "نزدیک پایان حجم" in panel.render_subscription_page(nearly, links, SUB_URL))
noconf = panel.render_subscription_page(dict(USER), [], SUB_URL)
check("بدون کانفیگ پیام مناسب", "کانفیگ فعالی ندارد" in noconf)
xss = dict(USER, name='<img src=x onerror=alert(1)>')
check("نام کاربر امن می‌شود", "<img src=x" not in panel.render_subscription_page(xss, links, SUB_URL))

print("\n── تحویل اشتراک")
panel.get_user_by_sub = lambda token: USER if token == USER["sub_token"] else None
panel.enabled_domains = lambda primary=None: ["node1.cncoo.ir", "node2.cncoo.ir"]
res_html = panel.subscription_response(USER["sub_token"], Request(headers=BROWSER))
check("مرورگر → صفحه‌ی خوشگل", isinstance(res_html, HTMLResponse) and "کاربر تست" in res_html.body)
res_raw = panel.subscription_response(USER["sub_token"], Request(headers={"accept": "*/*", "user-agent": "v2rayNG/1.8.5", "host": "node1.cncoo.ir"}))
decoded = base64.b64decode(res_raw.body).decode()
check("اپلیکیشن → base64 کانفیگ", decoded.startswith("vless://") and decoded.count("vless://") == 2)
check("عنوان پروفایل", res_raw.headers.get("profile-title", "").startswith("base64:"))
check("مصرف در هدر اشتراک", "download=" in res_raw.headers.get("subscription-userinfo", ""))
check("انقضا در هدر اشتراک", "expire=4070908800" in res_raw.headers.get("subscription-userinfo", ""), res_raw.headers.get("subscription-userinfo"))
check("صفحه‌ی وب در هدر", res_raw.headers.get("profile-web-page-url") == SUB_URL)
res_forced = panel.subscription_response(USER["sub_token"], Request(headers=BROWSER), force_raw=True)
check("خروجی خام اجباری", not isinstance(res_forced, HTMLResponse))
try:
    panel.subscription_response("nope-nope-nope", Request(headers=BROWSER))
    check("توکن اشتباه رد می‌شود", False)
except HTTPException as exc:
    check("توکن اشتباه رد می‌شود", exc.status_code == 404)

print("\n── لینک اشتراک در API ربات")
panel.init_db()
pub = panel.public_user(USER, "node1.cncoo.ir")
check("آدرس اشتراک روی /s/ است", pub["subscription_url"] == SUB_URL, pub["subscription_url"])
check("کانفیگ‌ها هم برگردانده می‌شوند", isinstance(pub.get("links"), list))

print("")
if FAILS:
    print("❌ test-panel: %d تست ناموفق" % len(FAILS))
    for name in FAILS:
        print("   • " + name)
    sys.exit(1)
print("✅ test-panel: همه‌ی تست‌ها پاس شدند")
