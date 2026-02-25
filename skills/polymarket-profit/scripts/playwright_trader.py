#!/usr/bin/env python3
"""Polymarket browser automation trader using Playwright.

Usage:
    python3 playwright_trader.py check                          # Check login state
    python3 playwright_trader.py balance                        # Get balance
    python3 playwright_trader.py buy <market_url> <yes|no> <amount>
    python3 playwright_trader.py positions                      # List positions
    python3 playwright_trader.py sell <market_url> <yes|no> <shares>
    python3 playwright_trader.py login                          # Interactive login (headed)
"""

import sys, os, json, time, argparse
from pathlib import Path
from datetime import datetime

STORAGE_DIR = Path.home() / ".playwright-data" / "polymarket"
STORAGE_STATE = STORAGE_DIR / "state.json"
SCREENSHOTS_DIR = Path(__file__).resolve().parent.parent / "data" / "screenshots"
BASE_URL = "https://polymarket.com"

SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
STORAGE_DIR.mkdir(parents=True, exist_ok=True)


def screenshot(page, name):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = SCREENSHOTS_DIR / f"{name}_{ts}.png"
    page.screenshot(path=str(path), full_page=False)
    print(f"Screenshot: {path}")
    return path


def make_browser(headed=False):
    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start()
    args = ["--disable-blink-features=AutomationControlled"]
    launch_opts = dict(headless=not headed, args=args)
    browser = pw.chromium.launch(**launch_opts)
    ctx_opts = dict(
        viewport={"width": 1280, "height": 800},
        user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    )
    if STORAGE_STATE.exists():
        ctx_opts["storage_state"] = str(STORAGE_STATE)
    ctx = browser.new_context(**ctx_opts)
    ctx.set_default_timeout(30000)
    return pw, browser, ctx


def save_state(ctx):
    ctx.storage_state(path=str(STORAGE_STATE))
    print(f"State saved to {STORAGE_STATE}")


def close_all(pw, browser):
    try:
        browser.close()
    except:
        pass
    try:
        pw.stop()
    except:
        pass


# --- Commands ---

def cmd_login():
    """Open headed browser for manual login, then save state."""
    print("Opening headed browser for manual login...")
    print("Please log in to Polymarket, then press Enter here when done.")
    pw, browser, ctx = make_browser(headed=True)
    page = ctx.new_page()
    page.goto(BASE_URL, wait_until="domcontentloaded")
    input("Press Enter after logging in...")
    save_state(ctx)
    screenshot(page, "login")
    close_all(pw, browser)
    print("Login state saved. You can now use headless commands.")


def cmd_check():
    """Check if login state is valid."""
    if not STORAGE_STATE.exists():
        print("ERROR: No login state found. Run: python3 playwright_trader.py login")
        return False
    pw, browser, ctx = make_browser()
    page = ctx.new_page()
    try:
        page.goto(BASE_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        screenshot(page, "check")
        # Check for logged-in indicators
        # Polymarket shows a portfolio/wallet icon or user avatar when logged in
        # and a "Log In" or "Sign Up" button when not
        content = page.content()
        if "Log In" in page.inner_text("body")[:5000] or "Sign Up" in page.inner_text("body")[:5000]:
            print("NOT LOGGED IN - login state may be expired")
            return False
        else:
            print("LOGGED IN ✓")
            return True
    except Exception as e:
        print(f"Error checking login: {e}")
        screenshot(page, "check_error")
        return False
    finally:
        save_state(ctx)
        close_all(pw, browser)


def cmd_balance():
    """Get portfolio balance from the site."""
    pw, browser, ctx = make_browser()
    page = ctx.new_page()
    try:
        # Go to portfolio page which shows balance
        page.goto(f"{BASE_URL}/portfolio", wait_until="domcontentloaded")
        page.wait_for_timeout(4000)
        screenshot(page, "balance")

        # Try to find balance - Polymarket shows it in the wallet/portfolio area
        # Look for dollar amounts
        body_text = page.inner_text("body")
        print("--- Page text (first 3000 chars) ---")
        print(body_text[:3000])
        print("---")

        # Try to find cash balance specifically
        # Common patterns: "Cash $X.XX" or "Portfolio Value $X.XX"
        import re
        amounts = re.findall(r'\$[\d,]+\.?\d*', body_text)
        if amounts:
            print(f"Found amounts: {amounts}")
        else:
            print("No dollar amounts found on page")

        save_state(ctx)
    except Exception as e:
        print(f"Error: {e}")
        screenshot(page, "balance_error")
    finally:
        close_all(pw, browser)


def cmd_buy(market_url, outcome, amount):
    """Buy an outcome on a market.
    
    NOTE: This may fail if Polymarket requires wallet signature popups
    that can't be handled in headless mode.
    """
    outcome = outcome.lower()
    assert outcome in ("yes", "no"), "Outcome must be 'yes' or 'no'"
    amount = float(amount)
    assert amount > 0, "Amount must be positive"

    pw, browser, ctx = make_browser()
    page = ctx.new_page()
    try:
        print(f"Opening market: {market_url}")
        page.goto(market_url, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        screenshot(page, "buy_1_market")

        # Click Yes or No button
        btn_text = "Yes" if outcome == "yes" else "No"
        print(f"Clicking '{btn_text}'...")
        # Polymarket typically has Yes/No buttons in the trade widget
        # Try multiple selectors
        clicked = False
        for selector in [
            f'button:has-text("{btn_text}")',
            f'div[role="button"]:has-text("{btn_text}")',
            f'text="{btn_text}"',
        ]:
            try:
                el = page.locator(selector).first
                if el.is_visible(timeout=2000):
                    el.click()
                    clicked = True
                    break
            except:
                continue

        if not clicked:
            print(f"WARNING: Could not find '{btn_text}' button")
            screenshot(page, "buy_no_button")
            return False

        page.wait_for_timeout(1000)
        screenshot(page, "buy_2_selected")

        # Find amount input and type
        print(f"Entering amount: ${amount}")
        input_found = False
        for selector in [
            'input[placeholder*="Amount"]',
            'input[type="number"]',
            'input[inputmode="decimal"]',
            'input[placeholder*="0.00"]',
        ]:
            try:
                inp = page.locator(selector).first
                if inp.is_visible(timeout=2000):
                    inp.click()
                    inp.fill(str(amount))
                    input_found = True
                    break
            except:
                continue

        if not input_found:
            print("WARNING: Could not find amount input")
            screenshot(page, "buy_no_input")
            return False

        page.wait_for_timeout(500)
        screenshot(page, "buy_3_amount")

        # Click buy/confirm button
        print("Clicking confirm...")
        confirmed = False
        for selector in [
            'button:has-text("Buy")',
            'button:has-text("Confirm")',
            'button:has-text("Place Order")',
            'button:has-text("Submit")',
        ]:
            try:
                btn = page.locator(selector).first
                if btn.is_visible(timeout=2000) and btn.is_enabled():
                    btn.click()
                    confirmed = True
                    break
            except:
                continue

        if not confirmed:
            print("WARNING: Could not find confirm button")
            screenshot(page, "buy_no_confirm")
            return False

        # Wait for transaction
        page.wait_for_timeout(5000)
        screenshot(page, "buy_4_result")
        print("Buy order submitted. Check screenshot for result.")
        print("⚠️  If a wallet signature popup appeared, the tx may have failed in headless mode.")

        save_state(ctx)
        return True
    except Exception as e:
        print(f"Error during buy: {e}")
        screenshot(page, "buy_error")
        return False
    finally:
        close_all(pw, browser)


def cmd_positions():
    """Get current positions."""
    pw, browser, ctx = make_browser()
    page = ctx.new_page()
    try:
        page.goto(f"{BASE_URL}/portfolio", wait_until="domcontentloaded")
        page.wait_for_timeout(4000)
        screenshot(page, "positions")

        body_text = page.inner_text("body")
        print("--- Portfolio page ---")
        print(body_text[:5000])
        print("---")

        save_state(ctx)
    except Exception as e:
        print(f"Error: {e}")
        screenshot(page, "positions_error")
    finally:
        close_all(pw, browser)


def cmd_sell(market_url, outcome, shares):
    """Sell shares of a position."""
    outcome = outcome.lower()
    assert outcome in ("yes", "no")
    shares = float(shares)

    pw, browser, ctx = make_browser()
    page = ctx.new_page()
    try:
        page.goto(market_url, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        screenshot(page, "sell_1_market")

        # Click on Sell tab if exists
        for selector in ['button:has-text("Sell")', 'text="Sell"']:
            try:
                el = page.locator(selector).first
                if el.is_visible(timeout=2000):
                    el.click()
                    break
            except:
                continue

        page.wait_for_timeout(1000)

        # Select outcome
        btn_text = "Yes" if outcome == "yes" else "No"
        for selector in [f'button:has-text("{btn_text}")', f'text="{btn_text}"']:
            try:
                el = page.locator(selector).first
                if el.is_visible(timeout=2000):
                    el.click()
                    break
            except:
                continue

        page.wait_for_timeout(500)

        # Enter shares
        for selector in ['input[type="number"]', 'input[inputmode="decimal"]', 'input[placeholder*="0"]']:
            try:
                inp = page.locator(selector).first
                if inp.is_visible(timeout=2000):
                    inp.fill(str(shares))
                    break
            except:
                continue

        page.wait_for_timeout(500)
        screenshot(page, "sell_2_amount")

        # Confirm
        for selector in ['button:has-text("Sell")', 'button:has-text("Confirm")', 'button:has-text("Submit")']:
            try:
                btn = page.locator(selector).first
                if btn.is_visible(timeout=2000) and btn.is_enabled():
                    btn.click()
                    break
            except:
                continue

        page.wait_for_timeout(5000)
        screenshot(page, "sell_3_result")
        print("Sell order submitted. Check screenshot.")

        save_state(ctx)
    except Exception as e:
        print(f"Error: {e}")
        screenshot(page, "sell_error")
    finally:
        close_all(pw, browser)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "login":
        cmd_login()
    elif cmd == "check":
        cmd_check()
    elif cmd == "balance":
        cmd_balance()
    elif cmd == "buy":
        if len(sys.argv) != 5:
            print("Usage: python3 playwright_trader.py buy <market_url> <yes|no> <amount>")
            sys.exit(1)
        cmd_buy(sys.argv[2], sys.argv[3], sys.argv[4])
    elif cmd == "positions":
        cmd_positions()
    elif cmd == "sell":
        if len(sys.argv) != 5:
            print("Usage: python3 playwright_trader.py sell <market_url> <yes|no> <shares>")
            sys.exit(1)
        cmd_sell(sys.argv[2], sys.argv[3], sys.argv[4])
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)
