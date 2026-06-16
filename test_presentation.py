from agent.toolkit import Toolkit

toolkit = Toolkit()
toolkit.execute("run_solve", {"label": "Test_Initial_Run"})
solve = toolkit._context._solves[0]
print(solve)