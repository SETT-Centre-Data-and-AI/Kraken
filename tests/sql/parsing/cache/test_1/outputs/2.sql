SELECT
    VisitID,
    VisitDate,
    Department
FROM Hospital."Visit ; Table"
WHERE PatientID = 1234
ORDER BY VisitDate DESC
