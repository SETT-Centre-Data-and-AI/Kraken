-- List all departments with their total patient count
SELECT department_id, COUNT(*) AS patient_count
FROM patients
GROUP BY department_id
