# routers.py
import time

def handle_arbetsformedlingen(page, context, job_url):
    """Breaks through Arbetsförmedlingen to land on the actual company page."""
    if "arbetsformedlingen.se" not in job_url:
        return check_for_nested_apply(page, context)

    print("📍 Breaking through Arbetsförmedlingen middleman page...")
    try:
        page.get_by_role("button", name="Ansök via extern webbplats").first.click()

        link_element = page.locator("p.single-line.line-break").first
        link_element.wait_for(timeout=3000)
        real_url = link_element.text_content().strip()

        if real_url.startswith("http"):
            print(f"🔗 Going directly to real site: {real_url}")
            page.goto(real_url)
            page.wait_for_load_state("networkidle")
            return check_for_nested_apply(page, context) # Run nested check on the new page!

    except Exception as e:
        print(f"⚠️ Direct extraction timed out, attempting click fallback... ({e})")

    try:
        with context.expect_popup() as popup_info:
            page.locator("button:has-text('Gå vidare till webbplatsen')").first.click()
        new_page = popup_info.value
        new_page.wait_for_load_state("networkidle")
        return check_for_nested_apply(new_page, context) # Run nested check on the popup page!
    except Exception as fallback_err:
        print(f"❌ Navigation fallback failed: {fallback_err}")
        return page

def check_for_nested_apply(page, context):
    """TARGETS THE NESTED BUTTONS (SuccessFactors, Workday, etc.)"""
    nested_selectors = [
        "a:has-text('Apply now')",
        "a:has-text('Ansök nu')",
        "button:has-text('Apply now')",
        "a.b_cta--button", # Targets your exact SuccessFactors tag class
        "a[href*='successfactors.eu']" # Target by domain pattern if needed
    ]

    for selector in nested_selectors:
        try:
            locator = page.locator(selector).first
            if locator.is_visible(timeout=1500):
                print(f"🔗 Found nested transition button: '{selector}'. Clicking through...")
                try:
                    # If it opens a popup tab, follow it
                    with context.expect_popup(timeout=3000) as popup_info:
                        locator.click()
                    new_page = popup_info.value
                    new_page.wait_for_load_state("networkidle")
                    return new_page
                except:
                    # If it loads on the same page, stay on it
                    locator.click()
                    page.wait_for_load_state("networkidle")
                    return page
        except:
            continue
    return page