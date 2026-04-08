from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parent
DATA_DIR = PROJECT_ROOT / "data"

RESUME_MD = str(DATA_DIR / "RESUME.md")
RESUME_JSON = str(DATA_DIR / "RESUME.json")
QUERIES_FILE = str(DATA_DIR / "queries.yaml")
DB_FILE = str(DATA_DIR / "jobs.db")
