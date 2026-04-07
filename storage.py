import pandas as pd
from typing import Union, Sequence

from sqlalchemy import create_engine, inspect, text

DB_URL = "sqlite:///jobs.db"
TABLE_NAME = "jobs"

def initialize_db() -> None:
    engine = create_engine(DB_URL)
    create_stmt = text(
        f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            id TEXT,
            site TEXT,
            job_url TEXT,
            job_url_direct TEXT,
            title TEXT,
            company TEXT,
            location TEXT,
            date_posted TEXT,
            job_type TEXT,
            salary_source TEXT,
            interval TEXT,
            min_amount FLOAT,
            max_amount FLOAT,
            currency TEXT,
            is_remote BOOLEAN,
            job_level TEXT,
            job_function TEXT,
            listing_type TEXT,
            emails TEXT,
            description TEXT,
            company_industry TEXT,
            company_url TEXT,
            company_logo TEXT,
            company_url_direct TEXT,
            company_addresses TEXT,
            company_num_employees TEXT,
            company_revenue TEXT,
            company_description TEXT,
            skills TEXT,
            experience_range TEXT,
            company_rating FLOAT,
            company_reviews_count FLOAT,
            vacancy_count FLOAT,
            work_from_home_type TEXT,
            applied BOOLEAN,
            fit_score FLOAT,
            hidden BOOLEAN
        )
        """
    )
    with engine.begin() as conn:
        conn.execute(create_stmt)


def normalize_jobspy_dataframe(jobs: pd.DataFrame) -> pd.DataFrame:
    '''Modify in-place but still return the DataFrame for chaining'''
    jobs["applied"] = False
    jobs["fit_score"] = 0.0
    jobs["fit_keywords"] = ""
    jobs["fit_reasoning"] = ""
    jobs["hidden"] = False
    return jobs

def load_existing_jobs() -> pd.DataFrame:
    engine = create_engine(DB_URL)

    inspector = inspect(engine)

    # If table does not exist yet → return empty DataFrame
    if TABLE_NAME not in inspector.get_table_names():
        initialize_db()
        return pd.DataFrame()

    df = pd.read_sql_table(TABLE_NAME, engine)

    # Convert `date_posted` column to datetime
    df["date_posted"] = pd.to_datetime(df["date_posted"], errors="coerce")

    return df


def dedup_jobs_dataframe(jobs: pd.DataFrame) -> None:
    jobs.drop_duplicates(subset=["id", "job_url_direct", "job_url"], inplace=True)


def filter_duplicates(
    scraped_jobs: pd.DataFrame, existing_jobs: pd.DataFrame
) -> pd.DataFrame:
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

    engine = create_engine(DB_URL)

    new_jobs.to_sql(
        TABLE_NAME,
        con=engine,
        if_exists="append",
        index=False,
    )
    print(f"Saved {len(new_jobs)} new jobs to the {TABLE_NAME} table in {DB_URL}.")


def update_job_field(
    job_id: str,
    fields: Union[str, Sequence[str]],
    values: Union[float, bool, str, Sequence[Union[float, bool, str]]],
) -> None:
    allowed_fields = {"applied", "hidden", "fit_score", "fit_keywords", "fit_reasoning"}

    # Normalize to lists
    if isinstance(fields, str):
        fields = [fields]
    else:
        fields = list(fields)

    if isinstance(values, (list, tuple)):
        values = list(values)
    else:
        values = [values]

    # Validation
    if len(fields) != len(values):
        raise ValueError("field and value must have the same length")

    for f in fields:
        if f not in allowed_fields:
            raise ValueError(f"Unsupported field update: {f}")

    engine = create_engine(DB_URL)
    inspector = inspect(engine)
    if TABLE_NAME not in inspector.get_table_names():
        raise RuntimeError(f"Table '{TABLE_NAME}' does not exist")

    # Build dynamic SET clause
    set_clause = ", ".join(f"{f} = :{f}" for f in fields)

    stmt = text(f"UPDATE {TABLE_NAME} SET {set_clause} WHERE id = :job_id")

    params = {f: v for f, v in zip(fields, values)}
    params["job_id"] = job_id

    with engine.begin() as conn:
        result = conn.execute(stmt, params)
        if result.rowcount == 0:
            raise ValueError(f"No job found with id='{job_id}'")
