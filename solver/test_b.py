from ortools.sat.python import cp_model
model = cp_model.CpModel()

var_n = model.NewBoolVar("var_n")
var_p = model.NewBoolVar("var_p")
var_b = model.NewBoolVar("var_b")

model.add(var_n == 1)

model.add_bool_or([var_n, var_p]).OnlyEnforceIf(var_b)
x = model.add()

model.maximize(var_b) # var_b = 1
#model.minimize(var_b) # var_b = 0


solver = cp_model.CpSolver()
solver.solve(model)
print("var_n:", solver.value(var_n))
print("var_p:",  solver.value(var_p))
print("var_b:", solver.value(var_b))