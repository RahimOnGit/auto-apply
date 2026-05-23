# Auto-Apply

A minimal Python/Playwright script that auto‑fills job‑application forms using your personal CV, cover letter and contact info stored in a JSON file.

## 📂 Project layout
```
auto-apply/
├─ auto_apply.py      # main automation script
├─ my_info.json       # your personal data (editable)
├─ CV.pdf             # your résumé (place here)
└─ CoverLetter.pdf   # your cover letter (place here)
```

## 🛠️ Prerequisites
- **Python 3.8+**
- **Playwright** (`pip install playwright`) and its browsers (`playwright install`)
- Your CV and cover letter PDFs in the project folder

## ⚙️ Setup
```bash
# Clone or copy the folder to E:\Projects\auto-apply
cd E:\Projects\auto-apply
# Install dependencies
pip install -r <(pip freeze | grep playwright)   # or simply:
pip install playwright
# Install browsers for Playwright
playwright install
```

## ▶️ Usage
Edit `my_info.json` with your real details, then run:
```bash
python auto_apply.py
```
The script will launch a **visible** Chromium window, navigate to the URL you pass to `apply_to_job`, fill the fields and upload the files. When the form is done you get a prompt – hit **Enter** in the terminal after you manually submit the form.

### Example
```python
if __name__ == "__main__":
    apply_to_job("https://example.com/job-application-form")
```
Replace the URL with the actual job‑application page you want to target.

## 🔧 Customising selectors
Playwright uses CSS selectors to locate form inputs. If a site uses different names/ids, edit the `page.fill` / `page.set_input_files` calls in `auto_apply.py` accordingly.

### Advanced tweaks
- **`exact=True` on “Jag samtycker”** – forces Playwright to click the exact label text next to the fake checkbox, skipping the long legal‑text block.
- **`force=True` on `#pul`** – overrides visibility checks so a hidden real checkbox can be toggled even when covered by design elements.
- **Refined button targeting** – uses a precise selector `<input type="submit" value="Skicka" />` via the standard button‑role helper, making the submit click reliable across layout changes.

## 📜 License
Feel free to use, tweak, or pirate this snippet – it’s yours.

---
*Created by Rah Elhaj – your personal AI sidekick.*
