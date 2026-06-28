import polars as pl

slots = pl.Series("slot", list(range(0, 48)))

VALID_WORK_WEEK_PATTERNS = [
    (2,3,4,5,6), (3,4,5,6,0), (4,5,6,0,1),
    (5,6,0,1,2), (6,0,1,2,3), (0,1,2,3,4), (1,2,3,4,5)
]
work_week_patterns = (pl.DataFrame({"day": VALID_WORK_WEEK_PATTERNS})
                      .with_row_index("id")
                      .explode("day")
)

VALID_SHIFT_STARTS = [16, 18, 20, 22]  # hours; *2 to convert to slots
shift_start_slots = pl.Series("slot", VALID_SHIFT_STARTS)

ctx = pl.SQLContext(eager=True)
ctx.register("slots", slots)
ctx.register("work_week_patterns", work_week_patterns)
ctx.register("shift_start_slots", shift_start_slots)

sql = """
WITH shift_variants AS (
     SELECT  shift_start.slot AS shift_start
          ,  first_break.slot AS first_break
          ,        lunch.slot AS lunch
          , second_break.slot AS second_break
          ,  shift_start.slot + 17 AS shift_end
          , ROW_NUMBER() AS shift_id
       FROM slots AS shift_start
 CROSS JOIN slots AS first_break
 CROSS JOIN slots AS lunch
 CROSS JOIN slots AS second_break
 INNER JOIN shift_start_slots AS st ON shift_start.slot = st.slot
      WHERE  first_break.slot >= shift_start.slot + 3
        AND        lunch.slot >= first_break.slot + 3
        AND second_break.slot >=       lunch.slot + 3
        AND second_break.slot <= shift_start.slot + 14
),
schedule_variants AS (
    SELECT ROW_NUMBER() AS schedule_id
         , wwp.id AS work_week_id
         , vss.shift_id
         , wwp.day
         , vss.shift_start
         , vss.first_break
         , vss.lunch
         , vss.second_break
      FROM work_week_patterns    AS wwp
CROSS JOIN valid_shift_summaries AS vss
),
shift_slots AS (
    SELECT vss.shift_id
         , vss.shift_start
         , vss.first_break
         , vss.lunch
         , vss.second_break
         ,   s.slot
         , CASE WHEN s.slot = vss.first_break  THEN 1
                WHEN s.slot = vss.lunch        THEN 0
                WHEN s.slot = vss.second_break THEN 1
                WHEN s.slot BETWEEN vss.shift_start AND vss.shift_end THEN 2
                ELSE 0
            END AS activity
      FROM valid_shift_summaries AS vss
CROSS JOIN slots AS s
),
schedule_slots AS (
    SELECT  sv.schedule_id
         ,  sv.day
         , vss.slot
         , vss.activity
      FROM schedule_variants AS sv
INNER JOIN shift_slots      AS vss ON sv.shift_id = vss.shift_id
)
SELECT * FROM schedule_slots;
"""

df = ctx.execute(sql)
result = df.sample(df.height*.2, seed=42)
