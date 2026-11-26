"""Real Chromium checks, run against a fresh synthetic demo server."""
import argparse
import os
from pathlib import Path
from playwright.sync_api import sync_playwright, expect


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--screenshot", type=Path)
    parser.add_argument("--mobile-screenshot", type=Path)
    args = parser.parse_args()
    errors = []
    with sync_playwright() as playwright:
        executable = os.environ.get("CHROMIUM_EXECUTABLE")
        browser = playwright.chromium.launch(headless=True, executable_path=executable)
        page = browser.new_page(viewport={"width":1440,"height":1000}, device_scale_factor=1)
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(args.url)
        expect(page.locator("#status")).to_contain_text("5,000 sale lines")
        expect(page.locator("#health")).to_have_text("Warehouse ready")
        expect(page.locator("#quality-status")).to_have_text("All checks passed")
        expect(page.locator("#checks .check")).to_have_count(10)
        expect(page.locator("#trend .trend-col")).to_have_count(24)
        expect(page.locator("#kpis .kpi")).to_have_count(8)
        if args.screenshot:
            args.screenshot.parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=args.screenshot)
        page.locator("#category").select_option("Bedroom")
        page.locator("#apply").click()
        expect(page.locator("#status")).not_to_contain_text("5,000 sale lines")
        expect(page.locator("#status")).to_contain_text("sale lines")
        expect(page.locator("#categories .bar-label")).to_have_count(1)
        expect(page.locator("#categories .bar-label")).to_contain_text("Bedroom")
        page.locator("#start").fill("2025-05-01")
        page.locator("#end").fill("2024-05-01")
        page.locator("#apply").click()
        expect(page.locator("#status")).to_contain_text("Unable to refresh")
        page.locator("#reset").click()
        expect(page.locator("#status")).to_contain_text("5,000 sale lines")
        page.locator("#start").fill("2026-01-01")
        page.locator("#apply").click()
        expect(page.locator("#status")).to_contain_text("0 sale lines")
        expect(page.locator("#months")).to_contain_text("No matching data")
        page.locator("#reset").click()
        expect(page.locator("#status")).to_contain_text("5,000 sale lines")
        page.goto(args.url+"/docs")
        expect(page.get_by_text("Furniture Sales Intelligence", exact=True)).to_be_visible()
        mobile = browser.new_page(viewport={"width":390,"height":844}, device_scale_factor=1, is_mobile=True, has_touch=True)
        mobile.on("pageerror", lambda error: errors.append(str(error)))
        mobile.goto(args.url)
        expect(mobile.locator("#status")).to_contain_text("5,000 sale lines")
        assert mobile.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "mobile layout overflow"
        if args.mobile_screenshot:
            args.mobile_screenshot.parent.mkdir(parents=True, exist_ok=True)
            mobile.screenshot(path=args.mobile_screenshot)
        browser.close()
    assert not errors, errors
    print("Browser smoke passed: initial report, quality, category filter, invalid range, empty state, reset, OpenAPI, and mobile layout.")


if __name__ == "__main__":
    main()
