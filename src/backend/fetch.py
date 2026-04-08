import pandas as pd
from jobspy import scrape_jobs
import yaml

ALL_JOB_SITES = ["LINKEDIN", "INDEED", "ZIPRECRUITER", "GLASSDOOR", "GOOGLE", "BAYT", "NAUKRI", "BDJOBS"]
JOB_SITE_LABELS = {
    "LINKEDIN": "LinkedIn",
    "INDEED": "Indeed",
    "ZIPRECRUITER": "ZipRecruiter",
    "GLASSDOOR": "Glassdoor",
    "GOOGLE": "Google",
    "BAYT": "Bayt",
    "NAUKRI": "Naukri",
    "BDJOBS": "BDJobs",
}
DEFAULT_JOB_SITES = ["LINKEDIN", "INDEED"]

def load_queries(queries_file):
    try:
        with open(queries_file, "r") as f:
            queries = yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Error: Queries file '{queries_file}' not found.")
        return []
    except yaml.YAMLError as e:
        print(f"Error parsing YAML file '{queries_file}': {e}")
        return []
    assert isinstance(queries, list), f"Error: Expected a list of queries in '{queries_file}', but got {type(queries).__name__}."
    return queries

def get_country(location):
    return location.split(",")[-1].rstrip().lstrip().lower()

def query(search_term, location, jobsites=DEFAULT_JOB_SITES, results_wanted=20, trial=False) -> pd.DataFrame:
    jobsites = [site.upper() for site in jobsites] if jobsites else DEFAULT_JOB_SITES
    if trial:
        return fakequery()
    for site in jobsites:
        assert site in ALL_JOB_SITES, f"Error: Unsupported job site '{site}'. Supported sites are: {', '.join(ALL_JOB_SITES)}."
    jobs = scrape_jobs(
         site_name=jobsites,
         search_term=search_term,
         location=location,
         country_indeed=get_country(location),
         results_wanted=results_wanted,
         linkedin_fetch_description=True,
     )
    if not jobs.empty:
        for site in jobsites:
            num_jobs_site = (jobs["site"] == site).sum()
            print(f"Found {num_jobs_site} jobs on {JOB_SITE_LABELS[site]}.")
    jobs['date_posted'] = pd.to_datetime(jobs['date_posted'], errors='coerce')  # Uniform 
    return jobs

def fakequery():
    # TODO: Move this to a test
    import pandas as pd
    csvfile = "./data/c++-fem-france-2026-04-03-13:00.csv"
    df = pd.read_csv(csvfile)
    print(f"Loaded {len(df)} jobs from {csvfile} for the search term 'c++ finite lement' in France.")
    return df
