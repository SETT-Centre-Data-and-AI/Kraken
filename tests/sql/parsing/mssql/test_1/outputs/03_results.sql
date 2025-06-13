
--$DataFrame = Results
-- ignore the ; in this comment
DECLARE @HospitalNo VARCHAR(10) = 'a_test_no;'

SELECT  *
FROM    a_database.a_schema.a_table
WHERE   HospitalNumber = @HospitalNo
