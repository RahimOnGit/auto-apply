# mass_apply.py
import json
import os
from auto_apply import apply_to_job
from tracker import is_processed, record_job

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'jobs_db.json')

def run_mass_apply():
    try:
        with open(DB_PATH, 'r', encoding='utf-8') as f:
            jobs = json.load(f)
    except Exception as e:
        print(f"❌ Failed to read jobs database: {e}")
        return

    print(f"📦 Database loaded. {len(jobs)} total jobs found.")
    jobs.sort(key=lambda x: x.get('score', 0), reverse=True)

    BATCH_SIZE = 10
    # Filters out any job that is already in job_history.json
    active_batch = [j for j in jobs if not is_processed(j.get('link'))][:BATCH_SIZE]

    if not active_batch:
        print("🎉 High-five! No new unprocessed jobs remaining in this batch configuration.")
        return

    print(f"🔥 Starting batch run for the top {len(active_batch)} open jobs.\n")

    for index, job in enumerate(active_batch):
        company = job.get('company', 'Unknown Company')
        title = job.get('title', 'Unknown Role')
        url = job.get('link')

        print("\n" + "="*60)
        print(f"🚀 Processing [{index + 1}/{len(active_batch)}]: {title} @ {company}")
        print("="*60)

        try:
            status, outcome_message = apply_to_job(url)

            if status == "quit":
                print("🛑 Batch runner paused by user request.")
                break

            record_job(url, status, outcome_message)

        except Exception as err:
            print(f"💥 Critical error handling job webpage: {err}")
            record_job(url, "failed", str(err))
            continue

if __name__ == "__main__":
    run_mass_apply()