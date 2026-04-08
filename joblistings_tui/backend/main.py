import pandas as pd
from datetime import datetime

from .fetch import load_queries, query
from .storage import (
    load_existing_jobs,
    filter_duplicates,
    save_new_jobs,
    normalize_jobspy_dataframe,
)
from .fit_score import score_jobs

import argparse
from joblistings_tui.config import QUERIES_FILE


def search_jobs(
    queries, jobsites, results_wanted, score=True, trial=False
) -> pd.DataFrame:
    accumulated_new_jobs = pd.DataFrame()
    if not queries:
        print("No queries provided.")
        return accumulated_new_jobs

    existing_jobs = load_existing_jobs()

    for q in queries:
        print(
            f"Searching for '{q['search_term']}' in {q['location']} on {', '.join(jobsites)}, this may take a moment..."
        )
        scraped_jobs = query(
            **q, jobsites=jobsites, results_wanted=results_wanted, trial=trial
        )

        if scraped_jobs.empty:
            print("No jobs scraped for this query.")
            continue

        new_jobs = filter_duplicates(scraped_jobs, existing_jobs)

        if new_jobs.empty:
            print(
                f"No new jobs found, database (size {len(existing_jobs)}) is up to date."
            )
            continue
        new_jobs = normalize_jobspy_dataframe(new_jobs)
        if score:
            new_jobs = score_jobs(new_jobs)
        advertise_new_jobs(new_jobs)
        save_new_jobs(new_jobs)

        accumulated_new_jobs = pd.concat(
            [accumulated_new_jobs, new_jobs], ignore_index=True
        )
        existing_jobs = pd.concat([existing_jobs, new_jobs], ignore_index=True)

    return accumulated_new_jobs


def advertise_new_jobs(new_jobs: pd.DataFrame) -> None:
    if new_jobs.empty:
        print("No new jobs to advertise.")
        return

    print(f"Found {len(new_jobs)} new jobs:")

    if "site" in new_jobs.columns:
        print("By site:")
        for site, count in new_jobs["site"].value_counts().items():
            print(f"- {site}: {count}")

    print("Details:")
    for _, row in new_jobs.iterrows():
        if pd.notna(row["job_url_direct"]) and row["job_url_direct"] != "":
            url = row["job_url_direct"]
        elif pd.notna(row["job_url"]) and row["job_url"] != "":
            url = row["job_url"]
        else:
            url = "N/A"

        print(
            f"- {row['title']} at {row['company']} in {row['location']} "
            f"(site: {row['site']}, fit_score: {row['fit_score']}, URL: {url})"
        )

    # --- write CSV with timestamp ---
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    filename = f"new_jobs_{ts}.csv"

    new_jobs.to_csv(
        filename,
        index=False,
    )

    print(f"Saved new jobs to: {filename}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Search for new jobs and save them to the database."
    )
    parser.add_argument(
        "--queries",
        type=str,
        default=QUERIES_FILE,
        help="Path to the YAML file containing search queries.",
    )
    parser.add_argument(
        "--jobsites",
        nargs="+",
        default=["linkedin", "indeed"],
        help="List of job sites to scrape (e.g., linkedin indeed).",
    )
    parser.add_argument(
        "--results",
        type=int,
        default=10,
        help="Number of job results to fetch per query.",
    )
    parser.add_argument(
        "--trial", action="store_true", help="Run in trial mode with fake query."
    )
    args = parser.parse_args()

    if not args.trial:
        queries = load_queries(args.queries)
    else:
        queries = [{"search_term": "", "location": ""}]

    search_jobs(
        queries, jobsites=args.jobsites, results_wanted=args.results, trial=args.trial
    )


if __name__ == "__main__":
    main()
