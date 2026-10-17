with 

destinations AS (
    SELECT
    concat(year, ' - ', month, ' - ', day) AS flight_date,
    origin,
    destination
    FROM  nyc_flights_fixed
)

SELECT 
    origin,
    COUNT(destination) AS num_destinations,
    ROUND(COUNT(DISTINCT flight_date)/COUNT(DISTINCT destination), 2) AS avg_destinations
FROM destinations
GROUP BY origin


