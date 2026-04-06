import pandas as pd
from datetime import datetime

from fetch import load_queries, query
from storage import load_existing_jobs, filter_duplicates, save_new_jobs

import argparse

def search_jobs(queries, jobsites, results_wanted, trial=False) -> None:
    if not queries:
        print("No queries provided.")
        return
    for q in queries:
        print(f"Searching for '{q['search_term']}' in {q['location']} on {', '.join(jobsites)}, this may take a moment...")
        scraped_jobs = query(**q, jobsites=jobsites, results_wanted=results_wanted, trial=trial)

        if scraped_jobs.empty:
            print("No jobs scraped.")
            return

        existing_jobs = load_existing_jobs()
        new_jobs = filter_duplicates(scraped_jobs, existing_jobs)

        if new_jobs.empty:
            print(f"No new jobs found, database (size {len(existing_jobs)}) is up to date.")
            continue

        advertise_new_jobs(new_jobs)
        save_new_jobs(new_jobs)

def advertise_new_jobs(new_jobs: pd.DataFrame) -> None:
    print(f"Found {len(new_jobs)} new jobs:")

    for _, row in new_jobs.iterrows():
        url = row.get("job_url_direct") or row.get("job_url") or "N/A"
        print(
            f"- {row.get('job_title', '')} at {row.get('company', '')} "
            f"in {row.get('location', '')} (URL: {url})"
        )

    # --- write CSV with timestamp ---
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    filename = f"new_jobs_{ts}.csv"

    new_jobs.to_csv(
        filename,
        index=False,
    )

    print(f"Saved new jobs to: {filename}")

if __name__=="__main__":
    parser = argparse.ArgumentParser(description="Search for new jobs and save them to the database.")
    parser.add_argument("--queries", type=str, default="queries.yaml", help="Path to the YAML file containing search queries.")
    parser.add_argument("--jobsites", nargs="+", default=["linkedin", "indeed"], help="List of job sites to scrape (e.g., linkedin indeed).")
    parser.add_argument("--results", type=int, default=10, help="Number of job results to fetch per query.")
    parser.add_argument("--trial", action="store_true", help="Run in trial mode with fake query.")
    args = parser.parse_args()

    if not args.trial:
        queries = load_queries(args.queries)
    else:
        queries = [{"search_term": "", "location": ""}]

    search_jobs(queries, jobsites=args.jobsites, results_wanted=args.results,
                trial=args.trial)
