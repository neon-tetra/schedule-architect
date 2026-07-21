from ortools.sat.python import cp_model
import polars as pl


def add_vars(df: pl.DataFrame, fn, col_name: str, **kwargs) -> pl.DataFrame:
    kwargs.setdefault("name", "")
    vars_ = [fn(**kwargs) for _ in range(df.height)]
    return df.with_columns(pl.Series(col_name, vars_, dtype=pl.Object))

def add_constraints(df: pl.DataFrame, fn, args_builder) -> pl.DataFrame:
    for row in df.iter_rows(named=True):
        fn(*args_builder(row))
    return df

def add_reified_conditional_constraint(df, model, conditional_args_builder, principal_args_builder):
    cond_vars = []
    for row in df.iter_rows(named=True):
        expr = conditional_args_builder(row)
        conditional_var = model.new_bool_var("")
        model.add(expr).only_enforce_if(conditional_var) 
        model.add_linear_expression_in_domain(expr, expr.bounds.complement()).only_enforce_if(conditional_var.Not())
       # model.add(complement).only_enforce_if(conditional_var.Not()) 
        
        #if A = true, then expression must be true
        #if B = true, then expression must be true
        #A <> B
        #if A_Anchor = true, then expression must be true
        #
        #If A_Anchor = false, then A_Beachball = true
        #Lets do this.  A_Crab = 1, but only if beachball is true
        #Expr = A_Crab, but only if A_Beachball is true
        #What does this do.  We're in unknown state, so anchor is false,
        #so beachball is true.  This forces crab (1) to expr.
        #Now, if the expression was false, then A_Anchor has nowhere to go
        #If the expression was true, the condition is satisfied.
        #It needs an out
        #model.add_linear_expression_in_domain(expr, [1]).only_enforce_if(conditional_var)
        
    
        principal_expr = principal_args_builder(row)
        model.add(principal_expr).only_enforce_if(conditional_var)
        cond_vars.append(conditional_var)
        print(f"conditional_var: {conditional_var}, inverse_conditional_var: {inverse_var}, conditional_expr: {conditional_var}, principal_expr: {principal_expr}")
    df = df.with_columns(pl.Series("cond_var", cond_vars, dtype=pl.Object))
    return df
    
model = cp_model.CpModel()

#make array of numbers 0-100
nums = list(range(100))
#make 100-len bool array with 1 if index num is prime
primes = [1 if all(num % i != 0 for i in range(2, int(num**0.5) + 1)) and num > 1 else 0 for num in nums]
print(primes)

df = (pl.DataFrame({
    "i": range(100),})
    .pipe(add_vars, model.new_int_var,  col_name="var_i", lb=0, ub=100)
    .pipe(add_vars, model.new_int_var,  col_name="var_a", lb=0, ub=100)
    .pipe(add_vars, model.new_bool_var, col_name="var_b")
    .pipe(add_vars, model.new_int_var,  col_name="var_c", lb=0, ub=100)
    .pipe(add_constraints, model.add, lambda row: [
        row["var_i"] == row["i"]])
    .pipe(add_reified_conditional_constraint, model,
            conditional_args_builder = lambda row: row["var_i"] > 50,
            principal_args_builder   = lambda row: row["var_a"] == row["var_i"])
    .pipe(add_constraints, model.add_element, lambda row: [row["var_a"], primes, row["var_b"]])
    .pipe(add_reified_conditional_constraint, model,
            conditional_args_builder = lambda row: row["var_b"] == 1,
            principal_args_builder   = lambda row: row["var_c"] == row["var_a"] * 2)
    )

solver = cp_model.CpSolver()
model.maximize(sum(df["var_a"]))
solve = solver.Solve(model)
print([solver.value(v) for v in df["cond_var"]])
print("Solver status:", solver.StatusName(solve))
df_printable = (df
                .with_columns(pl.Series("var_i_val", [solver.Value(var) for var in df["var_i"]], dtype=pl.Int64))
                .with_columns(pl.Series("var_a_val", [solver.Value(var) for var in df["var_a"]], dtype=pl.Int64))
                .with_columns(pl.Series("var_b_val", [solver.Value(var) for var in df["var_b"]], dtype=pl.Int64))
                .with_columns(pl.Series("var_c_val", [solver.Value(var) for var in df["var_c"]], dtype=pl.Int64))

                .select("i", "var_i_val", "var_a_val", "var_b_val", "var_c_val"))
print(df_printable)

model.add(b == 1).only_enforce_if(n_or_p)
model.add(n_or_p == 1).only_enforce_if(b)

# var_a = model.NewIntVar(0, 10, "var_a")
# model.add(var_a == 5)

# vars = []

# for i in range(10):
#     var_b = model.NewIntVar(0, 10, f"var_b_{i}")

#     conditional_expr = (i >= var_a)

#     conditional_var = model.NewBoolVar(f"conditional_var_{i}")
#     model.Add(conditional_expr).OnlyEnforceIf(conditional_var)

#     inverse_conditional_var = model.NewBoolVar(f"inverse_conditional_var_{i}")
#     model.Add(conditional_expr).OnlyEnforceIf(inverse_conditional_var.Not())
#     model.Add(inverse_conditional_var == 1).OnlyEnforceIf(conditional_var.Not())
    
#     principal_expr = (var_b == 1)

#     model.add(principal_expr).OnlyEnforceIf(conditional_var)
#     vars.append([var_b, conditional_var, inverse_conditional_var])


# solver = cp_model.CpSolver()
# solve = solver.Solve(model)
# print("Solver status:", solver.StatusName(solve))
# for i in range(10):
#     print(f"var_b_{i}: {solver.Value(vars[i][0])}, conditional_var_{i}: {solver.Value(vars[i][1])}, inverse_conditional_var_{i}: {solver.Value(vars[i][2])}")
