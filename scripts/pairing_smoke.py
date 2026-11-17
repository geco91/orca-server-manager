"""Disposable Compose pairing checks; never print native credentials or browser URLs."""

import json
import os
import threading
from time import monotonic, sleep
from urllib.parse import urlsplit

from manager.pairing import native_pairing


class PairingWorker:
    """Fixture for the PVE-only queue transport, using the real Orca pairing CLI."""

    def __init__(self, compose, native, origin):
        self.compose, self.native, self.origin = compose, native, origin
        self.stop = threading.Event()
        self.error = False

    def manager(self, script, document=None, user="0:0"):
        return self.compose(
            "exec",
            "-T",
            "--user",
            user,
            "manager",
            "python",
            "-c",
            script,
            input_data=json.dumps(document) if document is not None else None,
        )

    def seed(self):
        self.manager(
            """
import json, os, sys
from pathlib import Path
from manager.control import atomic_document, utc_now
root = Path('/control')
root.mkdir(exist_ok=True)
for name, owner, mode in [('requests',1000,0o700),('results',0,0o755),('pairings',0,0o2710)]:
    path = root/name
    if not path.exists():
        path.mkdir()
        os.chmod(path,mode)
        os.chown(path,owner,1000 if name == 'pairings' else owner)
native = json.load(sys.stdin)
atomic_document(root/'status.json',dict(schema=1,observed_at=utc_now(),runtime=native['runtime'],
    integrations=native['integrations'],deployment=dict(version='1.4.261',generation=1)),mode=0o644)
""",
            self.native,
        )

    def drain(self):
        self.seed()
        jobs = json.loads(
            self.manager(
                """
import json
from pathlib import Path
from manager.control import read_document
print(json.dumps([read_document(p) for p in Path('/control/requests').glob('*.json')]))
""",
                user="1000:1000",
            )
        )
        for job in jobs:
            assert job["action"] == "pair_web"
            payload = native_pairing(
                self.compose(
                    "exec",
                    "-T",
                    "runtime",
                    "orca",
                    "pair",
                    "--address",
                    self.origin.replace("https://", "wss://", 1) + "/orca",
                    "--json",
                ),
                self.origin,
                job["id"],
                1,
            )
            self.manager(
                """
import json, sys
from pathlib import Path
from manager.control import atomic_document
payload = json.load(sys.stdin)
root = Path('/control')
atomic_document(root/'pairings'/(payload['id']+'.json'),payload,mode=0o640)
atomic_document(root/'results'/(payload['id']+'.json'),dict(id=payload['id'],state='completed',
    message='The private native pairing link is ready.'),mode=0o644)
""",
                payload,
            )
            self.manager(
                "import json,sys;from pathlib import Path;"
                "(Path('/control/requests')/(json.load(sys.stdin)+'.json')).unlink()",
                user="1000:1000",
                document=job["id"],
            )

    def run(self):
        try:
            while not self.stop.wait(0.5):
                self.drain()
        except Exception:  # noqa: BLE001 - suppress potentially credential-bearing native errors
            # A native response or URL must not leak through an exception traceback.
            self.error = True


def check_pairing(compose, native, origin, page, post, csrf, password):
    worker = PairingWorker(compose, native, origin)
    worker.seed()
    html = post("/actions/web-pairing", {"csrf_token": csrf("/"), "open": "0"})
    import re

    endpoint = re.search(r'data-status-url="([^"]+)"', html)[1]
    assert "orca://pair" not in html
    worker.drain()
    response = json.loads(page(endpoint))
    assert response["state"] == "ready", "The private pairing endpoint did not become ready"
    assert response["pairing"]["code"] not in page("/api/status")
    assert response["pairing"]["code"] not in compose(
        "exec", "-T", "manager", "cat", "/control/results/" + endpoint.rsplit("/", 1)[1] + ".json"
    )
    if os.environ.get("OSM_BROWSER_QA") != "1":
        return
    thread = threading.Thread(target=worker.run, daemon=True)
    thread.start()
    stage = "start browser"
    failures = []
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as engine:
            browser = engine.chromium.launch(executable_path=os.environ.get("OSM_CHROMIUM") or None)
            context = browser.new_context(ignore_https_errors=True)
            context.on(
                "response",
                lambda response: (
                    failures.append(response.status)
                    if response.status >= 400
                    and urlsplit(response.url).path
                    in {"/actions/web-pairing", "/orca/web-index.html"}
                    else None
                ),
            )
            dashboard = context.new_page()
            stage = "sign in to the disposable manager"
            dashboard.goto(origin + "/login")
            dashboard.locator('[name="password"]').fill(password)
            dashboard.get_by_role("button", name="Sign in", exact=True).click()
            dashboard.wait_for_url(origin + "/")
            stage = "open the prepared native WebUI"
            with dashboard.expect_popup() as opened:
                dashboard.get_by_role(
                    "button", name="Open and connect Orca WebUI", exact=False
                ).click()
            web = opened.value
            stage = "connect through native Orca pairing"
            web.wait_for_url("**/orca/web-index.html*", timeout=60000)
            # Native Orca consumes the fragment and persists its browser identity.
            deadline = monotonic() + 45
            while monotonic() < deadline:
                if (
                    web.locator('input[placeholder="orca://pair?code=..."]').count() == 0
                    and web.locator("body").inner_text().strip()
                    and "#pairing=" not in web.url
                ):
                    break
                sleep(0.25)
            else:
                raise AssertionError()
            stage = "read authenticated runtime status through the paired browser"
            web.wait_for_function("typeof window.api?.runtime?.call === 'function'")
            assert web.evaluate("""async () => {
                try {
                    const result = await window.api.runtime.call({method:'status.get'});
                    return result?.ok === true && typeof result.result === 'object';
                } catch {return false;}
            }""")
            stage = "retain the paired identity after reload"
            web.reload(wait_until="networkidle")
            assert web.locator('input[placeholder="orca://pair?code=..."]').count() == 0
            assert "Connect to Orca" not in web.locator("body").inner_text()
            assert "#pairing=" not in web.url
            web.wait_for_function("typeof window.api?.runtime?.call === 'function'")
            assert web.evaluate("""async () => {
                try {
                    const result = await window.api.runtime.call({method:'status.get'});
                    return result?.ok === true && typeof result.result === 'object';
                } catch {return false;}
            }""")
            browser.close()
            print(
                "PASS: real Chromium opened and paired the original Orca WebUI; authenticated native status RPC passed before and after reload.",
                flush=True,
            )
    except Exception:  # noqa: BLE001 - browser errors may include the private fragment URL
        print("Pairing HTTP error statuses: " + json.dumps(failures), flush=True)
        raise RuntimeError(
            f"Browser pairing check failed at: {stage}. Credentials suppressed."
        ) from None
    finally:
        worker.stop.set()
        thread.join(timeout=40)
        assert not worker.error, "The disposable pairing worker failed (private output suppressed)."
