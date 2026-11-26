"""Run against a locally started server: python tests/browser_smoke.py."""
import os
from pathlib import Path

from playwright.sync_api import sync_playwright, expect

url = os.environ.get("MARKETPULSE_URL","http://127.0.0.1:8000")
with sync_playwright() as p:
    options = {"executable_path": os.environ["CHROMIUM_PATH"]} if os.environ.get("CHROMIUM_PATH") else {}
    browser=p.chromium.launch(headless=True,**options)
    for width,height in ((1440,1000),(390,844)):
        page=browser.new_page(viewport={"width":width,"height":height})
        errors=[]
        page.on("pageerror",lambda err: errors.append(str(err)))
        page.goto(url,wait_until="networkidle")
        expect(page.locator("#gate")).to_have_text("PASS")
        expect(page.locator("#model")).to_have_text("ridge regularized")
        expect(page.locator("#chart polyline")).to_have_count(3)
        expect(page.locator("#models tr")).to_have_count(3)
        page.select_option("#range","30")
        expect(page.locator("#chart polyline").first).to_have_attribute("points",__import__("re").compile(r"^.+$"))
        assert len(page.locator("#chart polyline").first.get_attribute("points").split())==30
        assert page.locator("#error").is_hidden(), "Dashboard error"
        assert not errors,errors
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "Horizontal overflow"
        if os.environ.get("SCREENSHOT_DIR"):
            Path(os.environ["SCREENSHOT_DIR"]).mkdir(parents=True,exist_ok=True)
            page.screenshot(path=str(Path(os.environ["SCREENSHOT_DIR"])/f"dashboard-{width}.png"),full_page=True)
        print(f"PASS: {width}px dashboard, chart filter, data and bounds")
        page.close()
    browser.close()
