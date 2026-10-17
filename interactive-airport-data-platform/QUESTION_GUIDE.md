# How to ask successful airport analytics questions

Use this guide with the [quickstart](QUICKSTART.md). Examples describe supported
analysis requests, not guaranteed model responses. Model interpretation can still fail;
always review the generated report's metric, filters, period, and limitations.

## 1. Use a specific question structure

> For [origin airport] during [period], calculate [one metric], broken down by
> [optional grouping], with [optional filter or ranking].

Include:

- **Airport:** use `EWR`, `JFK`, or `LGA` for an origin, or explicitly request all three.
  Avoid "the airport" unless refining a report that already identifies it.
- **Period:** use 2013 or specific dates within the historical snapshot. ISO dates
  such as `2013-01-01` avoid date-format ambiguity. This is not live flight data.
- **Metric:** ask for one measure per question, such as flight count or mean departure delay.
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

## 3. Choose supported metrics and breakdowns

| Metric | Meaning | Supported breakdowns |
|--------|---------|----------------------|
| Flight count | Count of matching flight records, not passengers or necessarily completed flights | Any breakdown listed below |
| Distinct destination count | Count of distinct destination codes among matching flight records | Origin airport, month |
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
- Provider authentication, connection, rate-limit, and budget errors cannot be fixed
  by better question wording. See [quickstart troubleshooting](QUICKSTART.md).
- No matching records does not prove there were no real-world flights; check the
  snapshot scope, exact codes, dates, and filters.

Live model acceptance evaluation remains pending. These examples align with the
application catalog; they are not a claim that every configured model has passed them.
