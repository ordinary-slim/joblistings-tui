import pandas as pd
from sqlalchemy import create_engine, inspect

DB_URL = "sqlite:///jobs.db"
TABLE_NAME = "jobs"

def load_existing_jobs() -> pd.DataFrame:
    engine = create_engine(DB_URL)

    inspector = inspect(engine)

    # If table does not exist yet → return empty DataFrame
    if TABLE_NAME not in inspector.get_table_names():
        return pd.DataFrame()

    df = pd.read_sql_table(TABLE_NAME, engine)

    return df

def filter_duplicates(scraped_jobs: pd.DataFrame,
                 existing_jobs: pd.DataFrame) -> pd.DataFrame:
    if scraped_jobs.empty:
        return scraped_jobs

    # 1. Remove duplicates inside the newly scraped batch
    scraped_with_direct = scraped_jobs[scraped_jobs["job_url_direct"].notna()].drop_duplicates(subset=["job_url_direct"])
    scraped_without_direct = scraped_jobs[scraped_jobs["job_url_direct"].isna()].drop_duplicates(subset=["job_url"])
    scraped_jobs = pd.concat([scraped_with_direct, scraped_without_direct], ignore_index=True)

    # 2. If DB is empty, everything is new
    if existing_jobs.empty:
        return scraped_jobs

    # 3. Filter out rows already present in DB by direct URL first
    existing_direct_urls = set(existing_jobs["job_url_direct"].dropna())
    has_direct = scraped_jobs["job_url_direct"].notna()
    new_jobs = pd.concat(
        [
            scraped_jobs[has_direct & ~scraped_jobs["job_url_direct"].isin(existing_direct_urls)],
            scraped_jobs[~has_direct],
        ],
        ignore_index=True,
    )

    # 4. Then filter remaining rows by regular job URL
    existing_job_urls = set(existing_jobs["job_url"].dropna())
    new_jobs = scraped_jobs[
        scraped_jobs["job_url"].isna() | ~scraped_jobs["job_url"].isin(existing_job_urls)
    ].copy()

    return new_jobs

def save_new_jobs(new_jobs: pd.DataFrame) -> None:
    if new_jobs.empty:
        return

    engine = create_engine(DB_URL)

    new_jobs.to_sql(
        TABLE_NAME,
        con=engine,
        if_exists="append",
        index=False,
    )
    print(f"Saved {len(new_jobs)} new jobs to the {TABLE_NAME} table in {DB_URL}.")
