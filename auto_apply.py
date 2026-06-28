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

def ask_groq_ai(question_context, context_type="essay", options=None):
    """Uses Groq LLaMA 3 to answer dynamic text scenarios or radio choice prompts."""
    if not GROQ_API_KEY:
        return "yes" if context_type == "radio" else "Please contact me for details."

    try:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)

        # Core background injected directly into the prompt profile
        profile_backstory = """
        You are an AI assistant representing Abdelrahim Elhaj for a job application form field.
        Profile: Fullstack Developer student at Teknikhögskolan living in Malmö, Sweden.
        Skills: Java (Spring Boot), Spring Security, React, TypeScript, SQL, PostgreSQL, SQLite, Git, Agile/Scrum.
        Experience: Served as Scrum Master and Backend Engineer on a Youth Portal application for the football club FBK Balkan.
        Built automated data sync structures pulling real-time statistics from the Swedish Football Association (SvFF) API.
        Eligibility: Fully eligible to work in Sweden (lives locally in Malmö).
        Language Proficiency: Professional working competency in Swedish; fluent in English.
        
        A technical challenge story you can use if asked about bugs:
        "While building the FBK Balkan match synchronization engine using the SvFF API, an asynchronous scheduler lacked 
        proper transactional boundaries (@Transactional). Under API latency spikes, this caused PostgreSQL connection pool 
        saturation and left orphan tracking records. I analyzed the Hibernate connection logs, found the rollback leak, 
        and resolved it by optimizing batch scopes and configuring explicit pool execution timeouts."
        """

        if context_type == "radio":
            prompt = f"""
            {profile_backstory}
            
            Question asked on form: "{question_context}"
            Available options to select from: {options}
            
            Task: Which specific option from the list fits his background best?
            Respond with ONLY the exact string or text of the best option from the list. Do not explain your choice.
            """
        else:
            prompt = f"""
            {profile_backstory}
            
            Question asked on form: "{question_context}"
            
            Task: Write a professional, concise, short answer (1-3 sentences maximum) for this textbox field representing his background accurately. 
            Write the response in the same language as the question (Swedish or English). Do not include quotes.
            """

        completion = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=1500
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        print(f"⚠️ Groq inference anomaly: {e}")
        return "Yes" if context_type == "radio" else "See attached CV."


def handle_custom_questions(page):
    """Scans for and completely fills out dynamic textareas and multiple-choice radio fields on the fly."""
    print("🧠 Scanning for dynamic form fields and custom questions...")

    # === PART A: RESOLVE ESSAY & SHORT TEXT FIELDS ===
    try:
        # Catch textareas and long text inputs
        text_fields = page.locator("textarea, input[type='text']").all()
        for field in text_fields:
            # Skip if the field is hidden, disabled, or already has an autofilled value
            if not field.is_visible() or field.is_disabled() or field.input_value():
                continue

            # Skip standard profile tracking fields to avoid messing up contact info
            field_name = (field.get_attribute("name") or "").lower()
            field_id = (field.get_attribute("id") or "").lower()
            if any(x in field_name or x in field_id for x in ["name", "email", "phone", "mobil", "epost", "password", "title", "titel"]):
                continue

            # Extract the closest question label text for this element
            question_text = ""
            if field_id:
                label_loc = page.locator(f"label[for='{field_id}']")
                if label_loc.count() > 0:
                    question_text = label_loc.first.inner_text()

            if not question_text:
                # Fallback: scan closest container tag text blocks
                question_text = field.evaluate("""el => {
                    let container = el.closest('.form-group, .form-row, div[class*="field"], label');
                    return container ? container.innerText : '';
                }""")

            # If we found a question, let Groq fill it
            if question_text and len(question_text.strip()) > 5:
                clean_question = question_text.split('\n')[0].strip() # target first header line
                print(f"❓ Found text question: '{clean_question}'")
                ai_answer = ask_groq_ai(clean_question, context_type="essay")
                field.fill(ai_answer)
                print(f"✓ AI filled answer text layout.")
    except Exception as e:
        print(f"⚠️ Text field handling loop anomaly: {e}")

    # === PART B: RESOLVE DYNAMIC RADIO BUTTONS ===
    try:
        radios = page.locator("input[type='radio']").all()
        # Group individual radios by their shared 'name' attribute
        radio_groups = {}
        for r in radios:
            name = r.get_attribute("name")
            if name:
                radio_groups.setdefault(name, []).append(r)

        for name, elements in radio_groups.items():
            # Skip group entirely if you already selected something manually or automatically
            if any(el.is_checked() for el in elements):
                continue

            # Grab the parent block inner text to read the main question context heading
            first_radio = elements[0]
            group_context = first_radio.evaluate("""el => {
                let container = el.closest('fieldset, .form-group, .form-row, div[class*="question"], div[class*="block"]');
                if (!container) container = el.parentElement.parentElement;
                return container ? container.innerText : '';
            }""")

            if group_context:
                # Scrape the specific labels for the options in this specific radio group
                options_map = []
                for el in elements:
                    rad_id = el.get_attribute("id")
                    opt_label = ""
                    if rad_id:
                        lbl = page.locator(f"label[for='{rad_id}']")
                        if lbl.count() > 0:
                            opt_label = lbl.first.inner_text()
                    if not opt_label:
                        opt_label = el.evaluate("el => el.parentElement.innerText")
                    options_map.append({"element": el, "text": opt_label.strip()})

                # Clean question header extraction
                clean_question = group_context.split('\n')[0].strip()
                just_options_text = [opt["text"] for opt in options_map if opt["text"]]

                if just_options_text:
                    print(f"❓ Found radio question: '{clean_question}' with options {just_options_text}")
                    ai_choice = ask_groq_ai(clean_question, context_type="radio", options=just_options_text)

                    # Target and click the specific radio button matching Groq's text selection
                    for opt in options_map:
                        if ai_choice.lower() in opt["text"].lower() or opt["text"].lower() in ai_choice.lower():
                            opt["element"].check(force=True)
                            print(f"✓ AI selected choice option: '{opt['text']}'")
                            break
    except Exception as e:
        print(f"⚠️ Radio field selection loop anomaly: {e}")

def handle_email_application(page, job_title):
    """
    Detects email-only application pages and opens a pre-filled mailto: link.
    NOTE: This must be called AFTER routing so it runs on the real company page,
    not on the Arbetsförmedlingen listing (which often has contact emails in the
    sidebar that are NOT the application address).
    """
    try:
        page_text = page.inner_text("body").lower()
        mail_links = page.locator('a[href^="mailto:"]').all()
        for link in mail_links:
            if not link.is_visible(timeout=500):
                continue
            parent_text = link.locator("..").inner_text().lower()
            email = link.get_attribute('href').replace('mailto:', '').strip()

            if any(kw in parent_text for kw in ["maila", "e-post", "skicka", "email"]) or "ansök" in link.inner_text().lower():
                print(f"📧 EMAIL APPLICATION DETECTED → {email}")
                send_email(page, email, job_title)
                return "email_opened"

        mail_match = re.search(
            r'ansök via mail:?\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
            page_text, re.IGNORECASE
        )
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

def apply_to_job(job_url):                          # ← parameter is job_url throughout
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

        # ── Step 1: Route through Arbetsförmedlingen / nested ATS ────────────
        # FIX: was passing undefined `url` — now correctly passes `job_url`.
        # FIX: unpack tuple — handle_arbetsformedlingen returns (page, status_override).
        page, status_override = handle_arbetsformedlingen(page, context, job_url)
        if status_override == "expired":
            browser.close()
            return "expired", "Ansökningstiden har gått ut"

        # ── Step 2: Email check — runs on the REAL company page now ──────────
        # FIX: moved AFTER routing so AF sidebar contact emails don't trigger
        # false positives before we even reach the actual application page.
        job_title = job_url.split('/')[-1] or "Fullstack Developer"
        email_status = handle_email_application(page, job_title=job_title)
        if email_status:
            user_choice = input("👉 ENTER = Mark Applied & Continue | q = Quit: ")
            browser.close()
            if user_choice.lower() == 'q':
                return "quit", "Session stopped by user."
            return "applied", "Handled via automated email client generation."

        # ── Step 3: BankID / authentication detection ────────────────────────
        try:
            form_body = (
                page.locator("form, main, #content").inner_text().lower()
                if page.locator("form").count() > 0
                else page.content().lower()
            )
        except Exception:
            form_body = ""

        if any(x in form_body for x in ["mobilt bankid", "e-legitimation"]):
            print("\n⚠️ BankID signature portal detected. Awaiting manual authentication!")
            input("👉 Complete BankID manually in the browser window, then press ENTER here...")

        # ── Step 4: Fill profile fields ──────────────────────────────────────
        print("\n🖊️ Filling profile info...")
        fill_field_by_aliases(page, ["First name", "First Name", "Förnamn", "Tilltalsnamn"], me.get('first_name'))
        fill_field_by_aliases(page, ["Last name", "Last Name", "Efternamn"], me.get('last_name'))
        fill_field_by_aliases(page, ["Email", "E-post", "E-postadress"], me.get('email'))
        fill_field_by_aliases(page, ["Phone", "Mobile", "Telefon", "Telefonnummer"], me.get('phone'))
        fill_field_by_aliases(page, ["Title", "Role", "Titel"], me.get('title'))

        # ── Step 5: Groq AI screening questions ──────────────────────────────
        handle_custom_questions(page)

        # ── Step 6: Smart document upload ────────────────────────────────────
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
        except Exception:
            print("⚠️ File upload input skipped.")

        # ── Step 7: Consent checkbox ──────────────────────────────────────────
        print("\n📋 Validation processing...")
        try:
            page.get_by_text("Jag samtycker").click(timeout=1000)
        except Exception:
            pass

        # ── Step 8: Submit ────────────────────────────────────────────────────
        submit_selectors = [
            "button:has-text('Ansök')",
            "button:has-text('Apply')",
            "button:has-text('Submit')",
            "input[type='submit']",
        ]
        for selector in submit_selectors:
            try:
                btn = page.locator(selector).first
                if btn.is_visible(timeout=1000):
                    btn.dispatch_event("click")
                    print(f"🚀 Clicked submission button: {selector}")
                    break
            except Exception:
                continue

        user_choice = input("👉 ENTER = Mark Applied & Continue | s = Skip tracking | q = Quit: ")
        browser.close()

        if user_choice.lower() == 's':
            return "skipped", "User manually skipped recording this job."
        elif user_choice.lower() == 'q':
            return "quit", "Session stopped by user."

        return "applied", "Successfully completed submission logic."

if __name__ == "__main__":
    print("Executing standalone single-job test...")
    apply_to_job("https://arbetsformedlingen.se/platsbanken/annonser/31073897")