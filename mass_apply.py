import json
import os
from auto_apply import apply_to_job

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'jobs_db.json') # Make sure this matches your file name

def run_mass_apply():
    try:
        with open(DB_PATH, 'r', encoding='utf-8') as f:
            jobs = json.load(f)
    except FileNotFoundError:
        print(f"❌ Couldn't find {DB_PATH}.")
        return

    print(f"📦 Successfully loaded large database ({len(jobs)} total jobs found).")

    # --- CHILL FILTERING & SORTING ---
    # 1. Sort jobs so highest score comes first (or change to 'published_date' if you prefer)
    jobs.sort(key=lambda x: x.get('score', 0), reverse=True)
    
    # 2. Slice the data so you only deal with a small batch at a time
    BATCH_SIZE = 10 
    jobs_batch = jobs[:BATCH_SIZE]
    
    print(f"🔥 Picked the top {BATCH_SIZE} highest-scoring jobs for this session.\n")
    
    for index, job in enumerate(jobs_batch):
        company = job.get('company', 'Unknown Company')
        title = job.get('title', 'Unknown Role')
        score = job.get('score', 'N/A')
        job_link = job.get('link')
        
        if not job_link:
            continue
            
        print("==================================================")
        print(f"🚀 Job {index + 1} of {len(jobs_batch)}: {title} @ {company} (Score: {score})")
        print("==================================================")
        
        # Fire off your working automation script
        apply_to_job(job_link)
        
        print("\n--------------------------------------------------")
        user_input = input("👉 Press ENTER to load the NEXT job, or type 'q' to QUIT: ")
        
        if user_input.lower() == 'q':
            print("🛑 Stopping the session. Rest up!")
            break

    print("\n🎉 Batch complete! Run the script again whenever you want to tackle the next 10.")

if __name__ == "__main__":
    run_mass_apply()