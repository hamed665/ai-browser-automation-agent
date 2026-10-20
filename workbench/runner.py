"""Fresh browser, no credentials and only a local synthetic fixture."""

from playwright.async_api import async_playwright


async def run_task(task, directory, origin):
    target = origin + "/demo-fixture"
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        try:
            context = await browser.new_context(java_script_enabled=False, accept_downloads=False)

            async def route(request):
                if request.request.url == target:
                    await request.continue_()
                else:
                    await request.abort()

            await context.route("**/*", route)
            page = await context.new_page()
            await page.goto(target, wait_until="domcontentloaded", timeout=10000)
            result = {"title": await page.title(), "heading": await page.locator("h1").inner_text()}
            if task["spec"]["action"] == "screenshot":
                await page.screenshot(path=str(directory / (task["id"] + ".png")))
                result["screenshot"] = True
            return result
        finally:
            await browser.close()
