-- Retrieve all patients admitted to a specific department
SELECT patient_id, first_name, last_name, admission_date, discharge_date
FROM patients
WHERE department_id = 10
