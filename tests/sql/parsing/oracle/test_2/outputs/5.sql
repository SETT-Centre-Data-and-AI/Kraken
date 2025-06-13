-- Get the count of patients admitted each year
SELECT EXTRACT(YEAR FROM admission_date) AS admission_year, COUNT(*) AS patient_count
FROM patients
GROUP BY EXTRACT(YEAR FROM admission_date)
ORDER BY admission_year
