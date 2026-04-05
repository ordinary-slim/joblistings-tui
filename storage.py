import pandas as pd
from typing import Union

from sqlalchemy import create_engine, inspect, text

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

def dedup_jobs_dataframe(jobs : pd.DataFrame):
    jobs.drop_duplicates(subset=["id", "job_url_direct", "job_url"], inplace=True)

def filter_duplicates(scraped_jobs: pd.DataFrame, existing_jobs: pd.DataFrame):
    if scraped_jobs.empty:
        return scraped_jobs

    # 1. Remove duplicates within the scraped jobs themselves first
    dedup_jobs_dataframe(scraped_jobs)

    # 2. If DB is empty, everything is new
    if existing_jobs.empty:
        return scraped_jobs

    # 3. Find duplicates between scraped jobs and existing jobs
    for k in ["id", "job_url_direct", "job_url"]:
        scraped_jobs = scraped_jobs[~scraped_jobs[k].isin(existing_jobs[k])]

    return scraped_jobs


def save_new_jobs(new_jobs: pd.DataFrame) -> None:
    if new_jobs.empty:
        return
    new_jobs["applied"] = False
    new_jobs["fit_score"] = 5.0
    new_jobs["hidden"] = False

    engine = create_engine(DB_URL)

    new_jobs.to_sql(
        TABLE_NAME,
        con=engine,
        if_exists="append",
        index=False,
    )
    print(f"Saved {len(new_jobs)} new jobs to the {TABLE_NAME} table in {DB_URL}.")

def update_job_field(job_id: str, field: str, value: Union[float, bool]) -> None:
    allowed_fields = {"applied", "hidden", "fit_score"}
    if field not in allowed_fields:
        raise ValueError(f"Unsupported field update: {field}")

    engine = create_engine(DB_URL)
    inspector = inspect(engine)
    if TABLE_NAME not in inspector.get_table_names():
        raise RuntimeError(f"Table '{TABLE_NAME}' does not exist")

    stmt = text(f"UPDATE {TABLE_NAME} SET {field} = :value WHERE id = :job_id")

    with engine.begin() as conn:
        result = conn.execute(stmt, {"value": value, "job_id": job_id})
        if result.rowcount == 0:
            raise ValueError(f"No job found with id='{job_id}'")
