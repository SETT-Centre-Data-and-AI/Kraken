-- $Database = KRAKEN_TEST_MAIN
-- $Dataframe = TheOrderDoesntMatter
SELECT 4 AS RUN_ORDER
;

-- $Dataframe = AnotherQuery
-- $Arraysize = 100
SELECT 5 AS RUN_ORDER
;

-- $Dataframe = ThisRunsSixth
SELECT 6 AS RUN_ORDER
;
