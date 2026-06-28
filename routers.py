# routers.py
import os
import time
from groq import Groq

# ---------------------------------------------------------------------------
# Groq client — lazy init
# ---------------------------------------------------------------------------
_groq_client = None

def _get_groq():
    global _groq_client
    if _groq_client is None:
        _groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    return _groq_client


# ---------------------------------------------------------------------------
# Expired listing detection
# ---------------------------------------------------------------------------
def _is_expired(page) -> bool:
    """Detects the 'Ansökningstiden har gått ut' heading before any clicks."""
    try:
        if page.locator("h2:has-text('Ansökningstiden har gått ut')").count() > 0:
            return True
        if "Ansökningstiden har gått ut" in page.content():
            return True
    except Exception:
        pass
    return False


# ---------------------------------------------------------------------------
# Extract the real company URL from the Arbetsförmedlingen apply modal.
#
# ROOT CAUSE of the Migrationsverket bug:
#   Scanning ALL <a href> on the page picks up government nav/footer links
#   (migrationsverket.se, skatteverket.se, etc.) that appear BEFORE the modal
#   content in the DOM. The actual application URL is stored as plain text in
#   a <p class="single-line line-break"> element inside the modal — not as an
#   anchor at all. So we target that text node FIRST and only fall back to
#   anchor scanning scoped tightly inside the modal overlay.
# ---------------------------------------------------------------------------
def _extract_real_url(page) -> str | None:
    """
    Returns the real company application URL from the AF modal.
    Never returns a mailto:, arbetsformedlingen.se, or Swedish gov-site URL.
    """

    # Hard-blocked domains — these are never the apply destination
    BLOCKED = [
        "arbetsformedlingen.se",
        "migrationsverket.se",
        "skatteverket.se",
        "forsakringskassan.se",
        "pensionsmyndigheten.se",
        "regeringen.se",
    ]

    def _is_valid(url: str) -> bool:
        return (
                url.startswith("http")
                and "mailto" not in url
                and not any(d in url for d in BLOCKED)
        )

    # ── Strategy 1 (PRIMARY): raw text node inside the modal ────────────────
    # AF renders the URL as visible text in p.single-line.line-break.
    # This is the most reliable signal — it IS the URL, not a nav link.
    text_selectors = [
        "p.single-line.line-break",
        "pbj-application-method p",
        ".application-method p",
        "[class*='application'] p",
    ]
    for sel in text_selectors:
        try:
            el = page.locator(sel).first
            el.wait_for(timeout=2000)
            raw = el.text_content().strip()
            print(f"🔍 URL candidate from text node ({sel}): {raw!r}")
            if _is_valid(raw):
                return raw
        except Exception:
            continue

    # ── Strategy 2 (FALLBACK): anchors SCOPED to the modal overlay only ─────
    # We restrict to the CDK overlay pane so page-wide nav links are excluded.
    modal_scope_selectors = [
        ".cdk-overlay-pane",
        "[role='dialog']",
        "[aria-modal='true']",
        "pbj-application-method",
        ".application-method",
    ]
    for scope_sel in modal_scope_selectors:
        try:
            scope = page.locator(scope_sel).first
            if not scope.is_visible(timeout=800):
                continue
            anchors = scope.locator("a[href^='http']").all()
            for a in anchors:
                href = (a.get_attribute("href") or "").strip()
                print(f"🔍 Anchor candidate inside {scope_sel}: {href!r}")
                if _is_valid(href):
                    return href
        except Exception:
            continue

    print("⚠️ _extract_real_url: no valid URL found in modal.")
    return None


# ---------------------------------------------------------------------------
# Groq fallback oracle — called only when ALL rule-based selectors fail
# ---------------------------------------------------------------------------
_GROQ_SYSTEM = (
    "You are a web automation assistant. "
    "Given a snippet of page HTML, find the single best CSS selector that targets "
    "the PRIMARY job-application button or link (text like 'Apply now', 'Ansök nu', "
    "'Sök tjänsten', 'Apply here', or similar). "
    "Respond with ONLY the CSS selector — no explanation, no markdown. "
    "If none exists, respond with exactly: NONE"
)

def _groq_find_apply_selector(page) -> str | None:
    """
    Groq LLaMA oracle — last resort when rule-based selectors all fail.
    Sends a trimmed HTML snippet, returns a CSS selector string or None.
    """
    print("🤖 Rule-based selectors exhausted — calling Groq oracle...")
    try:
        try:
            snippet = page.locator("main").inner_html(timeout=2000)
        except Exception:
            snippet = page.content()

        snippet = snippet[:6000]  # keep it cheap

        client = _get_groq()
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",   # ← updated model (llama3-70b-8192 is decommissioned)
            messages=[
                {"role": "system", "content": _GROQ_SYSTEM},
                {"role": "user",   "content": f"PAGE HTML:\n{snippet}"},
            ],
            temperature=0,
            max_tokens=80,
        )
        selector = response.choices[0].message.content.strip()
        if not selector or selector.upper() == "NONE":
            print("🤖 Groq: no apply button found on this page.")
            return None
        print(f"🤖 Groq returned selector: {selector!r}")
        return selector
    except Exception as e:
        print(f"⚠️ Groq oracle call failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Internal helper — try a list of selectors, return navigated page or same page
# ---------------------------------------------------------------------------
def _try_selectors(page, context, selectors: list):
    for selector in selectors:
        try:
            locator = page.locator(selector).first
            if not locator.is_visible(timeout=1500):
                continue
            print(f"🔗 Found apply entry point: '{selector}' — clicking...")
            try:
                with context.expect_popup(timeout=3000) as popup_info:
                    locator.click()
                new_page = popup_info.value
                new_page.wait_for_load_state("networkidle")
                return new_page
            except Exception:
                locator.click()
                page.wait_for_load_state("networkidle")
                return page
        except Exception:
            continue
    return page


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def handle_arbetsformedlingen(page, context, job_url):
    """
    Breaks through Arbetsförmedlingen to land on the real company apply page.

    Returns: (page, status_override)
      - status_override is None (keep going) or "expired" (short-circuit).

    ⚠️  IMPORTANT — callers in auto_apply.py must unpack the tuple:
        page, status_override = handle_arbetsformedlingen(page, context, url)
        if status_override == "expired":
            return "expired", "Ansökningstiden har gått ut"
    """
    if "arbetsformedlingen.se" not in job_url:
        return check_for_nested_apply(page, context), None

    print("📍 Breaking through Arbetsförmedlingen middleman page...")

    # ── Check for expired listing BEFORE any click ───────────────────────────
    if _is_expired(page):
        print("⏰ Listing expired (Ansökningstiden har gått ut). Skipping.")
        return page, "expired"

    # ── Open the external-apply modal ────────────────────────────────────────
    modal_opened = False
    try:
        page.get_by_role("button", name="Ansök via extern webbplats").first.click()
        page.wait_for_timeout(2000)   # give Angular enough time to render the modal
        modal_opened = True
    except Exception as e:
        print(f"⚠️ Could not click 'Ansök via extern webbplats': ({e})")

    if modal_opened:
        real_url = _extract_real_url(page)
        if real_url:
            print(f"🔗 Navigating to real site: {real_url}")
            try:
                page.goto(real_url, timeout=30000)
                page.wait_for_load_state("networkidle")
                return check_for_nested_apply(page, context), None
            except Exception as nav_err:
                print(f"⚠️ Navigation to {real_url} failed: {nav_err}")
                # URL found but unreachable — return current page for manual handling
                return page, None
        else:
            print("⚠️ Modal opened but no valid URL found inside it.")

    # ── Popup fallback — AF sometimes opens company site in a new tab ─────────
    try:
        btn = page.locator("button:has-text('Gå vidare till webbplatsen')").first
        if btn.is_visible(timeout=2000):
            try:
                with context.expect_popup(timeout=5000) as popup_info:
                    btn.click()
                new_page = popup_info.value
                new_page.wait_for_load_state("networkidle")
                return check_for_nested_apply(new_page, context), None
            except Exception:
                # No popup — navigated in same tab
                btn.click()
                page.wait_for_load_state("networkidle")
                return check_for_nested_apply(page, context), None
    except Exception as fallback_err:
        print(f"❌ Popup fallback failed: {fallback_err}")

    return page, None

def check_for_nested_apply(page, context, depth=0, max_depth=4):
    """
    LONG-TERM FIX: Recursively drills through middleman pages.
    Instead of fighting UI banners with clicks, it extracts the raw hrefs and teleports directly.
    """
    if not page or depth >= max_depth:
        return page

    # 🛑 GUARD 1: Destination reached check
    try:
        if page.locator("input[type='file'], textarea, input[name*='resume']").count() > 0:
            print("🎯 Destination reached: Active application form detected.")
            return page
    except:
        pass

    initial_url = page.url
    initial_pages_count = len(context.pages)

    # 🛠️ SPECIFIC STRUCTURAL & TEXT SELECTORS
    transition_selectors = [
        "a[href*='positionquick']",
        "a[href*='/apply/']",
        "a[href*='apply-gate']",
        ".btn-apply",
        ".apply-button",
        "a:has-text('Sök jobbet')",
        "a:has-text('Ansök här')",
        "a:has-text('Ansök nu')",
        "a:has-text('Apply now')",
        "button:has-text('Ansök')",
        "button:has-text('Apply')",
        "a:has-text('Gå till ansökan')",
        "a[href*='successfactors']"
    ]

    # 🛡️ THE BLACKLIST
    login_blacklist = [
        "logga in", "login", "sign in", "skapa konto",
        "register", "mitt konto", "my account", "connect"
    ]

    # --- Phase 1: Fast Rule-Based Matching ---
    for selector in transition_selectors:
        try:
            elements = page.locator(selector).all()
            for element in elements:
                if not element.is_visible(timeout=500):
                    continue

                text_content = (element.inner_text() or "").lower()
                raw_href = element.get_attribute("href")
                href_lower = (raw_href or "").lower()

                if any(bad_word in text_content or bad_word in href_lower for bad_word in login_blacklist):
                    continue

                print(f"🔗 [Layer {depth + 1}] Target matched: '{selector}' ('{text_content.strip()}').")

                # 🚀 THE SILVER BULLET: Bypass UI completely and route directly via URL
                if raw_href and not raw_href.startswith("#") and "javascript" not in href_lower:
                    from urllib.parse import urljoin
                    full_url = urljoin(page.url, raw_href)
                    print(f"⚡ Bypassing UI click — Teleporting directly to: {full_url}")

                    try:
                        page.goto(full_url, timeout=15000)
                        page.wait_for_load_state("domcontentloaded")
                        return check_for_nested_apply(page, context, depth + 1, max_depth)
                    except Exception as e:
                        print(f"⚠️ Direct route failed: {e}. Falling back to DOM click...")

                # Standard Click Fallback (For button tags, SPAs, and weird JS overlays)
                next_page = None
                try:
                    with context.expect_popup(timeout=3000) as popup_info:
                        element.click(force=True) # force=True ignores sticky cookie banners blocking the element
                    next_page = popup_info.value
                except Exception:
                    if len(context.pages) > initial_pages_count:
                        next_page = context.pages[-1]
                    else:
                        next_page = page

                next_page.wait_for_load_state("domcontentloaded", timeout=4000)

                # Give inline SPAs a second to render the form before recursing
                if next_page == page and page.url == initial_url:
                    page.wait_for_timeout(1500)

                # Always recurse. If it's a dead end, depth limit (max_depth=4) safely kills it.
                return check_for_nested_apply(next_page, context, depth + 1, max_depth)
        except Exception:
            continue

    # --- Phase 2: Groq AI Oracle Fallback ---
    print(f"🤖 Fast rules exhausted on Layer {depth + 1}. Letting Groq AI scan the DOM...")

    # We still keep the AI oracle you built as the absolute last resort
    ai_selector = _groq_find_apply_selector(page)
    if ai_selector:
        try:
            ai_element = page.locator(ai_selector).first
            if ai_element.is_visible(timeout=2000):
                print(f"🧠 [Layer {depth + 1}] AI successfully locked onto target: '{ai_selector}'. Clicking...")

                next_page = None
                try:
                    with context.expect_popup(timeout=3000) as popup_info:
                        ai_element.click(force=True)
                    next_page = popup_info.value
                except Exception:
                    if len(context.pages) > initial_pages_count:
                        next_page = context.pages[-1]
                    else:
                        next_page = page

                next_page.wait_for_load_state("domcontentloaded", timeout=4000)

                if next_page == page and page.url == initial_url:
                    page.wait_for_timeout(1500)

                return check_for_nested_apply(next_page, context, depth + 1, max_depth)
        except Exception as e:
            print(f"⚠️ AI locator misfire: {e}")

    # If everything fails, we assume this is the final form context
    return page