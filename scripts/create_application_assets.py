from __future__ import annotations

import json
from pathlib import Path
import re
import sys
from typing import Mapping, Any


DEFAULT_APPLICATIONS_DIR = Path("/home/mehdi/Documents/job-application/applications")


def _slugify(value: str) -> str:
    value = (value or "").strip().lower()
    value = re.sub(r"\s+", "-", value)
    value = re.sub(r"[^a-z0-9-]", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value or "unknown"


def _country_from_location(location: str) -> str:
    if not location:
        return "unknown"
    parts = [part.strip() for part in location.split(",") if part.strip()]
    if not parts:
        return "unknown"
    return parts[-1]


def application_directory_name(job: Mapping[str, Any]) -> str:
    """Return a normalized directory name: country-company-job-title."""
    country = _country_from_location(str(job.get("location", "")))
    company = str(job.get("company", ""))
    title = str(job.get("title", ""))
    return "-".join((_slugify(country), _slugify(company), _slugify(title)))


def create_application_directory(
    job: Mapping[str, Any],
    base_dir: Path = DEFAULT_APPLICATIONS_DIR,
) -> Path:
    """Create and return the application directory path for a job."""
    directory = base_dir / application_directory_name(job)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _tex_escape(value: str) -> str:
    replacements = {
        "\\": r"\\textbackslash{}",
        "{": r"\\{",
        "}": r"\\}",
        "#": r"\\#",
        "$": r"\\$",
        "%": r"\\%",
        "&": r"\\&",
        "_": r"\\_",
        "~": r"\\textasciitilde{}",
        "^": r"\\textasciicircum{}",
    }
    return "".join(replacements.get(ch, ch) for ch in (value or ""))


def create_cover_letter_content_tex(
    job: Mapping[str, Any],
    output_dir: Path,
) -> Path:
    """Create cover-letter-content.tex in output_dir and return its path."""
    company = _tex_escape(str(job.get("company", "")))
    title = _tex_escape(str(job.get("title", "")))

    tex_path = output_dir / "cover-letter-content.tex"
    tex_path.write_text(
        "\n".join(
            [
                rf"\newcommand{{\myCompany}}{{{company}}}",
                rf"\newcommand{{\advertisedPosition}}{{{title}}}",
                r"\includerefstrue",
                r"\newcommand{\coverBody}{}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return tex_path


def create_description_markdown(job: Mapping[str, Any], output_dir: Path) -> Path:
    """Create description.md in output_dir and return its path."""
    title = str(job.get("title", "")).strip() or "N/A"
    company = str(job.get("company", "")).strip() or "N/A"
    location = str(job.get("location", "")).strip() or "N/A"
    date_posted = str(job.get("date_posted", "")).strip() or "N/A"
    job_type = str(job.get("job_type", "")).strip() or "N/A"

    salary_source = str(job.get("salary_source", "")).strip()
    currency = str(job.get("currency", "")).strip()
    interval = str(job.get("interval", "")).strip()
    salary = " ".join(
        part
        for part in [salary_source, currency, f"per {interval}" if interval else ""]
        if part
    ).strip()
    salary = salary or "N/A"

    is_remote = bool(job.get("is_remote", False))
    remote = "Yes" if is_remote else "No"

    url = (
        str(job.get("job_url_direct", "")).strip()
        or str(job.get("job_url", "")).strip()
        or "N/A"
    )
    description = str(job.get("description", "")).strip() or "No description available."

    fit_score = str(job.get("fit_score", "")).strip() or "N/A"
    fit_keywords = str(job.get("fit_keywords", "")).strip() or "N/A"
    fit_reasoning = str(job.get("fit_reasoning", "")).strip() or "N/A"

    description_path = output_dir / "description.md"
    content = "\n".join(
        [
            "# Job Context",
            "",
            f"Title: {title}",
            f"Company: {company}",
            f"Location: {location}",
            f"Date Posted: {date_posted}",
            f"Job Type: {job_type}",
            f"Salary: {salary}",
            f"Remote: {remote}",
            f"URL: {url}",
            f"Fit score (1-10): {fit_score}",
            f"Fit keywords: {fit_keywords}",
            "",
            "## Fit reasoning",
            fit_reasoning,
            "",
            "## Description",
            description,
            "",
        ]
    )
    description_path.write_text(content, encoding="utf-8")
    return description_path


def main(job: dict) -> str:
    # Create folder
    directory = create_application_directory(job)
    # Create description.md
    description_path = create_description_markdown(job, directory)
    # Create tex file
    tex_path = create_cover_letter_content_tex(job, directory)

    log_lines = [
        f"folder: {directory}",
        f"description: {description_path.name}",
        f"tex: {tex_path.name}",
    ]
    return " | ".join(log_lines)


if __name__ == "__main__":
    payload = json.loads(sys.stdin.read())
    if not isinstance(payload, dict):
        raise ValueError("Expected a JSON object on stdin")
    print(main(payload))
