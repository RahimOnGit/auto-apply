# auto_apply.py
import json
import os
import re
import webbrowser
import urllib.parse
from playwright.sync_api import sync_playwright
from routers import handle_arbetsformedlingen
from tracker import record_job

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- LOAD .ENV FILE MANUALLY ---
ENV_PATH = os.path.join(BASE_DIR, '.env')
if os.path.exists(ENV_PATH):
    with open(ENV_PATH, 'r', encoding='utf-8') as f:
        for line in f:
            if '=' in line and not line.strip().startswith('#'):
                key, value = line.strip().split('=', 1)
                os.environ[key.strip()] = value.strip()

# Load profile configuration
with open(os.path.join(BASE_DIR, 'my_info.json'), 'r', encoding='utf-8') as file:
    me = json.load(file)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

def ask_groq_ai(question_context):
    """Sends form questions to Groq's cloud using LLaMA 3"""
    if not GROQ_API_KEY:
        print("⚠️ No GROQ_API_KEY found in .env. Falling back to default 'yes'.")
        return "yes"

    try:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)

        prompt = f"""
        You are an AI managing a job application form for Abdelrahim Elhaj.
        User Background: Fullstack Developer student. Finished an internship at FBK Balkan building web apps with Spring Boot, React, and TypeScript. Speaks Swedish (professional/working proficiency) and English.
        
        Form Question Found on Page: "{question_context}"
        
        Task: If this is a Yes/No type question, reply with exactly 'yes' or 'no'. Otherwise, give a brief, accurate response based on his background. Reply with ONLY the answer.
        """

        # HERE IS THE MODEL RUNNING ON GROQ'S CLOUD
        completion = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=20
        )
        response = completion.choices[0].message.content.strip().lower()
        print(f"🤖 Groq AI analyzed question and decided: '{response}'")
        return response
    except Exception as e:
        print(f"⚠️ Groq AI encountered an error: {e}")
        return "yes"

def handle_custom_questions(page):
    """Scans the page for tricky screening questions (like language checks)"""
    print("🧠 Scanning for custom screening questions...")
    try:
        lang_context = page.locator("body").inner_text()
        if "talar du svenska" in lang_context.lower() or "språk" in lang_context.lower():
            ai_decision = ask_groq_ai("Talar du svenska på en professionell nivå? (motsvarande C1 eller högre)")

            if ai_decision == "yes":
                for target_label in ["Ja", "Yes", "Stämmer", "True"]:
                    radio = page.get_by_label(target_label, exact=False).first
                    if radio.is_visible(timeout=500):
                        radio.check(force=True)
                        print(f"✓ Checked radio option: '{target_label}'")
                        return
    except Exception as e:
        print(f"⚠️ Screening question check skipped: {e}")

def handle_email_application(page, job_title):
    try:
        page_text = page.inner_text("body").lower()
        mail_links = page.locator('a[href^="mailto:"]').all()
        for link in mail_links:
            if not link.is_visible(timeout=500): continue
            parent_text = link.locator("..").inner_text().lower()
            email = link.get_attribute('href').replace('mailto:', '').strip()

            if any(kw in parent_text for kw in ["maila", "e-post", "skicka", "email"]) or "ansök" in link.inner_text().lower():
                print(f"📧 EMAIL APPLICATION DETECTED → {email}")
                send_email(page, email, job_title)
                return "email_opened"

        mail_match = re.search(r'ansök via mail:?\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', page_text, re.IGNORECASE)
        if mail_match:
            email = mail_match.group(1)
            print(f"📧 EMAIL APPLICATION DETECTED → {email}")
            send_email(page, email, job_title)
            return "email_opened"
        return None
    except Exception:
        return None

def send_email(page, email, job_title):
    desc_text = page.inner_text("body").lower()
    is_english = any(word in desc_text for word in ["english", "developer", "application"])
    cover_letter = me.get('cover_letter_english') if is_english else me.get('cover_letter_swedish')
    subject = f"Application for {job_title}" if is_english else f"Ansökan: {job_title}"
    mailto_link = f"mailto:{email}?subject={urllib.parse.quote(subject)}&body={urllib.parse.quote(cover_letter)}"
    webbrowser.open(mailto_link)

def fill_field_by_aliases(page, labels, value):
    if not value: return
    for label in labels:
        try:
            locator = page.get_by_label(label, exact=False).first
            if locator.is_visible(timeout=500):
                locator.fill(value)
                print(f"✓ Filled field: '{label}'")
                return
        except: continue

def apply_to_job(job_url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        print(f"🌐 Navigating to: {job_url}")
        try:
            page.goto(job_url, timeout=45000)
            page.wait_for_load_state("networkidle")
        except Exception as e:
            browser.close()
            return "failed", f"Navigation timeout: {str(e)}"

        # 1. Email Check
        email_status = handle_email_application(page, job_title=job_url.split('/')[-1] or "Fullstack Developer")
        if email_status:
            user_choice = input("👉 ENTER = Mark Applied & Continue | q = Quit: ")
            browser.close()
            return "applied", "Handled via automated email client generation."

        # 2. Run through router (Handles Arbetsförmedlingen AND the nested SuccessFactors/Apply buttons)
        page = handle_arbetsformedlingen(page, context, job_url)

        # 3. Security Check (Isolating the form content to prevent header false positives)
        form_body = page.locator("form, main, #content").inner_text().lower() if page.locator("form").count() > 0 else page.content().lower()
        if any(x in form_body for x in ["mobilt bankid", "e-legitimation"]):
            print("\n⚠️ BankID signature portal detected. Awaiting manual authentication!")
            input("👉 Complete BankID manually in the browser window, then press ENTER here to let the script finish...")

        print("\n🖊️ Filling profile info...")
        fill_field_by_aliases(page, ["First name", "First Name", "Förnamn", "Tilltalsnamn"], me.get('first_name'))
        fill_field_by_aliases(page, ["Last name", "Last Name", "Efternamn"], me.get('last_name'))
        fill_field_by_aliases(page, ["Email", "E-post", "E-postadress"], me.get('email'))
        fill_field_by_aliases(page, ["Phone", "Mobile", "Telefon", "Telefonnummer"], me.get('phone'))
        fill_field_by_aliases(page, ["Title", "Role", "Titel"], me.get('title'))

        # Run the Groq AI checker for screening questions
        handle_custom_questions(page)

        # Smart Document Uploading
        try:
            text_context = page.inner_text("body").lower()
            is_eng = any(x in text_context for x in ["apply now", "resume", "english"])
            files = {
                "cv": "cv-fullstack.pdf" if is_eng else "new-cv-fullstack-svenska.pdf",
                "cl": "Cover-Letter.pdf" if is_eng else "personligt-brev.pdf"
            }
            file_inputs = page.locator('input[type="file"]')
            if file_inputs.count() > 0:
                file_inputs.first.set_input_files(os.path.join(BASE_DIR, files["cv"]))
                print(f"✓ Attached: {files['cv']}")
                if file_inputs.count() > 1:
                    file_inputs.nth(1).set_input_files(os.path.join(BASE_DIR, files["cl"]))
                    print(f"✓ Attached: {files['cl']}")
        except:
            print("⚠️ File upload input skipped.")

        print("\n📋 Validation processing...")
        try: page.get_by_text("Jag samtycker").click(timeout=1000)
        except: pass

        # Submit Strategy
        submit_selectors = ["button:has-text('Ansök')", "button:has-text('Apply')", "button:has-text('Submit')", "input[type='submit']"]
        for selector in submit_selectors:
            try:
                btn = page.locator(selector).first
                if btn.is_visible(timeout=1000):
                    btn.dispatch_event("click")
                    print(f"🚀 Clicked submission button: {selector}")
                    break
            except: continue

        user_choice = input("👉 ENTER = Mark Applied & Continue | s = Skip tracking | q = Quit: ")
        browser.close()

        if user_choice.lower() == 's':
            return "skipped", "User manually skipped recording this job."
        elif user_choice.lower() == 'q':
            return "quit", "Session stopped by user."

        return "applied", "Successfully completed submission logic."

if __name__ == "__main__":
    # If you run auto_apply.py directly, it will test this link!
    print("Executing standalone single-job test...")
    apply_to_job("https://arbetsformedlingen.se/platsbanken/annonser/29037463")