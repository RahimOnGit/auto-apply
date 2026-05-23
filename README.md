# 🚀 Auto Apply
## Smart Job Automator & Mass Applier (AI-Powered)

A modular, highly automated pipeline designed to streamline the job application workflow. This tool manages massive databases of job opportunities, routes cleanly through middleman boards like Arbetsförmedlingen, leverages **Groq AI (LLaMA 3)** to solve dynamic screening questionnaires on the fly, and maintains a strict local history tracker.

## 🛠 Features

* **🧠 Groq AI Core (LLaMA 3):** Automatically evaluates custom screening checkmarks, language checks (e.g., *"Talar du svenska?"*), and dynamic radio fields using cloud-based LLM context mapping based on your professional profile.
* **🔗 Nested Middleman Piercing:** Dynamically scans intermediate landing interfaces (like SuccessFactors, Workday, etc.) to target and click custom "Apply Now" anchors or wrapper popups automatically.
* **💾 Stateful Job Tracker:** Maintains an exact audit trail (`job_history.json`). It records jobs as `applied`, `skipped`, or `failed` (with explicit error codes) so the engine never opens or wastefully processes the same URL twice.
* **📧 Automated Mail Draft Generation:** Identifies pages requesting application via email, evaluates the text context to determine language, and auto-generates a pre-formatted `mailto:` package (Subject + full Body cover letter) directly inside your native operating system mail client.
* **🛡 Targeted Authentication Detection:** Isolates form and body markup areas to prevent global navigation login options from triggering false-positive BankID holds while keeping absolute compliance pauses when authentication is mandatory.

---

## 📁 File Structure

* `mass_apply.py`: The main orchestrator loop. It reads the master database, filters out already processed logs via the tracker, sorts by priority score, and runs controlled batches of 10.
* `auto_apply.py`: The absolute mechanical workhorse. Handles browser contexts, field input bindings, smart bilingual file selections, Groq API inference connections, and target submit clicks.
* `routers.py`: Dedicated platform-routing scripts handling the deep logic for cracking middleman domains and identifying transitional redirect anchors.
* `tracker.py`: Simple, transactional JSON handler managing state tracking, write locks, and diagnostic outcome strings.
* `.env`: A protected environment configuration holding your private API tokens.
* `my_info.json`: Contains structured identity nodes, current positioning data, and raw data profiles for both English and Swedish cover letters.

---

## ⚙️ Project Setup

### 1. Installation Dependencies

Install the required execution layers and build standard Playwright browser binaries inside your terminal:

```bash
pip install playwright groq
playwright install

```

### 2. Configure Credentials (`.env`)

Create a file named exactly `.env` inside the root directory and append your Groq deployment credentials:

```env
GROQ_API_KEY=gsk_your_actual_groq_api_key_string_here...

```

### 3. Verification Files Setup

Ensure your profile details inside `my_info.json` are accurate and make sure your matching portfolio files live in the same root folder:

* 📄 `cv-fullstack.pdf` (English Version)
* 📄 `new-cv-fullstack-svenska.pdf` (Swedish Version)
* 📄 `Cover-Letter.pdf` (English Version)
* 📄 `personligt-brev.pdf` (Swedish Version)

---

## 🚀 Execution Workflows

### Standard Batch Execution

To kick off the automated pipeline and process your database tracking allocations:

```bash
python mass_apply.py

```

### Direct Isolated Single-Job Diagnostics

If you ever want to test changes to form-filling or check a specific complex site design layout without checking the full JSON database layer, you can execute a standalone pass at the bottom of `auto_apply.py`:

```bash
python auto_apply.py

```

---

## 🧠 Interactive Human-In-The-Loop Commands

When the automation completes its sequence actions on a page, it yields terminal control to you so you stay perfectly in charge of the absolute final click sequence:

* **`ENTER` (Blank Input):** Saves the target job asset as `applied` to your history logs and immediately spins up the next open URL link.
* **`s` + `ENTER`:** Logs the asset target as `skipped` in your tracking history (will not open again) and proceeds.
* **`q` + `ENTER`:** Gracefully safely closes active headless browser instances and shuts down the core orchestrator loops cleanly.