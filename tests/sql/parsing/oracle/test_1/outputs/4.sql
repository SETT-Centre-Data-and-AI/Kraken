SELECT      One.*
        ,   Two.*
        ,   ROW_NUMBER() OVER(
                PARTITION BY One.GROUP_COLUMN
                ORDER BY     One.ORDER_COLUMN) AS RANK

FROM        SOMETHING_ELSE      One
INNER JOIN  "A DECLARE TABLE /" Two ON (Two.JOIN_COLUMN = One.JOIN_COLUMN)

WHERE   1=1
    AND One.FILTER_COLUMN IN ('A', 'List', 'Of', 'Things')
    AND Two.FILTER_COLUMN BETWEEN 'One Thing' AND 'Another'
    AND Two.WRONG_DEFINE IN ('Restriction', 'ATable')
