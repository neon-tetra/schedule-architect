from collections import defaultdict

from engine.context import ScenarioContext
from domain import SolveResult, SlotMatrix
from solver.var_registry import VarRegistry

from ortools.sat.python.cp_model import CpModel, CpSolver, LinearExpr, OPTIMAL, FEASIBLE


class ModelBuilder:
    """Builds and solves a CP-SAT scheduling model from a completed ScenarioContext.

    MVP implementation is intentionally monolithic — all model construction,
    constraint generation, and solving happens inside build_and_solve().
    Internal structure is deferred until the engine layer above it is complete.
    """

    def build_and_solve(self, context: ScenarioContext) -> SolveResult:
        """Read context, build CP-SAT model, solve, return result."""

        self._model = CpModel()

        var_registry = VarRegistry()

        # 1. Configuration

        AGENT_UPPER_BOUND = 20
        VALID_SHIFT_STARTS = [8, 9, 10, 11]  # in hours, corresponds to slots 16, 18, 20, 22
        SHIFT_DURATION_SLOTS = 17
        DAYS = range(0, 7)
        SLOTS = range(0, 48)

        # 2. Input
        agents = []
        for entry in context.current_roster.entries:
            skills = "_".join(entry.skills)
            for i in range(entry.count):
                agent_id = f"{skills}_{i+1}"
                agents.append({"id": agent_id, "skills": entry.skills})

        skill_ids = list(context.queues.keys())
        demand = context.demand.values

        # 3. Decision Variables
        for agent in agents:
            for day in DAYS:
                for shift in VALID_SHIFT_STARTS:
                    var_name = f"{agent['id']}_{day}_{shift}"
                    var = self._model.NewBoolVar(var_name)
                    var_registry.add(var, type="works", agent=agent["id"], day=day, shift=shift)

        # 4. Derived Expressions
        def slots_in_shift(shift):  # helper used for below
            return range(shift * 2, shift * 2 + SHIFT_DURATION_SLOTS)

        def coverage(day, slot, skill):
            valid_agents = [agent for agent in agents if skill in agent["skills"]]
            valid_shifts = [shift for shift in VALID_SHIFT_STARTS if slot in slots_in_shift(shift)]
            relevant_vars = []

            for agent in valid_agents:
                for shift in valid_shifts:
                    relevant_vars.extend(var_registry.query(type="works", agent=agent["id"], day=day, shift=shift))

            return LinearExpr.Sum(relevant_vars)

        def shifts_on_day(agent_id, day):
            return LinearExpr.Sum(var_registry.query(type="works", agent=agent_id, day=day))

        def shifts_in_week(agent_id):
            return LinearExpr.Sum(var_registry.query(type="works", agent=agent_id))

        # 5. Auxillary Variables
        for day in DAYS:
            for slot in SLOTS:
                for skill in skill_ids:
                    var_name = f"shortfall_{skill}_{day}_{slot}"
                    var = self._model.NewIntVar(0, AGENT_UPPER_BOUND, var_name)
                    var_registry.add(var, type="shortfall", day=day, slot=slot, skill=skill)
                    self._model.Add(var >= demand.get((day, slot, skill), 0) - coverage(day, slot, skill))

        # 6. Constraints
        for agent in agents:
            for day in DAYS:
                self._model.Add(shifts_on_day(agent["id"], day) <= 1)
            self._model.Add(shifts_in_week(agent["id"]) == 5)

        # 7. Objective
        shortfall_vars = var_registry.query(type="shortfall")
        self._model.Minimize(LinearExpr.Sum(shortfall_vars))

        # Solve
        solver = CpSolver()
        status = solver.Solve(self._model)
        solved = status in [OPTIMAL, FEASIBLE]

        supply_values: dict[tuple[int, int, str], int] = defaultdict(int)
        if solved:
            for day in DAYS:
                for slot in SLOTS:
                    for skill in skill_ids:
                        value = 0
                        valid_agents = [agent for agent in agents if skill in agent["skills"]]
                        valid_shifts = [shift for shift in VALID_SHIFT_STARTS if slot in slots_in_shift(shift)]
                        for agent in valid_agents:
                            for shift in valid_shifts:
                                works_var = var_registry.query_one(type="works", agent=agent["id"], day=day, shift=shift)
                                value += solver.Value(works_var)
                        if value > 0:
                            supply_values[(day, slot, skill)] = value

        supply = SlotMatrix(label="supply", values=dict(supply_values))
        shortfall = context.demand - supply

        return SolveResult(
            status=solver.StatusName(status),
            solve_time_seconds=solver.WallTime(),
            roster=context.current_roster,
            queues=context.queues,
            demand=context.demand,
            supply=supply,
            shortfall=shortfall,
        )
