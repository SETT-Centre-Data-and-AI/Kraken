-- Ignore this ; as in a comment
SELECT
    p.patient_id,
    p.first_name,
    p.last_name,
    d.diagnosis_name,
    t.treatment_name,
    m.medication_name,
    COUNT(*) AS treatment_count,
    SUM(CASE WHEN m.medication_name LIKE '%antibiotic%' THEN 1 ELSE 0 END) AS antibiotic_usage,
    AVG(TIMESTAMPDIFF(DAY, v.visit_date, CURDATE())) AS avg_days_since_visit
FROM
    patients p
JOIN
    visits v ON p.patient_id = v.patient_id
JOIN
    diagnoses d ON v.visit_id = d.visit_id
LEFT JOIN
    treatments t ON d.diagnosis_id = t.diagnosis_id
LEFT JOIN
    `medication;table` m ON t.treatment_id = m.treatment_id
WHERE
    v.visit_date BETWEEN '2024-01-01' AND '2024-12-31'
    AND d.diagnosis_name IN ('Diabetes', 'Hypertension', 'Pneumonia')
GROUP BY
    p.patient_id, d.diagnosis_name
HAVING
    COUNT(*) > 2
ORDER BY
    avg_days_since_visit DESC
;

SELECT patient_id, first_name, last_name, date_of_birth
FROM patients
ORDER BY last_name ASC
;

SELECT visit_id, visit_date, visit_reason
FROM visits
WHERE patient_id = 12345
ORDER BY visit_date DESC
;

SELECT medication_name, dosage, frequency
FROM medications
WHERE visit_id = 67890
;
