-- Use a DO block to populate the temporary table
DO $$
BEGIN
    INSERT INTO temp_numbers (num)
    VALUES (42), (100), (7);
END
$$;
