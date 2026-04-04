from jobspy import scrape_jobs
import yaml

queries_file = "queries.yaml"
def load_queries():
    with open(queries_file, "r") as f:
        queries = yaml.safe_load(f)
    return queries

def get_country(location):
    return location.split(",")[-1].rstrip().lstrip().lower()

jobsites = ["linkedin", "indeed"]
def query(search_term, location, results_wanted=20, trial=False):
    if trial:
        return fakequery()
    jobs = scrape_jobs(
         site_name=jobsites,
         search_term=search_term,
         location=location,
         country_indeed=get_country(location),
         results_wanted=results_wanted,
     )
    num_jobs_linkedin = (jobs["site"] == "linkedin").sum()
    num_jobs_indeed = (jobs["site"] == "indeed").sum()
    print(f"Found {num_jobs_linkedin} jobs on LinkedIn and {num_jobs_indeed} jobs on Indeed for the search term '{search_term}' in {location}.")
    return jobs

def fakequery():
    import pandas as pd
    csvfile = "c++-fem-france-2026-04-03-13:00.csv"
    df = pd.read_csv(csvfile)
    print(f"Loaded {len(df)} jobs from {csvfile} for the search term 'c++ finite lement' in France.")
    return df
