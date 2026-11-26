import json
import re
from pathlib import Path
from uuid import uuid4

import pytest
from helpers import serve_test_app
from playwright.sync_api import expect, sync_playwright
from test_web_push import PATH, browser_subscription

WEB_DIST = Path(__file__).resolve().parents[2] / "web" / "dist"


@pytest.fixture
def browser_site(settings):
    credentials = {"username": "browser-app", "password": "browser-test-password"}
    with serve_test_app(settings.model_copy(update={"static_dir": WEB_DIST})) as (address, web):
        web.post("/api/v1/auth/register", json=credentials).raise_for_status()
        yield address, credentials


def test_login_tracks_the_visible_viewport(browser_site, web_engine):
    address, credentials = browser_site
    with web_engine.launch() as browser:
        page = browser.new_page(
            base_url=address, viewport={"width": 390, "height": 844}, locale="zh-CN"
        )
        page.add_init_script(
            """(() => {
              const viewport = Object.assign(new EventTarget(), {
                height: innerHeight, width: innerWidth, scale: 1, offsetTop: 0, offsetLeft: 0,
              });
              Object.defineProperty(window, 'visualViewport', { value: viewport });
              window.setVisibleViewport = (height, offsetTop) => {
                Object.assign(viewport, { height, offsetTop });
                viewport.dispatchEvent(new Event('resize'));
              };
            })()"""
        )
        page.goto("/workspace/tasks")
        sign_in = page.get_by_role("dialog", name="登录", exact=True)
        sign_in.get_by_label("账号", exact=True).fill(credentials["username"])
        password = sign_in.get_by_label("密码", exact=True)
        password.focus()
        page.evaluate("setVisibleViewport(310, 52)")
        expect(sign_in).to_have_css("top", re.compile(r"^107\.8\d*px$"))
        password.fill(credentials["password"])
        submit = sign_in.get_by_role("button", name="登录", exact=True)
        submit.scroll_into_view_if_needed()
        bounds = submit.bounding_box()
        assert bounds and 52 <= bounds["y"] < bounds["y"] + bounds["height"] <= 362
        with page.expect_response("**/api/v1/auth/login") as login:
            submit.click()
        assert login.value.ok
        expect(sign_in).not_to_be_visible()
        page.set_viewport_size({"width": 844, "height": 390})
        page.evaluate(
            """() => {
              setVisibleViewport(390, 0);
              document.documentElement.style.setProperty('--ui-safe-left', '42px');
              document.documentElement.style.setProperty('--ui-safe-right', '42px');
            }"""
        )
        page.emulate_media(forced_colors="active")
        selected = page.get_by_role("tab", name="任务", exact=True)
        expect(selected).to_have_css("text-decoration-line", "underline")
        assert (selected.bounding_box() or {})["x"] >= 42


def test_install_and_background_notification(browser_site):
    address, credentials = browser_site
    _, _, subscription = browser_subscription()
    with sync_playwright() as playwright, playwright.chromium.launch() as browser:
        context = browser.new_context(base_url=address, locale="zh-CN")
        context.grant_permissions(["notifications"], origin=address)
        context.add_init_script(
            f"""(() => {{
              const subscription = {json.dumps(subscription)};
              function readSubscription() {{
                const key = JSON.parse(localStorage.getItem('test.push-key'));
                if (!key) return null;
                return {{
                  endpoint: subscription.endpoint,
                  expirationTime: null,
                  options: {{ applicationServerKey: Uint8Array.from(key).buffer }},
                  toJSON: () => ({{ keys: subscription }}),
                  unsubscribe: () => {{
                    localStorage.removeItem('test.push-key');
                    return Promise.resolve(true);
                  }},
                }};
              }}
              PushManager.prototype.getSubscription = () => Promise.resolve(readSubscription());
              PushManager.prototype.subscribe = (options) => {{
                localStorage.setItem('test.push-key', JSON.stringify(Array.from(options.applicationServerKey)));
                return Promise.resolve(readSubscription());
              }};
            }})()"""
        )
        page = context.new_page()
        page.goto("/")
        manifest_response = page.request.get("/manifest.webmanifest")
        assert manifest_response.ok
        manifest = manifest_response.json()
        assert manifest["display"] == "standalone"
        for icon in manifest["icons"]:
            assert page.request.get(icon["src"]).headers["content-type"] == "image/png"
        expect(page.get_by_role("banner")).to_be_visible()
        page.evaluate(
            """() => window.dispatchEvent(Object.assign(new Event('beforeinstallprompt'), {
              prompt: () => { window.installOpened = true; return Promise.resolve({outcome: 'accepted'}); },
            }))"""
        )
        page.get_by_role("button", name="安装应用", exact=True).click()
        assert page.evaluate("window.installOpened")
        login = page.request.post(
            "/api/v1/auth/login", data=credentials, headers={"Origin": address}
        )
        assert login.ok
        page.reload()
        account = page.get_by_role("button", name="账户 browser-app", exact=True)
        account.click()
        page.get_by_role("menuitem", name="生成完成通知", exact=True).click()
        dialog = page.get_by_role("dialog", name="生成完成通知", exact=True)
        enable = dialog.get_by_role("button", name="开启通知", exact=True)
        expect(enable).to_be_enabled()
        with page.expect_response(
            lambda response: response.url.endswith(PATH) and response.request.method == "PUT"
        ) as enabled:
            enable.click()
        assert enabled.value.status == 204, enabled.value.text()
        expect(dialog.get_by_text("通知已开启", exact=True)).to_be_visible()
        dialog.get_by_role("button", name="关闭", exact=True).click()
        expect(account).to_be_focused()

        # 保留真实 PushEvent 和服务工作线程。无系统通知服务的测试浏览器记录展示请求。
        (worker,) = context.service_workers
        worker.evaluate(
            """() => {
              ServiceWorkerRegistration.prototype.showNotification = async (title, options) => {
                const cache = await caches.open('test-browser-notifications');
                await cache.put('/test-browser-notifications/' + options.tag,
                  Response.json([title, options.data.url]));
              };
            }"""
        )
        monitor = context.new_page()
        monitor.goto("/manifest.webmanifest")
        cdp = context.new_cdp_session(monitor)
        registrations = []
        worker_errors = []
        cdp.on(
            "ServiceWorker.workerRegistrationUpdated",
            lambda data: registrations.extend(data["registrations"]),
        )
        cdp.on("ServiceWorker.workerErrorReported", lambda data: worker_errors.append(data))
        cdp.send("ServiceWorker.enable")
        page.close()
        registration = next(item for item in registrations if item["scopeURL"] == address + "/")
        task = str(uuid4())
        tag = task.replace("-", "")
        cdp.send(
            "ServiceWorker.deliverPushMessage",
            {
                "origin": address,
                "registrationId": registration["registrationId"],
                "data": json.dumps(
                    {
                        "title": "生成完成",
                        "body": "新成品已就绪，打开任务查看。",
                        "url": f"/workspace/tasks?task={task}&space=personal",
                        "tag": tag,
                    }
                ),
            },
        )
        notification = monitor.evaluate(
            """async (tag) => {
              const cache = await caches.open('test-browser-notifications');
              for (let attempt = 0; attempt < 80; attempt++) {
                const notice = await cache.match('/test-browser-notifications/' + tag);
                if (notice) return notice.json();
                await new Promise(resolve => setTimeout(resolve, 50));
              }
              return null;
            }""",
            tag,
        )
        assert notification == [
            "生成完成",
            f"{address}/workspace/tasks?task={task}&space=personal",
        ], worker_errors
        monitor.goto("/")
        monitor.get_by_role("button", name="账户 browser-app", exact=True).click()
        monitor.get_by_role("menuitem", name="生成完成通知", exact=True).click()
        settings = monitor.get_by_role("dialog", name="生成完成通知", exact=True)
        assert monitor.request.get(PATH).json()["enabled"]
        with monitor.expect_response(
            lambda response: response.url.endswith(PATH) and response.request.method == "DELETE"
        ) as disabled:
            settings.get_by_role("button", name="关闭通知", exact=True).click()
        assert disabled.value.status == 204
        expect(settings.get_by_text("通知已关闭", exact=True)).to_be_visible()


def test_notification_settings_handle_an_unavailable_browser_service(browser_site):
    address, credentials = browser_site
    with sync_playwright() as playwright, playwright.chromium.launch() as browser:
        page = browser.new_page(
            base_url=address, viewport={"width": 320, "height": 700}, locale="zh-CN"
        )
        page.add_init_script(
            """PushManager.prototype.getSubscription = () =>
              Promise.reject(new DOMException('Platform service unavailable', 'IndexSizeError'));"""
        )
        assert page.request.post(
            "/api/v1/auth/login", data=credentials, headers={"Origin": address}
        ).ok
        page.goto("/")
        account = page.get_by_role("button", name="账户 browser-app", exact=True)
        account.click()
        page.get_by_role("menuitem", name="生成完成通知", exact=True).click()
        dialog = page.get_by_role("dialog", name="生成完成通知", exact=True)
        expect(dialog.get_by_text("浏览器通知需要受支持的浏览器和 HTTPS 地址。")).to_be_visible()
        expect(dialog.get_by_role("button", name="开启通知", exact=True)).to_be_disabled()
        expect(dialog.get_by_role("alert")).to_have_count(0)
        dialog.get_by_role("button", name="关闭", exact=True).click()
        expect(account).to_be_focused()
