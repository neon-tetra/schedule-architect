import polars as pl

from ortools.sat.python import cp_model

model = cp_model.CpModel()

def add_all_different_groups(df: pl.DataFrame, group_col: str) -> pl.DataFrame:
    for row in df.group_by(group_col).agg(pl.col("value")).iter_rows(named=True):
        model.add_all_different(row["value"])
    return df

df_grid = (pl.Series("row", list(range(0, 9))).to_frame()
             .join(pl.Series("col", list(range(0, 9))).to_frame(), how="cross")
             .with_columns(value =  pl.col("row").map_elements(lambda _: model.new_int_var(1, 9, "")))
             .with_columns(box   = (pl.col("row") // 3) * 3 + 
                                   (pl.col("col") // 3))
             .pipe(add_all_different_groups, "row")
             .pipe(add_all_different_groups, "col")
             .pipe(add_all_different_groups, "box")                                   
)

#provided values
# [2,0] = 8
# [3,0] = 3
# [5,0] = 6
# [1,1] = 7
# [3,1] = 4
# [4,1] = 5
# [6,2] = 2
# [0,3] = 2
# [1,3] = 3
# [3,3] = 8
# [0,4] = 9
# [1,4] = 4
# [8,4] = 2
# [0,5] = 7
# [2,5] = 1
# [7,5] = 9
# [6,6] = 9
# [7,6] = 4
# [1,7] = 9
# [3,7] = 7
# [4,7] = 8
# [5,7] = 4
# [8,7] = 3
# [3,8] = 1
# [6,8] = 1

starting_values = {}
starting_values[(2,0)] = 8
starting_values[(3,0)] = 3
starting_values[(5,0)] = 6
starting_values[(1,1)] = 7
starting_values[(3,1)] = 4
starting_values[(4,1)] = 5
starting_values[(6,2)] = 2
starting_values[(0,3)] = 2
starting_values[(1,3)] = 3
starting_values[(3,3)] = 8
starting_values[(0,4)] = 9
starting_values[(1,4)] = 4
starting_values[(8,4)] = 2
starting_values[(0,5)] = 7
starting_values[(2,5)] = 1
starting_values[(7,5)] = 9
starting_values[(6,6)] = 9
starting_values[(7,6)] = 7
starting_values[(1,7)] = 9
starting_values[(3,7)] = 7
starting_values[(4,7)] = 8
starting_values[(5,7)] = 4
starting_values[(8,7)] = 6
starting_values[(3,8)] = 1
starting_values[(6,8)] = 4


for row in df_grid.iter_rows(named=True):
    for (r, c), v in starting_values.items():
        if row["row"] == r and row["col"] == c:
            model.Add(row["value"] == v)

solver = cp_model.CpSolver()
solver.parameters.max_time_in_seconds = 200
solver.parameters.num_search_workers = 8
solver.parameters.log_search_progress = True
solver.parameters.cp_model_presolve = True
status = solver.Solve(model)
print(f"Solver status: {status}")
