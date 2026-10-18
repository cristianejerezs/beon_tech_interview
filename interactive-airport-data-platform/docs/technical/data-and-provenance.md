# Source data and provenance

[Documentation home](README.md) | [Previous: Architecture and component map](architecture.md) | [Next: Request lifecycle and interpretation contracts](request-lifecycle.md)

Implementation reference: 2026-10-18. See [scope and status](README.md#scope-and-status).

- [Source data, joins, and validation](#source-data-joins-and-validation)
  - [Dataset contracts](#dataset-contracts)
  - [Ordered source schemas](#ordered-source-schemas)
  - [Join relationships](#join-relationships)
  - [Validation pipeline](#validation-pipeline)
- [Snapshot and semantic context](#snapshot-and-semantic-context)
  - [Complete-day evidence](#complete-day-evidence)
  - [Weather units](#weather-units)

## Source data, joins, and validation

### Dataset contracts

| CSV | DuckDB relation | Grain/key | Analytical use |
|---|---|---|---|
| [nyc_flights_fixed.csv](../../source_data/nyc_flights_fixed.csv) | `flights` | Source row identifier, normalized as `column00` | Departure observations, routes, delays, dates, aircraft and airline references |
| [nyc_airports.csv](../../source_data/nyc_airports.csv) | `airports` | `faa` | Airport code/name/reference attributes |
| [nyc_airlines.csv](../../source_data/nyc_airlines.csv) | `airlines` | `carrier` | Airline code-to-name resolution |
| [nyc_planes.csv](../../source_data/nyc_planes.csv) | `planes` | `tailnum` | Manufacturer, model, listed seats and aircraft reference attributes |
| [nyc_weather.csv](../../source_data/nyc_weather.csv) | `weather` | `(origin, time_hour)` | Airport-hour contextual weather observations |

The blank/index column in supplied CSVs is a source-row concern, not an airport code.
**`airports.faa` is the airport code** used by the flight origin/destination joins.
The flight `flight` field is a flight number, not a unique operated-departure identifier.

Required schemas/types and normalization are defined in the data catalog/loader.
Headers must match the catalog's exact ordered columns. Only a blank first header is
normalized to `column00`; extra, missing, renamed or reordered columns are not accepted.
Do not substitute a different public NYC dataset simply because its filename looks similar.
The application answers about these supplied, validated files.

### Ordered source schemas

The following are accepted ingestion shapes, not SQL result schemas. Fractional columns
accept `DOUBLE` or `BIGINT`; ordinary integer columns require `BIGINT`, text requires
`VARCHAR`, and `time_hour` requires `TIMESTAMP WITH TIME ZONE`.

```text
flights:
  column00 BIGINT,
  year BIGINT, month BIGINT, day BIGINT,
  dep_time BIGINT, sched_dep_time BIGINT, dep_delay BIGINT,
  arr_time BIGINT, sched_arr_time BIGINT, arr_delay BIGINT,
  carrier VARCHAR, flight BIGINT, tailnum VARCHAR,
  origin VARCHAR, dest VARCHAR,
  air_time BIGINT, distance BIGINT, hour BIGINT, minute BIGINT,
  time_hour TIMESTAMP WITH TIME ZONE

airports:
  faa VARCHAR, name VARCHAR,
  latitude DOUBLE|BIGINT, longitude DOUBLE|BIGINT,
  altitude BIGINT, timezone BIGINT, dst VARCHAR, timezone_name VARCHAR

airlines:
  carrier VARCHAR, name VARCHAR

planes:
  tailnum VARCHAR, year BIGINT, type VARCHAR,
  manufacturer VARCHAR, model VARCHAR, engines BIGINT,
  seats BIGINT, speed BIGINT, engine VARCHAR

weather:
  origin VARCHAR,
  year BIGINT, month BIGINT, day BIGINT, hour BIGINT,
  temp DOUBLE|BIGINT, dewp DOUBLE|BIGINT, humid DOUBLE|BIGINT,
  wind_dir BIGINT, wind_speed DOUBLE|BIGINT, wind_gust DOUBLE|BIGINT,
  precip DOUBLE|BIGINT, pressure DOUBLE|BIGINT, visib DOUBLE|BIGINT,
  time_hour TIMESTAMP WITH TIME ZONE
```

These contracts deliberately reject arbitrary schema drift. Changing a source column is
a loader/catalog/validation change, not merely replacing a file in the same directory.

### Join relationships

```text
flights.carrier  -> airlines.carrier
flights.origin   -> airports.faa       (origin airport role)
flights.dest     -> airports.faa       (destination airport role)
flights.tailnum  -> planes.tailnum
(flights.origin, flights.time_hour) -> (weather.origin, weather.time_hour)
```

The weather key represents an airport and its exact recorded hour. It is not a nearest-time
or nearest-station match. Weather relationship calculations aggregate departure observations
to airport-hour before calculating equal-hour relationships.

Missing references are measured and disclosed. A missing key, an unmatched reference,
and a known reference with a missing attribute are different states. They must not all
be silently relabeled as the same category.

### Validation pipeline

Validation rejects incompatible source schemas/types, missing or duplicate required grain
keys, duplicate reference keys, duplicate weather airport-hour keys, non-finite measurements,
negative aircraft seat counts, and an empty flight source.

It also records source row counts, column missingness and join coverage. Reference uniqueness
is critical: a duplicate aircraft or weather row could multiply flight observations and make
every downstream count or sum wrong even though SQL executes successfully.

Validation runs before new analytics. Saved report evidence can still be displayed if current
source validation fails, but new execution, source-backed listing expansion, and paging are disabled.
## Snapshot and semantic context

A source snapshot is identified by content fingerprints, not by directory name or modification
time alone. The loader builds a `SnapshotManifest` with checksums, source metadata, row counts,
grain, missingness and reference coverage.

V2 also binds a **semantic context**. It incorporates the snapshot plus catalog/schema rules,
entity aliases, coverage and weather-unit provenance. Two requests over the same CSV bytes can
have different contexts if the interpretation rules or reviewed evidence changed.

| Identifier | Meaning |
|---|---|
| `snapshot_id` | Identity of the loaded source snapshot |
| `context_id` | Identity of source plus relevant semantic/evidence context |
| `request_id` | Analytical request lifecycle identity |
| `revision` | Meaning/scope revision within that lifecycle |
| `report_id` | Persisted report identity |
| `section_id` | One requested analysis within a report |
| `preference_version` | Presentation preference concurrency version, separate from analytical revision |
| `evidence_fingerprint` | SHA-256 of canonical saved visual evidence |

Execution, refinement, listing paging and expanded exports check current snapshot/context
bindings. If they do not match, the app does not quietly recompute a historical report against
new inputs. The analyst must start an explicit new analysis.

### Complete-day evidence

Calendar daily means need more than dates appearing in the data. A date with no records can
mean no flights, an incomplete extract, or a missing file segment.

[coverage.py](../../src/airport_analytics/data/coverage.py) validates a local declaration against
the [coverage schema](../../specs/002-natural-language-exploration/contracts/coverage.schema.json).
Checks include snapshot identity, evidence hashes, origin identities, interval overlap/gaps,
and local evidence availability. Invalid declarations yield unknown completeness plus a warning.

The two denominator bases are:

- `verified_calendar_days`: use reviewed complete-day coverage; do not infer completeness from activity.
- `observed_operating_days`: use dates with recorded scoped activity, only when explicitly selected.

Coverage is scoped to the relevant origins and period. Missing coverage is not permission to
invent zero-activity days. Supporting daily evidence records the chosen basis and day counts.

The declaration's runtime-required top-level fields are `snapshot_id`, `origins`,
`validation` and `documentation`:

- Origin entries include `code`, `covered_intervals` and `gaps`; intervals carry `start`/`end`.
- Validation has nonempty `checks`; each must have `passed=true` and an `evidence_reference`.
- Documentation entries provide a local `reference` and `sha256`.
- References are local files, not URLs, and their hashes must verify.

Use the linked JSON Schema as the complete syntax authority. A syntactically valid declaration
does not prove the extract is complete; review and supporting evidence must be genuine.

### Weather units

[units.py](../../src/airport_analytics/data/units.py) ties weather-unit declarations to the exact
weather content hash and local verification evidence. Expected weather units are temperature
in Fahrenheit, wind speed in mph, precipitation in inches, and visibility in miles.

If units are unverified, current relationship handling can still produce provisional
recorded-value Pearson coefficients with explicit unverified-unit labels. Unit-dependent
precipitation comparisons are omitted/unavailable. This is not a blanket claim that all
weather workflows succeed without unit evidence.

The unit declaration requires exactly these keys:

```text
schema_version, weather_sha256, units, reviewed_by, evidence_reference, evidence_sha256
```

`schema_version` is 1, `weather_sha256` matches the loaded file, and `units` must be:

```json
{"temp":"F","wind_speed":"mph","precip":"inches","visib":"miles"}
```

`reviewed_by` is nonempty. `evidence_reference` points to a local file relative to the
declaration, and `evidence_sha256` must match that file. Missing, malformed or stale evidence
does not become verified merely because the expected unit labels were supplied.

---

[Documentation home](README.md) | [Previous: Architecture and component map](architecture.md) | [Next: Request lifecycle and interpretation contracts](request-lifecycle.md)
