# Analytics engine and metric semantics

[Documentation home](README.md) | [Previous: Request lifecycle and interpretation contracts](request-lifecycle.md) | [Next: Model integration, token usage, and budgets](hosted-inference.md)

Implementation reference: 2026-10-18. See [scope and status](README.md#scope-and-status).

- [Analytical operations and exact meanings](#analytical-operations-and-exact-meanings)
  - [Operation inventory](#operation-inventory)
  - [Counts that must not be confused](#counts-that-must-not-be-confused)
  - [Dimensions and compatibility](#dimensions-and-compatibility)
  - [Daily destination means](#daily-destination-means)
  - [Daily seat capacity](#daily-seat-capacity)
  - [Departure delay](#departure-delay)
  - [Time grain and comparison](#time-grain-and-comparison)
  - [Manufacturer and model](#manufacturer-and-model)
  - [Relationships and weather](#relationships-and-weather)
  - [Metric authority](#metric-authority)
- [Query compilation and execution](#query-compilation-and-execution)
  - [Compilation](#compilation)
  - [Execution](#execution)
  - [Browsing and expanded export](#browsing-and-expanded-export)

## Analytical operations and exact meanings

### Operation inventory

| Operation ID | Main purpose | Typical family |
|---|---|---|
| `aggregate` | Counts, distinct counts, means, grouping and ranking | overall/grouped summary, ranking, category comparison, historical trend |
| `entity_list` | Unique entities or reference/observed airport populations | unique entity list |
| `flight_records` | Bounded individual flight browsing | individual records |
| `period_change` | Compare explicitly defined periods | period change |
| `distribution` | Bounded numeric bin counts | distribution |
| `flight_relationship` | Relationship between approved numeric flight fields | numeric relationship |
| `daily_distinct_mean` | Mean of per-date distinct destination counts | summary/grouped/category/ranking |
| `departure_delay_total` | Positive or explicitly requested net delay totals | summary/grouped/ranking/category/trend |
| `daily_capacity_mean` | Mean daily known-reference seat capacity | ranking/grouped/category |
| `aircraft_frequency` | Manufacturer/model counts under an explicit aircraft/frequency measure | ranking/grouped/category |
| `weather_relationship` | Fixed four-variable airport-hour weather panel | numeric relationship |

The catalog is authoritative for exact allowed combinations. Similar display families do
not imply interchangeable operations. For example, an ordinary aggregate mean cannot
substitute for the mean of daily distinct counts.

### Counts that must not be confused

| Measure/concept | Calculation and interpretation |
|---|---|
| `flight_count` | Count source flight records; one record is one recorded departure observation. |
| `distinct_flight_number_count` | Distinct `(carrier, flight)` pairs; repeated dates/routes do not add new flight numbers. |
| `distinct_destination_count` | Distinct outbound destination codes in the scoped flight records. |
| `distinct_connected_airport_count` | Distinct neighboring airports in either direction; no self-connections or missing endpoints. |
| `distinct_aircraft_count` | Distinct aircraft identity under its catalog definition; inspect reference-match semantics. |
| `distinct_tailnums` | Distinct matched aircraft tail numbers, used for manufacturer/model rankings. |
| `explicit_flight_frequency` | Matched-aircraft flight records, not unique aircraft. |

For a complete airline ranking by distinct flights, use the distinct flight-number measure
and include every airline, not the default top ten. This is not the number of operated
departures and not a daily distinct count summed across dates.

Connected-airport analysis uses the `airport` role to represent either endpoint.
It is different from grouping outbound destination counts by `origin`. Reference-airport
lists can include catalog airports with zero recorded connections; that requires the
appropriate `entity_list`/`airport_connections` population rather than changing a flight aggregate.

### Dimensions and compatibility

The V2 dimension vocabulary is `airport`, `origin`, `destination`, `carrier`, `airline_name`,
`tailnum`, `aircraft_manufacturer`, `aircraft_model`, `weather_precipitation_band`,
`flight_date`, `flight_week`, `flight_month`, `month_of_year`, and `weekday`.

These are approved identities, not universally compatible roles. For example:

- Connected-airport aggregate allows `airport`, date/week/month, carrier or airline name.
- Daily distinct destinations allows `origin` and/or `weekday`.
- Daily capacity requires carrier or airline name, optionally origin.
- Aircraft frequency requires the manufacturer or model role under its operation rules.
- Weather relationship permits origin breakdown, not arbitrary categorical grouping.
- Carrier and airline-name roles are not both added to express the same identity.

Keep operation-specific validation in place when exposing dimension choices in the UI.

### Daily destination means

For each eligible date `d`, calculate:

```text
C(d) = number of distinct destination codes among scoped flights on date d
daily mean = sum of C(d) / number of eligible dates
```

For weekday means, calculate the daily counts first, then average the date-level values
within each weekday. A destination appearing on several dates is counted once on each date;
a pooled distinct count over all Mondays is a different calculation.

The report states whether eligible dates are verified calendar days or observed operating
days. Optional half-up whole-number rounding is a display transformation of the final mean,
not permission to round intermediate daily calculations.

### Daily seat capacity

Daily capacity sums the listed aircraft seats once per scoped recorded departure, using
`tailnum` to join aircraft references. It then averages daily totals over the chosen eligible
days. **The implementation shares the scoped observed-date denominator across non-origin
categories, including airlines.** Once a date is eligible, an airline absent on that date
contributes zero. If grouped by origin, eligibility is evaluated per origin. This is not
necessarily the same as each airline's own nonzero operating-day mean.

Verified-calendar eligibility likewise uses the intersection of verified dates across selected
origins for non-origin grouping, or each origin's own verified dates when origin-grouped.
Eligible category/date grid cells without observations contribute zero; unknown dates do not
become verified calendar dates.

Unknown aircraft/seat information is excluded and disclosed. This is known-reference,
scheduled-capacity evidence, not booked seats, remaining availability, occupancy, or proof of
the aircraft's historical seat configuration.

### Departure delay

- `mean_departure_delay`: average known departure delay values.
- `positive_delay_minutes`: sum of positive delays; early departures contribute zero.
- `net_delay_minutes`: signed total; early departures can offset lateness.
- Missing delay values are not silently converted to observed zero delay.

An accumulated-delay ranking must not be implemented as an average-delay ranking.

### Time grain and comparison

`flight_month` means separate calendar year-months. `month_of_year` pools January through
December across the scoped years. They are different questions even when the current data
contains only one year.

Period comparison carries baseline and comparison endpoints. Supported previous-period rules
are calculated locally; the model must not invent wall-clock-based dates for a historical
snapshot. Zero/undefined comparison denominators and unavailable evidence are disclosed rather
than reported as arbitrary percentages.

### Manufacturer and model

The usual "most common manufacturer/model" measure counts distinct matched tail numbers,
not how often an aircraft flew. Manufacturer-qualified model identities prevent similarly
named models from different manufacturers from being combined incorrectly.

A ranking weighted by flights is a valid different analysis only when explicitly selected.
Missing tail numbers and unmatched aircraft references are separately important exclusions.

### Relationships and weather

Flight relationships use approved numeric pairs, pairwise eligibility/missingness and bounded
saved pair/density evidence. Correlation is undefined when its required sample/variance checks
fail; a chart is not permission to fabricate a coefficient. Weather Pearson requires at
least three complete pairs and nonzero variance on both axes. Fewer pairs produce
`insufficient_pairs`; a constant axis produces `constant_axis`.

Pair evidence stores all valid pairs up to 5,000. Above that limit it stores a density grid,
with at most 20 by 20 bins and counts reconciling to the full valid pair population.
This is an evidence representation change, not a random sample or a coefficient calculated
only on chart points.

`weather_relationship` owns a fixed panel of temperature, wind speed, precipitation and
visibility. Its input measure is `mean_departure_delay`, not four extra arbitrary measure IDs.
It uses `pairing=null`; weather fields are not a flight-field pair.

Flights are matched to weather by origin and recorded hour. Known departure delay values are
averaged per origin-hour, then each eligible hour contributes equally to the Pearson
relationship for the weather variable. This avoids weighting one hour multiple times just
because it had more flights. Origin-specific output is only requested when the scope asks for it.

Weather association is contextual, **not causal**. Missing weather, missing weather variables,
unverified units, small samples and constant series affect what can be reported.

### Metric authority

The production catalog, deterministic query compiler and independent test oracles define
analytical behavior. In particular, a ratio of distinct dates to distinct destinations is
not the mean daily destination count. Validate new analyses against those definitions,
not merely against a similarly named standalone query.

## Query compilation and execution

### Compilation

`CompiledQuery` includes SQL, positional parameters, purpose and expected output columns.
V1 uses `compile_analysis_plan`; V2 uses summary/listing/daily/distribution/pair/weather
compiler paths as appropriate.

The compiler derives required joins from approved metrics, grouping, filters and sorting.
Scope/evidence queries must use the same predicates as result queries. A correct aggregate
with mismatched supporting scope is still an incorrect report.

### Execution

The executor loads a validated in-memory analytical context, runs compiled read-only queries,
checks declared output columns, and enforces bounds and timeout handling.
The default query timeout is 30 seconds; timeout interrupts the query and surfaces a typed
error. The default model timeout is separate, at 60 seconds.
The executor serializes access to its single in-memory DuckDB connection with a re-entrant
process lock. It is not a connection pool. The interrupt timer acts while execution holds
that lock; callers sharing the executor queue rather than running simultaneous queries.

Scalar, grouped and ranking results retain observation/scope evidence, available versus
returned group counts and applicable tie information. Table truncation must be disclosed.
Source/reference match counts support limitation statements.

### Browsing and expanded export

Listings are not unbounded saved result sets. They have a total population count plus a
bounded saved preview. Paging and larger bounded exports execute against the current pinned
snapshot/context and deterministic ordering.

An out-of-range page can reset to page one with a notice. Export preparation checks that its
population and binding have not changed. A report/revision/scope/order-bound selection hash
prevents a confirmation for one population from authorizing a different export.
Page numbers are one-based. Public browsing accepts page sizes 25, 50, 100 or 500, with
100 as the default.

The allocated listing bundle UI allows a **combined maximum of 10,000 rows**, with explicit
per-section allocations. Partial populations require confirmation. A saved preview export
does not imply that every matching flight was exported.

---

[Documentation home](README.md) | [Previous: Request lifecycle and interpretation contracts](request-lifecycle.md) | [Next: Model integration, token usage, and budgets](hosted-inference.md)
