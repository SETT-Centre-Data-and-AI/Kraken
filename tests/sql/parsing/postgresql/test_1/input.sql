-- Create a temporary table to store data
CREATE TEMP TABLE temp_numbers (num INTEGER);

-- Use a DO block to populate the temporary table
DO $$
BEGIN
    INSERT INTO temp_numbers (num)
    VALUES (42), (100), (7);
END
$$;

-- Query the data from the temporary table
SELECT * FROM temp_numbers;
