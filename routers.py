# routers.py
import time

def handle_arbetsformedlingen(page, context, job_url):
    """Navigates through Arbetsförmedlingen to get the real job application page."""
    if "arbetsformedlingen.se" not in job_url:
        return page # Not an AF link, skip

    print("📍 Detected Arbetsförmedlingen link. Breaking through middleman pages...")
    try:
        # 1. Click the first button (bypassing strict mode duplicates)
        page.get_by_role("button", name="Ansök via extern webbplats").first.click()
        
        print("⏳ Modal opened. Extracting target URL directly...")
        
        # 2. Wait for that specific paragraph containing the link to show up
        link_element = page.locator("p.single-line.line-break").first
        link_element.wait_for(timeout=3000) # Give it up to 3 seconds to render
        
        # 3. Read the actual raw string link text
        real_url = link_element.text_content().strip()
        
        if real_url.startswith("http"):
            print(f"🔗 Found it! Navigating straight to: {real_url}")
            page.goto(real_url)
            page.wait_for_load_state("networkidle")
            return page # Return the updated current page
            
    except Exception as e:
        print(f"⚠️ Direct link extraction skipped or timed out: {e}")

    # --- FALLBACK: If the text extraction somehow misses, try the click method ---
    try:
        print("🔄 Trying fallback click method on the web component...")
        with context.expect_popup() as popup_info:
            # We target the actual button element inside the <digi-button> tag
            page.locator("button:has-text('Gå vidare till webbplatsen')").first.click()
        
        new_page = popup_info.value
        new_page.wait_for_load_state("networkidle")
        print(f"🚀 Landed via fallback click context: {new_page.url}")
        return new_page
        
    except Exception as fallback_err:
        print(f"❌ Both routing attempts failed: {fallback_err}")
        return page