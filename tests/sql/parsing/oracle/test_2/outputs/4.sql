-- Find the patient with the longest stay
SELECT patient_id, first_name, last_name, (discharge_date - admission_date) AS stay_days
FROM patients
ORDER BY stay_days DESC
FETCH FIRST 1 ROW ONLY
