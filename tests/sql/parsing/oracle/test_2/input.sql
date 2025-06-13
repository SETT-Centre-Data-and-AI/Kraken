DEFINE DepartmentID = "10"

DECLARE
    -- Variables to hold intermediate results
    v_patient_id       patients.patient_id%TYPE;
    v_department_name  departments.department_name%TYPE;
    v_total_stay_days  NUMBER := 0;
    v_sql_query        VARCHAR2(4000);
    v_avg_stay_days    NUMBER;

    -- Cursor for patient details
    CURSOR patient_cursor IS
        SELECT patient_id, discharge_date - admission_date AS stay_days
        FROM patients
        WHERE department_id = 10
        FOR UPDATE;

    -- Record to hold cursor data
    patient_record patient_cursor%ROWTYPE;

BEGIN
    -- Step 1: Fetch and process department information
    SELECT department_name
    INTO v_department_name
    FROM departments
    WHERE department_id = 10;

    DBMS_OUTPUT.PUT_LINE('Processing department: ' || v_department_name);

    -- Step 2: Process patients within the department
    OPEN patient_cursor;

    LOOP
        FETCH patient_cursor INTO patient_record;
        EXIT WHEN patient_cursor%NOTFOUND;

        v_total_stay_days := v_total_stay_days + patient_record.stay_days;

        -- Print patient details
        DBMS_OUTPUT.PUT_LINE('Patient ID: ' || patient_record.patient_id || ', Stay Days: ' || patient_record.stay_days);
    END LOOP;

    CLOSE patient_cursor;

    -- Step 3: Calculate average stay days
    v_avg_stay_days := v_total_stay_days / (SELECT COUNT(*) FROM patients WHERE department_id = 10);
    DBMS_OUTPUT.PUT_LINE('Total Stay Days: ' || v_total_stay_days || ', Average Stay Days: ' || v_avg_stay_days);

    -- Step 4: Execute dynamic SQL to find patients with above-average stays
    v_sql_query := 'SELECT patient_id, first_name, last_name, (discharge_date - admission_date) AS stay_days '
                || 'FROM patients '
                || 'WHERE department_id = :dept_id AND (discharge_date - admission_date) > :min_stay_days '
                || 'ORDER BY stay_days DESC';

    FOR long_stay_patient IN (EXECUTE IMMEDIATE v_sql_query USING 10, v_avg_stay_days)
    LOOP
        DBMS_OUTPUT.PUT_LINE('Patient ID: ' || long_stay_patient.patient_id
                            || ', Name: ' || long_stay_patient.first_name || ' ' || long_stay_patient.last_name
                            || ', Stay Days: ' || long_stay_patient.stay_days);
    END LOOP;

    -- Final step: Handle any errors
    EXCEPTION
        WHEN NO_DATA_FOUND THEN
            DBMS_OUTPUT.PUT_LINE('No data found for the specified department.');
        WHEN OTHERS THEN
            DBMS_OUTPUT.PUT_LINE('An error occurred: ' || SQLERRM);
END;
/


-- Retrieve all patients admitted to a specific department
SELECT patient_id, first_name, last_name, admission_date, discharge_date
FROM patients
WHERE department_id = &DepartmentID;

-- List all departments with their total patient count
SELECT department_id, COUNT(*) AS patient_count
FROM patients
GROUP BY department_id;

-- Find the patient with the longest stay
SELECT patient_id, first_name, last_name, (discharge_date - admission_date) AS stay_days
FROM patients
ORDER BY stay_days DESC
FETCH FIRST 1 ROW ONLY;

-- Get the count of patients admitted each year
SELECT EXTRACT(YEAR FROM admission_date) AS admission_year, COUNT(*) AS patient_count
FROM patients
GROUP BY EXTRACT(YEAR FROM admission_date)
ORDER BY admission_year;
