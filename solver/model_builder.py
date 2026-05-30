from engine.context import ScenarioContext
from domain import ScheduleResult
from solver.var_registry import VariableRegistry

from ortools.sat.python.cp_model import CpModel, CpSolver, CpSolverStatus
from collections import namedtuple
class ModelBuilder:
    """Builds and solves a CP-SAT scheduling model from a completed ScenarioContext.
    
    MVP implementation is intentionally monolithic — all model construction,
    constraint generation, and solving happens inside build_and_solve().
    Internal structure is deferred until the engine layer above it is complete.
    """

    def build_and_solve(self, context: ScenarioContext) -> ScheduleResult:
        """Read context, build CP-SAT model, solve, return result."""

        """
            1. Configuration: ## All hardcoded for now, variable (from scenario context) later
            UB - Agent Upper Bound (for coverage vars)
            SH - Valid Shift Start Times (e.g. 8, 9, 10, 11)
            SD - Shift Duration (in slots)
            D  - Days (0-6)
            SL - Slots (0 - 47)
            
            2. Input: ## All retrieved from scenario context
            A - Agents {expanded from roster}
            SK - Skills (from call environments)
            Demand - demand[d, sl, sk] from erlang curves

            3. Decision Variables:
            works[a, d, sh] in {0, 1} - agent a works shift sh on day d

            4. Derived Expressions:
            coverage[d, sl, sk] = sum(works[a, d, sh])
                for all a where a.sk == k
                for all sh where sl in [sh * 2, sh * 2 + 15]
            
            shifts_on_day[a, d] = sum(works[a, d, sh]) for all sh
            shifts_in_week[a] = sum(works[a, d, sh]) for all d, sh
            
            5. Auxillary Variables:
            shortfall[d, sl, sk] = max(0, demand[d, sl, sk] - coverage[d, sl, sk]) ## nonlinear, requires helper var

            6. Constraints:
            shifts_on_day[a, d] <= 1
            shifts_in_week[a] == 5

            7. Objective:
            Minimize sum(shortfall[d, sl, sk]) across all d, sl, sk
            
        """

        self._model = CpModel()
        
        var_registry = VariableRegistry()

        # 1. Configuration

        AGENT_UPPER_BOUND    = 20
        VALID_SHIFT_STARTS   = [8, 9, 10, 11]  # in hours, corresponds to slots 16, 18, 20, 22
        SHIFT_DURATION_SLOTS = 17
        DAYS                 = range(0, 7)
        SLOTS                = range(0, 48)


        # 2. Input
        agents = []
        for entry in context.current_roster.entries:
            skills = "_".join(entry.skills)
            for i in range(entry.count):
                agent_id = f"{skills}_{i+1}"
                agents.append({"id": agent_id, "skills": entry.skills})
        
        skills = skills = list(context.call_environments.keys())
        demand = {}
        for skill_id, erlang_result in context.current_erlang.items():
            curve = erlang_result.curve
            for day in DAYS:
                for slot in SLOTS:
                    demand[(day, slot, skill_id)] = curve[day][slot]
        
        # 3. Decision Variables
        for agent in agents:
            for day in DAYS:
                for shift in VALID_SHIFT_STARTS:
                    var_name = f"{agent['id']}_{day}_{shift}"
                    var = self._model.NewBoolVar(var_name)
                    var_registry.add(var, type="works", agent=agent["id"], day=day, shift=shift)
        
        # 4. Derived Expressions
        def slots_in_shift(shift): #helper used for below
            return range(shift * 2, shift * 2 + SHIFT_DURATION_SLOTS)
        
        def coverage(day, slot, skill):
            valid_agents = [agent for agent in agents if skill in agent["skills"]]
            valid_shifts = [shift for shift in VALID_SHIFT_STARTS if slot in slots_in_shift(shift)]
            relevant_vars = []

            for agent in valid_agents:
                for shift in valid_shifts:
                    relevant_vars.extend(var_registry.query(type="works", agent=agent["id"], day=day, shift=shift))

            return self._model.LinearExpr.Sum(relevant_vars) 
        
        def shifts_on_day(agent_id, day):
            return self._model.LinearExpr.Sum(var_registry.query(type="works", agent=agent_id, day=day))
        
        def shifts_in_week(agent_id):
            return self._model.LinearExpr.Sum(var_registry.query(type="works", agent=agent_id))
        
        # 5. Auxillary Variables
        for day in DAYS:
            for slot in SLOTS:
                for skill in skills:
                    var_name = f"shortfall_{skill}_{day}_{slot}"
                    var = self._model.NewIntVar(0, AGENT_UPPER_BOUND, var_name)
                    var_registry.add(var, type="shortfall", day=day, slot=slot, skill=skill)
                    self._model.Add(var >= demand[(day, slot, skill)] - coverage(day, slot, skill))

        # 6. Constraints
        for agent in agents:
            for day in DAYS:
                self._model.Add(shifts_on_day(agent["id"], day) <= 1)
            self._model.Add(shifts_in_week(agent["id"]) == 5)
        
        # 7. Objective
        shortfall_vars = var_registry.query(type="shortfall")
        self._model.Minimize(self._model.LinearExpr.Sum(shortfall_vars))

        # Solve
        solver = CpSolver()
        status = solver.Solve(self._model)

        #schedule result named tuple
        
        schedule_result = namedtuple("ScheduleResult",["status", "objective", "vars"])
        schedule_result.status = solver.StatusName(status)
        schedule_result.objective = solver.ObjectiveValue() if status == CpSolverStatus.OPTIMAL else None
        schedule_result.vars = {var.Name(): solver.Value(var) for var in var_registry.query(type="works")}
                                
        return schedule_result

        
