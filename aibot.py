from playwright.sync_api import sync_playwright
import sys
import time

STATE_FILE = "gemini_state.json"

#with sync_playwright() as p:
#    browser = p.chromium.launch(
#        headless=False,
#        args=["--disable-blink-features=AutomationControlled"]
#    )
#    context = browser.new_context(
#        viewport={"width": 1280, "height": 800}
#    )
#    page = context.new_page()
#    page.goto("https://gemini.google.com/app")
#
#    print("Log into your Google account in the browser window.")
#    input("Once the Gemini chat input box is visible, press ENTER here to save cookies...")
#
#    context.storage_state(path=STATE_FILE)
#    print(f"Session saved to {STATE_FILE}")
#    browser.close()

def ask_gemini(prompt: str) -> str:
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = browser.new_context(storage_state=STATE_FILE)
        page = context.new_page()

        # Block heavy media/fonts to speed up headless load
        page.route("**/*.{png,jpg,jpeg,gif,webp,svg,woff,woff2}", lambda route: route.abort())

        page.goto("https://gemini.google.com/app", wait_until="domcontentloaded")

        # 1. Wait for the rich-text prompt editor
        editor = page.locator('div[contenteditable="true"]').first
        editor.wait_for(state="visible", timeout=30000)

        # Count existing responses before sending (useful if continuing a thread)
        responses = page.locator("message-content")
        initial_count = responses.count()

        # 2. Type prompt and submit
        editor.fill(prompt)
        page.keyboard.press("Enter")
        time.sleep(10)
        # 3. Wait for a new response container to appear
        try:
            page.wait_for_function(f"document.querySelectorAll('message-content').length > {initial_count}", timeout=30000)
        except Exception:
            page.screenshot(path="gemini_debug.png")
            print("URL:", page.url, file=sys.stderr)
            raise
        # 4. Wait until generation finishes:
        # While streaming, Gemini shows a "Stop response" button or aria-busy state.
        # Stabilization check: poll the last message text until it stops changing.
        last_response = responses.last
        previous_text = ""
        stable_checks = 0

        while stable_checks < 3:
            time.sleep(1)
            current_text = last_response.inner_text().strip()
            if current_text and current_text == previous_text:
                stable_checks += 1
            else:
                previous_text = current_text
                stable_checks = 0

        # Refresh stored cookies in case Google rotated session tokens
        context.storage_state(path=STATE_FILE)
        browser.close()
        return previous_text

if __name__ == "__main__":
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
    elif not sys.stdin.isatty():
        query = sys.stdin.read().strip()
    else:
        print("Usage: gemini_web.py 'your prompt'  OR  echo 'prompt' | gemini_web.py", file=sys.stderr)
        sys.exit(1)

    raw_answer = ask_gemini(query)
    answer = str(raw_answer.text).replace('"', '`').replace("'", '`')
