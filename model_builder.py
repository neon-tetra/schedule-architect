from pydantic import BaseModel
from domain import Roster, QueueProfile
from slot_matrix import SlotMatrix
from var_registry import VarRegistry

from ortools.sat.python.cp_model import CpModel, CpSolver, LinearExpr


class SolverOutput(BaseModel):
    status: str
    solve_time_seconds: float
    demand: SlotMatrix
    supply: SlotMatrix
    shortfall: SlotMatrix


class ModelBuilder:
    """Builds and solves a CP-SAT scheduling model from a completed ScenarioContext."""

    def build_and_solve(
        self,
        roster: Roster,
        queues: dict[str, QueueProfile],
        demand: SlotMatrix,
    ) -> SolverOutput:
        """Read context, build CP-SAT model, solve, return result."""
        self._model = CpModel()

        var_registry = VarRegistry()

        AGENT_UPPER_BOUND = 20
        VALID_SHIFT_STARTS = [8, 9, 10, 11]
        SHIFT_DURATION_SLOTS = 17
        DAYS = range(0, 7)
        SLOTS = range(0, 48)

        agents = []
        for entry in roster.entries:
            skills = "_".join(entry.skills)
            for i in range(entry.count):
                agent_id = f"{skills}_{i + 1}"
                agents.append({"id": agent_id, "skills": entry.skills})

        skills = list(queues.keys())
        demand_dict = demand.values

        for agent in agents:
            for day in DAYS:
                for shift in VALID_SHIFT_STARTS:
                    var_name = f"{agent['id']}_{day}_{shift}"
                    var = self._model.NewBoolVar(var_name)
                    var_registry.add(var, type="works", agent=agent["id"], day=day, shift=shift)

        def slots_in_shift(shift):
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

        for day in DAYS:
            for slot in SLOTS:
                for skill in skills:
                    var_name = f"shortfall_{skill}_{day}_{slot}"
                    var = self._model.NewIntVar(0, AGENT_UPPER_BOUND, var_name)
                    var_registry.add(var, type="shortfall", day=day, slot=slot, skill=skill)
                    self._model.Add(var >= demand_dict.get((day, slot, skill), 0) - coverage(day, slot, skill))

        for agent in agents:
            for day in DAYS:
                self._model.Add(shifts_on_day(agent["id"], day) <= 1)
            self._model.Add(shifts_in_week(agent["id"]) == 5)

        shortfall_vars = var_registry.query(type="shortfall")
        self._model.Minimize(LinearExpr.Sum(shortfall_vars))

        solver = CpSolver()
        status = solver.Solve(self._model)

        supply_values = {}
        for day in DAYS:
            for slot in SLOTS:
                for skill in skills:
                    valid_agents = [a for a in agents if skill in a["skills"]]
                    valid_shifts = [sh for sh in VALID_SHIFT_STARTS if slot in slots_in_shift(sh)]
                    total = 0
                    for agent in valid_agents:
                        for shift in valid_shifts:
                            for var in var_registry.query(type="works", agent=agent["id"], day=day, shift=shift):
                                total += solver.Value(var)
                    supply_values[(day, slot, skill)] = total

        supply = SlotMatrix(label="supply", values=supply_values)

        shortfall_values = {}
        for day in DAYS:
            for slot in SLOTS:
                for skill in skills:
                    vars = var_registry.query(type="shortfall", day=day, slot=slot, skill=skill)
                    shortfall_values[(day, slot, skill)] = solver.Value(vars[0]) if vars else 0

        shortfall = SlotMatrix(label="shortfall", values=shortfall_values)

        return SolverOutput(
            status=solver.StatusName(status),
            solve_time_seconds=solver.WallTime(),
            demand=demand,
            supply=supply,
            shortfall=shortfall,
        )
