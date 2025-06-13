--$Database  = mssql_database
--$Dataframe = Drop Table
DROP TABLE IF EXISTS a_database.a_schema.a_table
;

CREATE TABLE a_database.a_schema.a_table (
    STUDY_ID VARCHAR(100),
    TYPE_CODE VARCHAR(50),
    RESULT_DATE DATETIME,
    RESULT FLOAT,
    UNITS VARCHAR(50)
)

-- $Dataframe = Create Table

-- Declare Variables to inject into remote Query
DECLARE @STUDY_ID VARCHAR(100)
DECLARE @PATIENT_NO VARCHAR(50)
DECLARE @DATA_START_DATE DATETIME
DECLARE @DATA_END_DATE DATETIME

-- Declare a cursor to fetch patients from the cohort
DECLARE FetchPatients CURSOR FOR
	SELECT	STUDY_ID
		,	PATIENT_NO
		,	DATA_START_DATE
		,	DATA_END_DATE
	FROM projects.surgnec.AUX_COHORT

-- Open the cursor
OPEN FetchPatients

-- Fetch the first row
FETCH NEXT FROM FetchPatients INTO @STUDY_ID, @PATIENT_NO, @DATA_START_DATE, @DATA_END_DATE

-- Loop through the cursor rows
WHILE @@FETCH_STATUS = 0
BEGIN
    -- Build and execute the dynamic SQL query with injected values
    DECLARE @DynamicSQL NVARCHAR(MAX)
    SET @DynamicSQL = N'
    INSERT INTO a_database.a_schema.a_table (STUDY_ID, TYPE_CODE, RESULT_DATE, RESULT, UNITS)
	SELECT '''+ @STUDY_ID +''' AS STUDY_ID
           ,	TYPE_CODE
           ,	RESULT_DATE
           ,	RESULT
           ,	UNITS

    FROM OPENQUERY("A_LINKED_SERVER", ''
        WITH Vitals AS (
            SELECT Spells.HospitalNumber,
                   Signals.PatientID AS PatientID,
                   Params.ParameterID AS ParameterID,
                   Params.ParameterName AS ParameterName,
                   Signals.Time AS Time,
                   (Signals.VALUE - Units.Addition) / Units.Multiplier AS Result,
                   Units.UnitName AS UnitName,
            FROM Patients Spells
            INNER JOIN Signals ON (Signals.PatientId = Spells.PatientID)
            INNER JOIN Parameters Params ON (Params.ParameterID = Signals.ParameterID)
            INNER JOIN Units ON (Units.UnitID = Params.UnitID)
            WHERE Signals.Error = 0
        )
        SELECT TYPE_CODE AS TYPE_CODE,
               Time AS RESULT_DATE,
               Result AS RESULT,
               UnitName AS UNITS
        FROM Vitals Vitals
        WHERE   Vitals.HospitalNumber     = ''''' + @PATIENT_NO + '''''
            AND Vitals.Time         BETWEEN ''''' + CONVERT(NVARCHAR, @DATA_START_DATE, 120) + '''''
                                        AND ''''' + CONVERT(NVARCHAR, @DATA_END_DATE, 120) + '''''
    '')'

    -- Execute the dynamic SQL
    EXEC sp_executesql @DynamicSQL

    -- Fetch the next row
    FETCH NEXT FROM FetchPatients INTO @STUDY_ID, @PATIENT_NO, @DATA_START_DATE, @DATA_END_DATE
END

-- Close and deallocate the cursor
CLOSE FetchPatients
DEALLOCATE FetchPatients
;

--$DataFrame = Results
-- ignore the ; in this comment
DECLARE @HospitalNo VARCHAR(10) = 'a_test_no;'

SELECT  *
FROM    a_database.a_schema.a_table
WHERE   HospitalNumber = @HospitalNo
