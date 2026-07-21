SELECT TOP 10
    c.cause_name,
    l.location_name,
    m.measure_name,
    met.metric_name,
    f.val
FROM fact_disease_burden f
JOIN dim_cause c ON f.cause_id = c.cause_id
JOIN dim_location l ON f.location_id = l.location_id
JOIN dim_measure m ON f.measure_id = m.measure_id
JOIN dim_metric met ON f.metric_id = met.metric_id;