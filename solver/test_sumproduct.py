
try:
    from problem import Problem       # dfor -- importable in place via the venv .pth file, see CLAUDE.md
    from report import solved as dfor_solved
except ImportError:

    import sys
    sys.path.insert(0, r"C:\neon_tetra\active\dfor")
    from problem import Problem
    from report import solved as dfor_solved

from ortools.sat.python import cp_model
model = cp_model.CpModel()
problem = Problem(model)
import polars as pl



l1 = [model.NewBoolVar(f"l1_{i}") for i in range(3)]
l2 = [model.NewBoolVar(f"l2_{i}") for i in range(3)]

df_result = (pl.DataFrame({"result":[1]})
             .pipe(problem.new_int_var, "result_var", lb=0, ub=10)
           #  .join(df, how="cross")
           #  .group_by("result")
           #  .agg(pl.col("col_1").alias("col_1_list"),
           #       pl.col("col_2").alias("col_2_list")) #cant easily zip or use comprehensions because vars need to resolve
            .pipe(problem.add, lambda row: (sum(i * j for i, j in zip(l1, l2)) == row["result"],)))

