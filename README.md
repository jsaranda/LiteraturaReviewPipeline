![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Status](https://img.shields.io/badge/status-research%20artifact-blue)
![Last Commit](https://img.shields.io/github/last-commit/jsaranda/LiteraturaReviewPipeline)

# Literature-search and screening pipeline

This repository contains the reproducible search, screening, combination, and
deduplication workflow developed for the systematic literature review:

> **Agentic AI in Logistics Operations: A Systematic Literature Review and
> Taxonomies**

The pipeline supports the computationally intensive stages of the review. It
does **not** replace researcher judgment. The eligibility criteria, screening
instructions, and final full-text decisions were defined and controlled by the
authors. Claude Haiku 4.5 was used only for batched title and abstract
classification against fixed protocol criteria. The three-pass reading and
final full-text eligibility decisions were performed manually.

## Workflow overview

Each bibliographic source was processed separately through impurity removal,
title screening, and abstract screening. Records were combined and
deduplicated only after these source-level stages so that source-specific
funnel counts remained traceable.

```text
Initial search
  -> Impurity removal
  -> Title screening
  -> Abstract screening
  -> Combination and deduplication
  -> Short-paper filter
  -> Manual three-pass reading
  -> Manual full-text eligibility decision
```

The review retrieved 23,116 records from nine bibliographic sources
and retained 37 primary studies. The public supplementary workbook contains
the final study identifiers, metadata, classifications, quality assessment,
evidence maturity, and analytical summary used in the manuscript.

## Supplementary review dataset

The reviewer-facing dataset supporting the systematic literature review is
available at:

[`supplementary/Agentic_AI_Logistics_Supplementary_Dataset.xlsx`](supplementary/Agentic_AI_Logistics_Supplementary_Dataset.xlsx)

The workbook contains the final 37-study corpus, bibliographic metadata,
study-level classifications, quality-assessment scores, evidence-maturity
levels, analytical mappings, and consolidated descriptive results reported in
the manuscript.

Study identifiers S01–S37 correspond directly to the identifiers used in the
manuscript tables and figures. The workbook contains the final validated
classifications and omits internal working notes, preliminary suggestions, and
superseded counts.

The full texts of the primary studies are not redistributed because they
remain subject to their respective publishers' copyright and access
conditions. Readers can access the publications through the DOI and URL
metadata provided in the workbook.

## Methodological responsibility and AI-assisted screening

The title and abstract stages use the Anthropic Message Batches API. The
default model recorded in `config.py` is:

```text
claude-haiku-4-5-20251001
```

The model did not receive an open-ended request to judge relevance. The exact
classification instructions are embedded in:

- `pipeline/06_llm_title_screening_submit.py`
- `pipeline/11_llm_abstract_screening_submit.py`

These instructions operationalize the protocol's inclusion and exclusion
criteria and require a structured `include` or `exclude` label plus a short
reason. Title requests contain at most 75 records, abstract requests at most
15 records, and both use `max_tokens=4096`. No temperature is explicitly set,
so the provider default applies.

Before full-scale title screening, a reproducible stratified pilot sampled six
titles per source (`random.seed(42)`). Nine sources were represented, yielding
54 titles. The pilot was manually classified and used to refine the fixed
instructions before batch execution. Formal pilot sensitivity, specificity,
or agreement statistics were not preserved and are therefore not claimed.

The LLM-generated labels supported only title and abstract screening. An
offline heuristic later ranked full texts to prioritize inspection, but it did
not determine eligibility. Manual three-pass reading and manual full-text
assessment produced the final corpus. No independent random audit of the
model-excluded records was preserved.

## Requirements

- Python 3.10 or newer
- Dependencies listed in `requirements.txt`
- API credentials for the sources used in a new execution

```bash
git clone https://github.com/jsaranda/LiteraturaReviewPipeline.git
cd LiteraturaReviewPipeline
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

All commands below must be run from the repository root because data paths are
relative to that directory.

## Credentials

Secrets are read from environment variables or a local `.env` file and must
never be committed.

| Variable | Purpose |
|---|---|
| `SPRINGER_API_KEY` | Springer Nature Meta API |
| `ELSEVIER_API_KEY` | Scopus and, when entitled, ScienceDirect APIs |
| `ELSEVIER_INST_TOKEN` | Optional Elsevier institutional token |
| `IEEE_API_KEY` | IEEE Xplore Metadata API |
| `ANTHROPIC_API_KEY` | Batched title and abstract screening |
| `OPENALEX_MAILTO` | Contact email for the OpenAlex polite pool |
| `LLM_MODEL` | Optional model override; defaults to `claude-haiku-4-5-20251001` |

## Repository structure

```text
config.py                    Search protocol, date window, criteria, and settings
connectors/                  API connectors using a shared record schema
  diagnostics/              Low-cost API and query diagnostics
ingest/manual_import.py      BibTeX/CSV import for manually exported sources
pipeline/                    Numbered pipeline stages, executed from 01 to 16
  extras/                    Read-only checks, reports, and calibration sampling
heuristics/                  Manual false-negative review support
data/
  raw/                       Connector outputs; not versioned
  manual_exports/            Manual BibTeX/CSV exports; not versioned
  processed/                 Intermediate and final outputs; not versioned
  heuristic_lists/           Candidate lists for manual reassessment
  initial_search_counts.json Source-level initial counts
supplementary/
  Agentic_AI_Logistics_Supplementary_Dataset.xlsx
                              Public reviewer-facing review dataset
```

The shared raw-record schema is:

```text
source_db, title, authors, year, venue, doi, abstract, url, raw_id, query_used
```

## Search sources

The review covered nine bibliographic sources: ACM Digital Library, IEEE
Xplore, OpenAlex, ScienceDirect, Scopus, SpringerLink, Taylor & Francis, Web of
Science, and Wiley. Some sources were queried by API and others through manual
BibTeX/CSV exports because access and export capabilities differed.

Automated connectors are provided for OpenAlex, Springer, Scopus, IEEE Xplore,
and ScienceDirect. Manual exports are imported according to the filename
prefixes below.

| Filename prefix | Source label |
|---|---|
| `acm_*` | `acm_dl` |
| `wiley_*` | `wiley` |
| `tandf_*` or `taylor_*` | `taylor_francis` |
| `wos_*` | `web_of_science` |
| `sciencedirect_*` or `sd_*` | `sciencedirect` |
| `google_scholar_*` or `scholar_*` | `google_scholar` |

The search string, date window, and protocol criteria are centralized in
`config.py`. Source-specific connectors adapt the same conceptual string only
to the syntax required by each platform.

## Running the collection stage

### API-enabled sources

```bash
python connectors/openalex.py
python connectors/springer.py
python connectors/scopus.py
python connectors/ieee_xplore.py
python connectors/sciencedirect.py
```

The ScienceDirect API may require additional entitlement. When it is not
available, use a manual export and import it with the same workflow as the
other manually accessed sources.

### Manual exports

Place BibTeX or CSV files in `data/manual_exports/`, using one of the prefixes
listed above, and run:

```bash
python ingest/manual_import.py
```

Keep the original BibTeX files available until the pipeline finishes because
the document-type and page-count stages reuse them.

## Numbered pipeline stages

| # | Script | Main output | Purpose |
|---:|---|---|---|
| 01 | `01_build_raw_pool.py` | `raw_pool_no_dedup.csv` | Combines source files without deduplication |
| 02 | `02_check_publication_type.py` | `publication_type_check.csv` | Extracts publication type and flags suspicious titles |
| 03 | `03_apply_impurity_filters.py` | `after_type_filter.csv` | Applies document-type impurity filters |
| 04 | `04_check_language.py` | `language_check.csv` | Detects language from title and abstract |
| 05 | `05_apply_language_filter.py` | `after_language_filter.csv` | Removes confirmed non-English records |
| 06 | `06_llm_title_screening_submit.py` | title batch registry | Submits title batches using fixed instructions |
| 07 | `07_llm_title_screening_retrieve.py` | `title_screening_results.csv` | Retrieves and consolidates title labels |
| 08 | `08_apply_title_filter.py` | `after_title_filter.csv` | Applies title-screening labels |
| 09 | `09_apply_ssrn_retracted_filter.py` | `after_title_filter_clean.csv` | Removes SSRN preprints and retracted records |
| 10 | `10_fetch_missing_scopus_abstracts.py` | enriched title-screened records | Retrieves missing Scopus abstracts |
| 11 | `11_llm_abstract_screening_submit.py` | abstract batch registry | Submits title, venue, and abstract batches |
| 12 | `12_llm_abstract_screening_retrieve.py` | `abstract_screening_results.csv` | Retrieves and consolidates abstract labels |
| 13 | `13_apply_abstract_filter.py` | `after_abstract_filter.csv` | Applies abstract-screening labels |
| 14 | `14_final_combination.py` | `final_combined_deduplicated.csv` | Combines sources and deduplicates by DOI/title |
| 15 | `15_apply_short_paper_filter.py` | `final_after_ec6.csv` | Removes papers of four pages or fewer when page data exist |
| 16 | `16_generate_three_pass_tracking_sheet.py` | `Three_Pass_Tracking.xlsx` | Creates the worksheet for manual three-pass reading |

### Batched title screening

```bash
python pipeline/06_llm_title_screening_submit.py
# wait for the asynchronous batch
python pipeline/07_llm_title_screening_retrieve.py
```

Repeat until the submit script reports that no records remain. Batch registries
and result CSV files allow interrupted runs to resume without relabeling
completed records.

### Batched abstract screening

```bash
python pipeline/10_fetch_missing_scopus_abstracts.py
python pipeline/11_llm_abstract_screening_submit.py
# wait for the asynchronous batch
python pipeline/12_llm_abstract_screening_retrieve.py
python pipeline/13_apply_abstract_filter.py
```

When no abstract is available, the classifier receives the title and venue and
is instructed to exclude the record if the available evidence is insufficient
to confirm all inclusion criteria.

## Complete execution sequence

```bash
# Collection
python connectors/openalex.py
python connectors/springer.py
python connectors/scopus.py
python connectors/ieee_xplore.py
# Add manual exports to data/manual_exports/

# Impurity removal
python pipeline/01_build_raw_pool.py
python pipeline/02_check_publication_type.py
python pipeline/03_apply_impurity_filters.py
python pipeline/04_check_language.py
python pipeline/extras/review_language_flags.py   # optional check
python pipeline/05_apply_language_filter.py

# Title screening
python pipeline/06_llm_title_screening_submit.py
python pipeline/07_llm_title_screening_retrieve.py
python pipeline/08_apply_title_filter.py
python pipeline/09_apply_ssrn_retracted_filter.py

# Abstract screening
python pipeline/10_fetch_missing_scopus_abstracts.py
python pipeline/11_llm_abstract_screening_submit.py
python pipeline/12_llm_abstract_screening_retrieve.py
python pipeline/extras/sample_abstract_decisions.py  # optional check
python pipeline/13_apply_abstract_filter.py

# Combination, deduplication, and manual-reading worksheet
python pipeline/14_final_combination.py
python pipeline/15_apply_short_paper_filter.py
python pipeline/16_generate_three_pass_tracking_sheet.py

# Source-level funnel report
python pipeline/extras/report_per_base_funnel.py
```

## Optional checks and reports

Scripts in `pipeline/extras/` read the available outputs and do not alter the
main workflow.

| Script | Purpose |
|---|---|
| `report_per_base_funnel.py` | Reports source-level counts across search and screening stages |
| `review_language_flags.py` | Lists records marked as non-English before exclusion |
| `sample_titles_for_calibration.py` | Produces the reproducible stratified title pilot |
| `sample_abstract_decisions.py` | Samples abstract-screening labels for inspection |
| `check_ssrn_and_retracted.py` | Previews records targeted by the SSRN/retraction filter |
| `check_abstract_coverage.py` | Reports abstract availability after title screening |
| `check_abstract_recovery_via_dedup.py` | Finds duplicates that may supply missing abstracts |
| `check_short_papers.py` | Previews records targeted by the short-paper filter |
| `diag_scopus_abstract_retrieval.py` | Tests Scopus abstract retrieval for one DOI |

## Manual false-negative reassessment support

The `heuristics/` scripts help researchers inspect candidates that may have
been excluded too early. They retrieve available abstracts, attempt additional
abstract recovery, and assign review priority using transparent term-based
rules. The priority is not an eligibility decision; researchers must read and
decide on each candidate manually.

## Reproducibility notes and limitations

- Raw and processed bibliographic files are not versioned because they may be
  large and may contain database-export content subject to license terms.
- Search results can change when databases update their coverage or APIs.
- ScienceDirect and Scopus API responses depend on institutional entitlement.
- Some manually exported records do not include abstracts. In those cases,
  the abstract-screening stage has less evidence available.
- Publication type and page count are most reliable for BibTeX imports; API
  records may depend on metadata completeness and title-based checks.
- `langdetect` can be unreliable for very short text. Records with fewer than
  60 characters are retained as `unknown` rather than automatically excluded.
- The LLM-assisted labels may vary with model version, provider defaults, and
  instruction wording. The exact model identifier and instructions are kept
  in the source code for auditability.
- The calibration pilot contained 54 manually classified titles, but formal
  diagnostic metrics were not preserved. No quantitative performance claim is
  made for the screening model.
- Final inclusion required manual reading; therefore, the repository should be
  interpreted as a reproducible screening aid, not as an autonomous study
  selection system.

## Data and copyright

The supplementary workbook distributes bibliographic metadata, study-level
codes, quality scores, and analytical mappings. It does not redistribute the
primary-study full texts. Readers should access those publications through the
DOIs and URLs provided in the dataset, subject to the relevant publishers'
copyright and access conditions.