# Draft Plan: Interactive Airport Data Platform

## Problem and proposed approach

Turn the airport exercise from a set of required charts into an interactive experience that helps non-technical users explore airport operations and understand what each metric means. Organize the interface around user questions, use plain-language labels and metric definitions, and make filters and drill-down behavior clear. Keep analysis decisions and assumptions transparent so the candidate can explain the work in the interview.

The repository currently contains the five source CSVs, the exercise brief, and a starter SQL file, but no dashboard implementation or selected platform. Do not implement until the user confirms scope and platform. The candidate must construct and defend the assessed SQL and analytical logic; support should remain within the exercise's AI-use restrictions.

## Proposed work

1. Confirm intended audience, platform, and scope.
2. Inventory available sources and decide (with the candidate) the grain, joins, time handling, and definitions required by each exercise metric. Do not supply finished exercise queries or metric results.
3. Plan an information architecture for the dashboard: an overview plus focused views for connectivity, delays/weather, airlines, and aircraft.
4. Design accessible interactions such as well-labeled filters, tooltips with plain-language definitions, sensible drill-downs, and visible time period/units.
5. Implement only after the user explicitly approves the plan and platform; keep candidate-authored analysis logic separate from any interface scaffolding.
6. Validate data relationships, metric behavior, and interactions against candidate-defined expectations, and review whether a non-technical user can interpret the views.

## Open decisions to confirm before finalizing

- **Audience:** Is the primary user airport management, general/non-technical stakeholders, or both?
- **Platform:** Should this be built in Power BI (closest to the exercise's BI recommendation), or as a custom interactive app such as Streamlit? Is another platform preferred?
- **Scope:** Should the platform present only the ten requested exercise metrics, with more usable exploration, or include additional analyses?
- **Interactivity:** Which user controls matter most (for example date range, airline, destination, weekday, or weather conditions)?
- **Candidate ownership:** Confirm that the candidate will write and interpret the SQL/metric logic, while assistance focuses on coaching, UX, and permitted implementation support.

## Notes and constraints

- Treat Newark (EWR) as the focal airport unless the brief or user clarifies otherwise.
- The local flights source is named `nyc_flights_fixed.csv`, while the brief refers to `nyc_flights.csv`; verify source alignment before analysis.
- Any dashboard should state metric definitions, filters, time coverage, and relevant data limitations rather than hiding assumptions.
- Do not create finished exercise queries, calculated answers, or an end-to-end analytical solution.
