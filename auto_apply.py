# auto_apply.py
import json
import os
from playwright.sync_api import sync_playwright
# Import your router function here!
from routers import handle_arbetsformedlingen

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(BASE_DIR, 'my_info.json'), 'r', encoding='utf-8') as file:
    me = json.load(file)

def fill_field_by_aliases(page, labels, value):
    if not value: return
    for label in labels:
        try:
            locator = page.get_by_label(label, exact=False)
            if locator.is_visible(timeout=500):
                locator.fill(value)
                print(f"✓ Filled field: '{label}'")
                return 
        except Exception: continue

def apply_to_job(job_url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        
        print(f"Navigating to: {job_url}")
        page.goto(job_url)
        page.wait_for_load_state("networkidle")
        
        # --- ROUTER ZONE ---
        # Pass the page into the router, and get the target page back
        page = handle_arbetsformedlingen(page, context, job_url)

        # --- BILINGUAL FILLING ZONE ---
        print("\nFilling out text fields...")
        fill_field_by_aliases(page, ["First name", "First Name", "Förnamn"], me.get('first_name'))
        fill_field_by_aliases(page, ["Last name", "Last Name", "Efternamn"], me.get('last_name'))
        fill_field_by_aliases(page, ["Email", "E-post", "E-postadress"], me.get('email'))
        fill_field_by_aliases(page, ["Phone", "Mobile", "Telefon", "Telefonnummer", "Mobilnummer"], me.get('phone'))
        fill_field_by_aliases(page, ["Title", "Role", "Titel", "Roll", "Titel/roll"], me.get('title'))
        fill_field_by_aliases(page, ["Organization", "Company", "Organisation", "Företag"], me.get('organization'))
        fill_field_by_aliases(page, ["LinkedIn", "LinkedIn URL", "Linkedin-profil"], me.get('linkedin'))
        fill_field_by_aliases(page, ["Portfolio", "Website", "Hemsida", "Webbplats", "URL"], me.get('portfolio'))

        # --- UPLOAD FILES ---
        print("\nUploading documents...")
        abs_cv_path = os.path.join(BASE_DIR, me['cv_path'])
        try:
            page.locator('input[type="file"]').first.set_input_files(abs_cv_path)
            print("✓ CV attached successfully.")
        except Exception: print("❌ Could not attach CV automatically.")

        # --- CHECKBOX & SUBMIT LOGIC ---
        print("\nHandling consent and submission...")
        try:
            page.get_by_text("Jag samtycker", exact=True).click()
        except Exception:
            try: page.locator("#pul").check(force=True)
            except Exception: pass

        try: page.get_by_role("button", name="Skicka").click()
        except Exception: pass

        print("\n🎉 Action sequence complete!")
        input("Press Enter in the terminal to close the session...")
        browser.close()

if __name__ == "__main__":
    af_link = "https://arbetsformedlingen.se/platsbanken/annonser/31030325"
    apply_to_job(af_link)