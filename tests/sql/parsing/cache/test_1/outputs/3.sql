SELECT
    Department,
    COUNT(*) AS VisitCount
FROM Hospital.Visit
GROUP BY Department
ORDER BY VisitCount DESC
