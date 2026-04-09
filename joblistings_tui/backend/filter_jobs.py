from __future__ import annotations

from dataclasses import dataclass
import re
import shlex

import pandas as pd


DEFAULT_TEXT_FIELDS = ("title", "company", "location", "description")
BOOL_ALIASES = {
    "saved": "saved",
    "applied": "applied",
    "hidden": "hidden",
    "remote": "is_remote",
}
COMPARATOR_RE = re.compile(r"^(>=|<=|>|<|=)(.+)$")


@dataclass(frozen=True)
class _QueryTerm:
    negated: bool
    field: str | None
    value: str


def _tokenize_query(query: str) -> list[str]:
    try:
        return shlex.split(query)
    except ValueError:
        return query.split()


def _parse_terms(query: str) -> tuple[list[_QueryTerm], str | None, bool]:
    terms: list[_QueryTerm] = []
    sort_field: str | None = None
    sort_desc = False

    for raw in _tokenize_query(query):
        negated = raw.startswith("-") and len(raw) > 1
        token = raw[1:] if negated else raw

        if ":" not in token:
            terms.append(_QueryTerm(negated=negated, field=None, value=token))
            continue

        field, value = token.split(":", 1)
        field = field.strip().lower()
        value = value.strip()

        if not value:
            continue

        if field == "sort":
            sort_desc = value.startswith("-")
            sort_field = value[1:] if sort_desc else value
            sort_field = sort_field.strip()
            continue

        terms.append(_QueryTerm(negated=negated, field=field, value=value))

    return terms, sort_field, sort_desc


def _contains(series: pd.Series, value: str) -> pd.Series:
    return series.fillna("").astype(str).str.contains(value, case=False, regex=False)


def _parse_comparator(value: str) -> tuple[str, str] | None:
    match = COMPARATOR_RE.match(value)
    if not match:
        return None
    op, rhs = match.groups()
    return op, rhs.strip()


def _compare(lhs: pd.Series, op: str, rhs: float) -> pd.Series:
    if op == ">=":
        return lhs >= rhs
    if op == "<=":
        return lhs <= rhs
    if op == ">":
        return lhs > rhs
    if op == "<":
        return lhs < rhs
    return lhs == rhs


def _text_term_mask(term: str, df: pd.DataFrame) -> pd.Series:
    fields = [field for field in DEFAULT_TEXT_FIELDS if field in df.columns]
    if not fields:
        return pd.Series(True, index=df.index)

    mask = pd.Series(False, index=df.index)
    for field in fields:
        mask = mask | _contains(df[field], term)
    return mask


def _field_term_mask(field: str, value: str, df: pd.DataFrame) -> pd.Series:
    if field == "is":
        col = BOOL_ALIASES.get(value.lower())
        if not col or col not in df.columns:
            return pd.Series(False, index=df.index)
        return df[col].fillna(False).astype(bool)

    if field not in df.columns:
        return pd.Series(False, index=df.index)

    series = df[field]
    comparator = _parse_comparator(value)

    if comparator:
        op, rhs_text = comparator

        if field == "date_posted":
            lhs = pd.to_datetime(series, errors="coerce")
            rhs = pd.to_datetime(rhs_text, errors="coerce")
            if pd.isna(rhs):
                return pd.Series(False, index=df.index)
            return _compare(lhs, op, rhs)

        lhs_num = pd.to_numeric(series, errors="coerce")
        try:
            rhs_num = float(rhs_text)
        except ValueError:
            return pd.Series(False, index=df.index)
        return _compare(lhs_num, op, rhs_num)

    if pd.api.types.is_bool_dtype(series):
        lowered = value.lower()
        if lowered in {"true", "1", "yes"}:
            target = True
        elif lowered in {"false", "0", "no"}:
            target = False
        else:
            return pd.Series(False, index=df.index)
        return series.fillna(False).astype(bool) == target

    return _contains(series, value)


def filter_jobs_df(query: str, jobs: pd.DataFrame) -> pd.DataFrame:
    """Filter jobs DataFrame using a GitHub-style query language.

    Supported patterns:
    - Free text: `python remote`
    - Field qualifiers: `company:stripe title:"staff engineer"`
    - Negation: `-company:amazon -intern`
    - Boolean aliases: `is:saved is:applied is:hidden is:remote`
    - Numeric/date comparators: `fit_score:>=0.7 date_posted:>=2026-01-01`
    - Sorting: `sort:-date_posted` or `sort:fit_score`
    """
    if jobs.empty:
        return jobs

    if not query or not query.strip():
        return jobs

    terms, sort_field, sort_desc = _parse_terms(query)
    if not terms and not sort_field:
        return jobs

    mask = pd.Series(True, index=jobs.index)

    for term in terms:
        if term.field is None:
            term_mask = _text_term_mask(term.value, jobs)
        else:
            term_mask = _field_term_mask(term.field, term.value, jobs)

        if term.negated:
            term_mask = ~term_mask
        mask = mask & term_mask

    filtered = jobs.loc[mask]

    if sort_field and sort_field in filtered.columns:
        filtered = filtered.sort_values(by=sort_field, ascending=not sort_desc)

    return filtered
