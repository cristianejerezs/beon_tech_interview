# Synthetic exploration fixtures

These hand-authored rows are fictional, deliberately small and immutable. They are development
fixtures, not held-out acceptance wording, actual flight records, source-unit provenance or
evidence that the supplied historical snapshot has complete days.

- Flights have unique `column00` IDs. Repeated rows with different IDs are observations, not
  duplicates to delete. N1 flies more often than N2; manufacturers share a model label.
- January 1 repeats a destination; January 2 has two destinations; January 3 has none.
  January 7 is a second Monday with a different destination count.
- The synthetic calendar declares January 1-3 and January 7 complete for JFK only.
  January 4 has observed activity but unknown completeness. January 5 is a known gap.
  LGA has no completeness declaration.
- Weather keys are unique origin/hour timestamps. Multiple flights share an hour. Missing
  weather values, missing delays and unmatched weather are separate cases.
- Seats include known values, a missing seat count and an unmatched tail number.
- Airport ZZZ and airline CC are reference-only; destination XXX lacks a reference name.

Copy files to a test-owned temporary directory before mutation. For invalid-source scenarios,
change a copied ID/key, delay to a nonfinite value, seat value to negative, date, or file bytes.
Never mutate these committed fixtures or `source_data`.
