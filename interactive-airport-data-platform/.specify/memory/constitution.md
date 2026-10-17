<!--
Sync Impact Report
Version change: 1.0.0 -> 2.0.0 (replaced exercise restrictions with question-driven report authorization)
Modified principles:
- V. Candidate Ownership and Responsible Coaching -> V. Question-Driven Analysis and Explainability
Added sections: None
Removed sections: None
Follow-up TODO: Confirm the original ratification date and replace its TODO marker.
-->
# Interactive Airport Data Platform Constitution

## Core Principles

### I. Defensible Analytical Correctness
Every reported metric MUST state its unit of analysis, population, time period, numerator and
denominator where applicable, and material exclusions. Analysis MUST distinguish counts, rates,
and averages, and MUST NOT present a result whose definition or interpretation cannot be explained.
This makes findings verifiable and suitable for interview discussion.

### II. Explicit Grain and Data Integrity
Before combining sources or aggregating records, contributors MUST establish the grain and keys of
each input and check for join fan-out, duplicate records, missing values, and incompatible codes
that could change the result. Transformations MUST preserve source meaning, and assumptions about
uncertain fields MUST be documented rather than silently treated as facts.

### III. Reproducible and Explainable Work
Analytical steps MUST be traceable to identified inputs and documented transformations. SQL,
Python, and report logic MUST use clear names and structure that let another person follow how an
output was derived. When an environment or data limitation prevents reproduction, the limitation
MUST be stated explicitly.

### IV. Honest, Decision-Useful Communication
Tables and visualizations MUST identify metric units and relevant time periods. Comparisons MUST
account for materially different volumes or sample sizes, and chart choices MUST not distort the
finding. Conclusions MUST separate observed results from assumptions and MUST state relevant
limitations; unsupported causal claims are prohibited.

### V. Question-Driven Analysis and Explainability
The platform MUST accept an analyst's natural-language question and generate a report that answers
it using relevant available data. Reports MAY include complete analytical answers, calculations,
comparisons, and visual summaries; the platform MUST NOT withhold a result solely because it
relates to an assessed exercise. Reports MUST distinguish data-backed findings from assumptions
and limitations, and MUST explain relevant analytical terms concisely when they arise, without
requiring the analyst to ask. This enables direct, question-led exploration while keeping results
interpretable and accountable.

## Data, Privacy, and Tooling Constraints

Contributors MUST inspect the available data and project instructions before assuming a schema,
SQL dialect, metric definition, or source quality. Source data MUST NOT be represented as verified
when it has not been checked. Personally identifiable information MUST be minimized and MUST NOT
be exposed in examples or outputs unless the task explicitly requires it and handling is
appropriate. No specific SQL engine, Python library, or visualization tool is mandated; choices
MUST be compatible with the available data and disclosed where they affect interpretation.

## Development Workflow and Quality Gates

Plans and changes MUST identify the analytical question and expected output grain before
implementing transformations or visuals. Contributors MUST validate relevant assumptions with
appropriate checks, such as row counts before and after joins, duplicate and null checks, boundary
cases, or reconciliation against source totals. Review MUST confirm that metric definitions,
filters, and visual labels agree with the implemented logic. Any unverified check or known
limitation MUST be reported rather than presented as a successful validation.

## Governance

This constitution governs project analysis and development guidance. Amendments MUST be reviewed
and recorded in this file. Changes that remove or redefine a principle incompatibly require a
MAJOR version increment; new principles or materially expanded requirements require MINOR; wording
clarifications and non-semantic corrections require PATCH. Version numbers use
MAJOR.MINOR.PATCH. The constitution version and amendment date MUST be updated with each amendment.
An unknown original ratification date MUST remain explicitly marked until confirmed.

Every feature plan and change review MUST check applicable principles, data integrity, and the
quality gates above. Any deviation MUST be justified in the relevant proposal or review, including
its impact and mitigation. Reviewers MUST request correction or an explicit, documented exception
when a change fails a requirement. This constitution takes precedence over conflicting project
guidance; supporting instructions may add detail but MUST NOT weaken these rules.

**Version**: 2.0.0 | **Ratified**: TODO(RATIFICATION_DATE): confirm original adoption date | **Last Amended**: 2026-10-17
