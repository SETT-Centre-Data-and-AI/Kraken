-- ignore this split ; and do not split the query
SELECT
    PatientID,
    Name,
    DateOfBirth
FROM Hospital.Patient
WHERE IsActive = 1
