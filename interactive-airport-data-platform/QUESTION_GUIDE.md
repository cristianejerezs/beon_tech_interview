# How to ask successful airport analytics questions

Use this guide with the [quickstart](QUICKSTART.md). Examples describe supported
analysis requests, not guaranteed model responses. Model interpretation can still fail;
always review the generated report's metric, filters, period, and limitations.
Reports display the submitted question as a level-two heading before the answer;
PDF exports place it directly beneath the report title.

## 1. Use a specific question structure

> For [origin airport] during [period], calculate [one metric per section], broken down by
> [optional grouping], with [optional filter or ranking].

Include:

- **Airport:** use `EWR`, `JFK`, or `LGA` for an origin, or explicitly request all three.
  Avoid "the airport" unless refining a report that already identifies it.
- **Period:** use 2013 or specific dates within the historical snapshot. ISO dates
  such as `2013-01-01` avoid date-format ambiguity. This is not live flight data.
- **Metric:** ask for one measure per section, such as flight count or mean departure delay.
  V2 accepts up to four related, explicitly labelled analyses in one report.
- **Breakdown:** state whether you want one total, results by airline, or a monthly trend.
- **Ranking:** say what "top" means, how many results you want, and the direction.
  For example, "top 5 destinations by flight count, highest first."

Ask in English. Keep the question between 1 and 2,000 characters after trimming.
Do not include credentials, passenger information, or other sensitive data. A selected
hosted provider receives the question and, for refinement, the active report's question
and analysis plan.

## 2. Start with these examples

| Goal | Example question |
|------|------------------|
| Count connected destinations | How many distinct destination airports appear in flights departing from JFK in 2013? |
| Compare connectivity | For each origin airport, EWR, JFK, and LGA, how many distinct destinations appear in 2013? |
| Count flights | How many flight records departed from EWR in 2013? |
| Rank destinations | What were the top 5 destinations from LGA by flight count in 2013, highest first? |
| Compare airlines | For flights departing from JFK in 2013, show mean departure delay in minutes by carrier, highest first. |
| Analyze arrivals | What was the mean arrival delay for flights from EWR to ORD in 2013? |
| Show a monthly trend | Show mean departure delay by month for flights departing from EWR in 2013. |
| Apply a numeric filter | How many flight records from JFK in 2013 had a departure delay greater than 15 minutes? |
| Analyze route distance | What was the mean route distance in miles by destination for flights from LGA in 2013? |
| Count aircraft | How many distinct aircraft tail numbers appear in flights from JFK in 2013? |
| Group aircraft activity | Show the number of distinct aircraft tail numbers by aircraft manufacturer for flights from JFK in 2013. |
| Analyze listed seats | What was the mean listed aircraft seat count for matched flight records from EWR in 2013? |
| Explore weather context | For flights from EWR in 2013 with matched weather, show mean departure delay by origin-hour precipitation band. |

Airport codes in the destination position, such as `ORD`, are destination filters,
not additional supported origin airports. A destination must occur in the supplied
flight data to produce matching results.

## 3. V2 analytical requests

V2 is on by default. Examples include:

- "For JFK in 2013, count distinct destinations, calculate rounded average daily distinct
  destinations, show those daily averages by weekday, and identify the busiest month by flights."
- "Compare mean departure delay in January and February 2013 at JFK."
- "Compare flight counts for March 2013 with the previous month."
- "Show the departure-delay distribution for LGA in 2013."
- "Show the relationship between departure and arrival delays from JFK in 2013."
- "Rank airlines by average daily recorded seat capacity from JFK in 2013."
- "Across all origins combined, average the per-date distinct destination counts over
  observed operating days only, rounded half up to a whole number."
- "Across all origins combined, average daily distinct destinations separately for
  each weekday, using observed operating days only."
  Explicit observed-day requests use only dates with recorded scoped flights. Without
  that selection, daily means still require verified calendar coverage; unknown
  dates are not silently included as zeros.
- "Rank all airlines by the number of distinct flight numbers they operate across all recorded dates."
  This counts each flight number once within its airline, regardless of departure date,
  origin or destination. It is not a count of recorded departures. Requests for flight
  counts without this distinct-flight-number definition continue to count source records.
- "Count distinct observed aircraft by manufacturer and model, not flight frequency."

Daily/weekday means require reviewed complete-day coverage. Without it, a calendar mean is
unavailable. Use **Edit analytical definition** to explicitly choose observed operating days;
that is a different, provisional denominator, not inferred completeness. Known-seat capacity
excludes unknown seat contributions and is a lower-bound proxy, not passenger throughput.
Weather requests use equal-weight origin-hours. Without verified local weather units, Pearson
coefficients use recorded numeric values and are labelled provisional; no physical units are
inferred and unit-dependent precipitation-band comparisons are omitted. Coefficients describe
association, never causality or significance.

V2 supports at most two grouping roles per section. It includes daily, Monday-week and monthly
chronological groups; period changes have inclusive endpoints and application-owned previous
equal-day/month/year rules. Distributions use anchored equal-width bins. A proposed wider bin
must be accepted explicitly when the initial definition exceeds 100 bins.
Width proposals respect the query timeout. Ranges or widths that cannot produce exact,
finite bin indexes and edges require a different width or narrower scope; they are not
silently rounded, coarsened or sampled.

### Airport counts and readable report details

"Count distinct destinations for each origin airport" groups the recorded flights
by origin and counts distinct destination codes. The supplied NYC flight file has
only EWR, JFK and LGA as departure origins; the larger airport reference catalogue
does not add departure observations for its other airports. Their worldwide
outgoing connections cannot be inferred from this dataset.

V2 reports display readable calculation details under "How this was calculated"
and scope/missingness under "Scope and data quality", rather than raw JSON.
Exact result tables and CSV evidence retain their original values and field IDs.

"Determine the number of distinct destinations connected to all airports" ranks every
airport that appears as an origin or destination (FAA code from the airport catalogue)
by its distinct connected airports in either flight direction, and shows a bar chart.
Each flight links both endpoints, so EWR counts its destinations and a destination such
as ATL counts the NYC origins that serve it. In Edit interpretation, choose the
"distinct connected airport count" measure and the "airport" group to get this view;
"airport" can also group flight count (flights departing from or arriving at the airport).

For a catalogue-wide connection table, ask:

> For every airport in the airport catalogue, count distinct neighbouring airports
> across both arrivals and departures. Include airports with no recorded connections.

This left-joins the catalogue to the union of recorded origin/destination edges.
Each neighbour counts once regardless of flight frequency or direction; self-connections
and missing endpoints are excluded. An observed neighbour code without reference metadata
still counts as a connection, but does not create an additional catalogue row.
Zero means no connection observed in the selected file, not no real-world service.
Airport-code filters choose catalogue rows; date/carrier/other flight filters restrict
the flights used to form edges while preserving zero-connection catalogue rows.
Use listing paging to inspect every airport or prepare a full CSV within the
existing 10,000-row listing limit. This is separate from outgoing-only distinct
destination counts and does not silently replace them.

"Identify the month with the highest accumulated departure delay" ranks calendar
months by total positive departure-delay minutes, not average delay or the largest
individual delay. Early departures contribute zero; missing delays are excluded
and disclosed. Explicitly request "net departure delay" if early departures should
offset lateness. Highest/lowest selects one ranked month with tie disclosures.

"Identify the month of the year with the highest accumulated departure delay for all years"
instead pools all Januaries, all Februaries, etc. (`month_of_year`, codes 01-12 with month
names), then ranks their total positive delay. Calendar-month rankings (`flight_month`,
YYYY-MM) keep each year separate. This grouping is also available for compatible counts,
means and other summary measures; it is not a fixed-question shortcut. Filters still define
the years included. Only years actually present contribute: a one-year snapshot may produce
the same winning total under either grouping, without making their meanings equivalent.

Weather/departure-delay correlation is one fixed analytical panel: temperature,
wind speed, precipitation and visibility against mean departure delay at equal
origin-hour grain. It is not a flight-level correlation or causal conclusion.
Valid local transformed-weather unit provenance is required for physical unit labels and
precipitation-band comparisons, not for provisional Pearson coefficients on recorded values.
Pearson is dimensionless and invariant to positive linear unit conversions; consistent scales
and meaningful numeric values are still assumptions, not verified facts.
The answer explains each coefficient's direction, valid-hour count and the largest absolute
association among available variables. These findings appear before technical metadata in
the PDF, and are also derived from saved evidence when opening older weather reports.
Provider interpretation can still fail strict local validation; no invalid response is executed or
automatically retried.

Several sections resolve before any main analysis executes. Clarifications are focused, with
at most three answered unresolved turns per section, then structured correction/removal/restart.
More than four requested analyses require an explicitly confirmed subset; excluded work never
runs automatically. For saved composite reports, choose a section or **All sections** in the
local scope-refinement form. Presentation preferences do not edit analytical evidence.

### Legacy V1 metrics and breakdowns

The following compatibility table applies when the V2 toggle is turned off:

| Metric | Meaning | Supported breakdowns |
|--------|---------|----------------------|
| Flight count | Count of matching flight records, not passengers or necessarily completed flights | Any breakdown listed below |
| Distinct destination count | Count of distinct destination codes among matching flight records | Origin airport, month |
| Distinct connected airport count | Count of distinct other airports (FAA codes) linked by at least one flight in either direction | Airport (origin or destination), airline, month |
| Mean departure delay | Average recorded departure delay in minutes | Any breakdown listed below |
| Mean arrival delay | Average recorded arrival delay in minutes | Any breakdown listed below |
| Mean distance | Average recorded route distance in miles | Any listed breakdown except aircraft manufacturer and aircraft model |
| Aircraft activity count | Count of distinct non-missing aircraft tail numbers | Any breakdown listed below |
| Mean aircraft seats | Mean listed seat count across matched flight records with known seats | Any breakdown listed below |
| Mean delay by weather context | Mean departure delay among records with an exact origin/hour weather match | Precipitation band, origin airport, month |

Available breakdowns:

- Origin airport or destination airport.
- Carrier code or airline name.
- Aircraft tail number, manufacturer, or model.
- Flight month.
- Matched origin-hour precipitation band.

Use no more than four breakdowns in one question; start with one for clarity.
For distinct destination counts, do not request an airline or destination breakdown.
To rank destinations instead, ask for **flight count by destination**.

### Filters

Supported filters include origin, destination, carrier code, airline name, tail number,
aircraft model, year, month number, flight date, departure delay, arrival delay, and distance.

- Use codes when possible: "origin JFK", "destination ORD", or "carrier UA".
- Spell out date ranges, for example "from 2013-06-01 through 2013-06-30".
- Use explicit numeric comparisons, for example "arrival delay greater than 30 minutes".
- Use text equality or lists, for example "origins EWR and JFK"; avoid fuzzy name searches.
- Manufacturer and precipitation band are available as breakdowns, but are not direct
  filter fields in the current catalog.

## 4. Replace ambiguous wording

| Avoid | Prefer |
|-------|--------|
| Determine the number of distinct destinations connected to the airport. | How many distinct destinations appear in flights departing from JFK in 2013? |
| Which airport is best? | Compare EWR, JFK, and LGA by mean departure delay in 2013, lowest first. |
| Show the busiest routes. | Show the top 10 destinations from EWR by flight count in 2013, highest first. |
| Show delays. | Show mean arrival delay in minutes by carrier for flights departing from LGA in 2013. |
| What happened last month? | Show flight count by destination for flights from JFK during June 2013. |
| How many passengers flew from JFK? | How many flight records departed from JFK in 2013? |
| Did rain cause delays? | Show mean departure delay by matched precipitation band for EWR in 2013; describe association only. |

Passenger counts cannot be inferred from listed seats. Similarly, an observed destination
is not proof of a currently scheduled connection.

## 5. Refine an existing report

1. Generate a successful report or open one from saved history.
2. Check the refinement-target caption to confirm the intended report is selected.
3. Enable **Refine the currently displayed report's scope**.
4. Enter a specific follow-up and select **Generate report**:
   - "Keep the same metric, but only include flights from EWR."
   - "Keep the same origin and metric, but restrict dates to June 2013."
   - "Keep the same filters, but show the result by month."
5. Verify the resulting scope. A new breakdown must still be compatible with the metric.

The refinement control is disabled until a report is available. Without refinement
enabled, write a self-contained question; do not assume arbitrary earlier conversation
is available to the model.

If the app requests clarification, resubmit a complete question incorporating the
answer, such as "Count distinct destinations from JFK in 2013", rather than only "JFK".

## 6. Understand limitations and failures

- The closed catalog does not support arbitrary SQL, live arrivals, forecasts, ticket
  prices, passenger counts, revenue, or arbitrary new metrics. Ask separate questions
  for multiple metrics. Median, percentile, and rate calculations are not current metrics.
- Negative delays indicate early departures or arrivals. Missing delay values are
  excluded from their averages, not treated as zero.
- Aircraft seat averages count repeated aircraft once per matching flight record.
  They are not a unique-aircraft fleet average or actual passenger occupancy.
- Weather comparisons exclude unmatched records for the weather-context metric.
  They do not establish causation.
- Results are bounded to at most 500 rows. Request a smaller ranking or a coarser
  breakdown rather than an unlimited extract.
- A plan-format or unsupported-grouping error means the model response was rejected
  before query execution. Simplify the request and use a compatible metric/breakdown.
  This is not necessarily an authentication failure.
- An empty date-range error is a model-output defect, not a problem with a question
  that already supplies a year. Date ranges must contain at least one date, or be
  `null` when unused. The structured-output schema disallows two null endpoints.
  As a diagnostic, spell out "from 2013-01-01 through 2013-12-31".
  Groq's wire schema requires both dates when a range is present; open-ended requests
  use date comparison filters instead. Local validation still accepts one-sided ranges.
- Provider authentication, connection, rate-limit, and budget errors cannot be fixed
  by better question wording. See [quickstart troubleshooting](QUICKSTART.md).
- No matching records does not prove there were no real-world flights; check the
  snapshot scope, exact codes, dates, and filters.

Live model acceptance evaluation remains pending. These examples align with the
application catalog; they are not a claim that every configured model has passed them.
