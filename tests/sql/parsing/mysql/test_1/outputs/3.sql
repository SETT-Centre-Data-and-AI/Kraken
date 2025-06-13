SELECT visit_id, visit_date, visit_reason
FROM visits
WHERE patient_id = 12345
ORDER BY visit_date DESC
;
