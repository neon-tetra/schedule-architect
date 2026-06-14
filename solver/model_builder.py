from core.domain import Roster, QueueProfile
from core.slot_matrix import SlotMatrix
from core.solve_run import SolveRun
from solver.var_registry import VarRegistry

from ortools.sat.python.cp_model import CpModel, CpSolver, LinearExpr


class ModelBuilder:
    """Builds and solves a CP-SAT scheduling model from a completed ScenarioContext.

    MVP implementation is intentionally monolithic — all model construction,
    constraint generation, and solving happens inside build_and_solve().
    Internal structure is deferred until the engine layer above it is complete.
    """

    def build_and_solve(self, roster: Roster, queues: dict[str, QueueProfile], demand: SlotMatrix) -> SolveRun:
        """Read context, build CP-SAT model, solve, return result."""

        # 1. Configuration: all hardcoded for now, variable (from scenario context) later
        #    UB - Agent Upper Bound (for coverage vars)
        #    SH - Valid Shift Start Times (e.g. 8, 9, 10, 11)
        #    SD - Shift Duration (in slots)
        #    D  - Days (0-6)
        #    SL - Slots (0 - 47)
        #
        # 2. Input: passed as explicit args for now - needs to be overhauled to be more
        #    dynamic after mvp
        #    A - Agents {expanded from roster}
        #    SK - Skills (from queues)
        #    Demand - demand[d, sl, sk] from erlang curves
        #
        # 3. Decision Variables:
        #    works[a, d, sh] in {0, 1} - agent a works shift sh on day d
        #
        # 4. Derived Expressions:
        #    coverage[d, sl, sk] = sum(works[a, d, sh])
        #        for all a where a.sk == k
        #        for all sh where sl in [sh * 2, sh * 2 + 17]
        #
        #    shifts_on_day[a, d] = sum(works[a, d, sh]) for all sh
        #    shifts_in_week[a] = sum(works[a, d, sh]) for all d, sh
        #
        # 5. Auxiliary Variables:
        #    shortfall[d, sl, sk] = max(0, demand[d, sl, sk] - coverage[d, sl, sk])
        #
        # 6. Constraints:
        #    shifts_on_day[a, d] <= 1
        #    shifts_in_week[a] == 5
        #
        # 7. Objective:
        #    Minimize sum(shortfall[d, sl, sk]) across all d, sl, sk

        self._model = CpModel()

        var_registry = VarRegistry()

        # 1. Configuration
        # TODO: move hardcoded config (VALID_SHIFT_STARTS, SHIFT_DURATION_SLOTS etc.) to ScenarioContext
        AGENT_UPPER_BOUND = 20
        VALID_SHIFT_STARTS = [8, 9, 10, 11]  # in hours; shift * 2 below maps these to slots 16, 18, 20, 22
        SHIFT_DURATION_SLOTS = 17
        DAYS = range(0, 7)
        SLOTS = range(0, 48)

        # 2. Input
        agents = []
        for entry in roster.entries:
            skills = "_".join(entry.skills)
            for i in range(entry.count):
                agent_id = f"{skills}_{i+1}"
                agents.append({"id": agent_id, "skills": entry.skills})

        skills = list(queues.keys())
        demand_dict = demand.values  # already a dict[(day, slot, skill_id) -> int]

        # 3. Decision Variables
        for agent in agents:
            for day in DAYS:
                for shift in VALID_SHIFT_STARTS:
                    var_name = f"{agent['id']}_{day}_{shift}"
                    var = self._model.NewBoolVar(var_name)
                    var_registry.add(var, type="works", agent=agent["id"], day=day, shift=shift)

        # 4. Derived Expressions
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

        # 5. Auxiliary Variables
        for day in DAYS:
            for slot in SLOTS:
                for skill in skills:
                    var_name = f"shortfall_{skill}_{day}_{slot}"
                    var = self._model.NewIntVar(0, AGENT_UPPER_BOUND, var_name)
                    var_registry.add(var, type="shortfall", day=day, slot=slot, skill=skill)
                    self._model.Add(var >= demand_dict.get((day, slot, skill), 0) - coverage(day, slot, skill))

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
        solver.Solve(self._model)

        # Build supply from solved works vars
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

        # Read shortfall directly from solved IntVars
        shortfall_values = {}
        for day in DAYS:
            for slot in SLOTS:
                for skill in skills:
                    vars = var_registry.query(type="shortfall", day=day, slot=slot, skill=skill)
                    shortfall_values[(day, slot, skill)] = solver.Value(vars[0]) if vars else 0

        shortfall = SlotMatrix(label="shortfall", values=shortfall_values)

        return SolveRun(
            run_id="",   # assigned by caller (Toolkit._run_solve)
            label="",    # assigned by caller
            demand=demand,
            supply=supply,
            shortfall=shortfall,
        )
