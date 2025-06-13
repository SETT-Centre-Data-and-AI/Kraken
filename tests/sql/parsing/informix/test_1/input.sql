-- Retrieve all patients admitted to a specific department
SELECT patient_id, first_name, last_name, admission_date
FROM "patients"
WHERE department_id = 5;

-- Find the total number of patients admitted to the hospital
SELECT COUNT(*) AS total_patients
FROM patients;

-- List all departments with the number of patients admitted
SELECT department_id, COUNT(*) AS patient_count
FROM patients
GROUP BY department_id;

-- Find the most recent admission date
SELECT MAX("admission_date") AS latest_admission
FROM "patients";
