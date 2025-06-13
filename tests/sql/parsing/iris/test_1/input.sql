-- ignore this split ; and do not split the query
SELECT
    PatientID,
    Name,
    DateOfBirth
FROM Hospital.Patient
WHERE IsActive = 1
;

SELECT
    VisitID,
    VisitDate,
    Department
FROM Hospital."Visit ; Table"
WHERE PatientID = 1234
ORDER BY VisitDate DESC
;

SELECT
    Department,
    COUNT(*) AS VisitCount
FROM Hospital.Visit
GROUP BY Department
ORDER BY VisitCount DESC
;
