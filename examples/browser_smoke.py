"""Real Chromium and HTTP flow, entirely synthetic, produces screenshot evidence."""

import asyncio
import os
import socket
import subprocess
import tempfile
from pathlib import Path

import httpx
from playwright.async_api import async_playwright


async def main():
    output = Path("test-results")
    output.mkdir(exist_ok=True)
    token = "synthetic-browser-smoke-token"
    with tempfile.TemporaryDirectory() as directory:
        environment = dict(
            os.environ,
            WORKBENCH_API_TOKEN=token,
            WORKBENCH_DATA=directory,
            WORKBENCH_BASE_URL="http://127.0.0.1:3188",
        )
        process = subprocess.Popen(  # noqa: ASYNC220 - launch the isolated demo server
            [
                "uv",
                "run",
                "uvicorn",
                "workbench.app:create_app",
                "--factory",
                "--host",
                "127.0.0.1",
                "--port",
                "3188",
            ],
            env=environment,
        )
        try:
            for _ in range(100):
                try:
                    with socket.create_connection(("127.0.0.1", 3188), timeout=0.2):
                        break
                except OSError:
                    if process.poll() is not None:
                        raise RuntimeError("Server exited")
                    await asyncio.sleep(0.1)
            with httpx.Client(
                base_url="http://127.0.0.1:3188",
                trust_env=False,
                headers={"Authorization": "Bearer " + token},
                timeout=30,
            ) as client:
                task = client.post("/api/tasks", json={"action": "screenshot"}).json()
                path = "/api/tasks/" + task["id"]
                assert client.post(path + "/run").status_code == 409
                assert client.post(path + "/approve").status_code == 200
                result = client.post(path + "/run").json()
                assert result["state"] == "succeeded", result
                assert result["result"]["title"] == "Synthetic order desk"
                assert client.post(path + "/run").status_code == 409
                image = client.get(path + "/screenshot")
                assert image.content.startswith(b"\x89PNG")
                (output / "controlled-browser.png").write_bytes(image.content)
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch()
                try:
                    page = await browser.new_page()
                    await page.goto("http://127.0.0.1:3188")
                    await page.get_by_label("Dedicated demo API token").fill(token)
                    await page.get_by_role("button", name="Refresh tasks").click()
                    await page.get_by_role("button", name="View details").click()
                    await page.locator("#image").wait_for(state="visible")
                    # Do not put the demo token into screenshots, even though it is synthetic.
                    await page.get_by_label("Dedicated demo API token").fill("")
                    for width in (320, 1440):
                        await page.set_viewport_size({"width": width, "height": 1000})
                        assert await page.evaluate(
                            "document.documentElement.scrollWidth <= innerWidth"
                        )
                        await page.screenshot(
                            path=str(output / f"workbench-{width}.png"), full_page=True
                        )
                finally:
                    await browser.close()
            print("Real browser flow passed; screenshots saved in test-results/")
        finally:
            process.terminate()
            process.wait(timeout=10)


if __name__ == "__main__":
    asyncio.run(main())
