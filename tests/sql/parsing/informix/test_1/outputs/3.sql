-- List all departments with the number of patients admitted
SELECT department_id, COUNT(*) AS patient_count
FROM patients
GROUP BY department_id;
