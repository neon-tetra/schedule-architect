from core.domain import Roster, QueueProfile
from core.slot_matrix import SlotMatrix
from core.solve_run import SolveRun
from solver.var_registry import VarRegistry
from solver.shifts import generate_variants
from ortools.sat.python.cp_model import CpModel, CpSolver, OPTIMAL, FEASIBLE

class ModelBuilder:
    """Builds and solves a CP-SAT scheduling model from a completed ScenarioContext.

    MVP implementation is intentionally monolithic — all model construction,
    constraint generation, and solving happens inside build_and_solve().
    Internal structure is deferred until the engine layer above it is complete.
    """

    def build_and_solve(self, roster: Roster, queues: dict[str, QueueProfile], demand: SlotMatrix) -> SolveRun:
        """Read context, build CP-SAT model, solve, return result."""


        AGENT_UPPER_BOUND    = 20
        VALID_SHIFT_STARTS   = [8, 9, 10, 11]
        SHIFT_DURATION_SLOTS = 17
        DAYS                 = range(0, 7)
        SLOTS                = range(0, 48)
        VALID_WORK_WEEK_PATTERNS = [
            (2,3,4,5,6), (3,4,5,6,0), (4,5,6,0,1),
            (5,6,0,1,2), (6,0,1,2,3), (0,1,2,3,4), (1,2,3,4,5)
        ]
        SCALED_UB = AGENT_UPPER_BOUND * 2
        shift_variants = generate_variants(VALID_SHIFT_STARTS, SHIFT_DURATION_SLOTS)
        #schedule variants - crossproduct of shift_variants and VALID_WORK_WEEK_PATTERNS
        schedule_variants = [(shift.variant_id, workweek) for shift in shift_variants for workweek in VALID_WORK_WEEK_PATTERNS]

        self._model = CpModel()

        agents = []
        for entry in roster.entries:
            primary   = entry.skills[0]
            secondary = entry.skills[1] if len(entry.skills) > 1 else None
            for i in range(entry.count):
                skill_key = "_".join(entry.skills)
                agents.append({
                    "id":        f"{skill_key}_{i+1}",
                    "primary":   primary,
                    "secondary": secondary,
                    "skills":    entry.skills,
                })
        skills = list(queues.keys())

        var_registry = VarRegistry()

        for day in DAYS:
            for slot in SLOTS:
                for skill in skills:
                    demand_const = demand.values.get((day, slot, skill), 0) * 2 # HALF-SLOT SCALING
                    var_registry.add(demand_const, type="demand_const", day=day, slot=slot, skill=skill)

        for pattern in VALID_WORK_WEEK_PATTERNS:
            for variant in shift_variants:
                    
                for day in DAYS:
                    for slot in SLOTS:
                        intensity_const = 2 if day in pattern and variant.slot_present[slot] else 0
                        present_const = 1 if intensity_const > 0 else 0


                        var_registry.add(present_const, type="present_const", schedule_variant=variant.variant_id,
                                            day=day,
                                            slot=slot)
                        var_registry.add(intensity_const, type="intensity_const", schedule_variant=variant.variant_id,
                                            day=day,
                                            slot=slot,
                                            intensity=intensity_const)
            
        for agent in agents:
            for variant in schedule_variants:
                var_registry.add(self._model.NewBoolVar(f"schedule_variant_{agent['id']}_{variant[0]}_{variant[1]}"), 
                                 type="schedule_variant", 
                                 agent=agent["id"], 
                                 schedule_variant=variant)
                #max one variant
            self._model.Add(sum(var_registry.query(type="schedule_variant", agent=agent["id"])) == 1)
        
        print("enter heavy duty loop")
        for agent in agents:
            for day in DAYS:
                for slot in SLOTS:
                    agent_slot_intensity_var = self._model.NewIntVar(0, 2, f"intensity_{agent['id']}_{day}_{slot}")
                    var_registry.add(agent_slot_intensity_var, type="agent_slot_intensity", 
                                     agent=agent["id"], 
                                     day=day, 
                                     slot=slot)
                    agent_slot_present_var = self._model.NewBoolVar(f"present_{agent['id']}_{day}_{slot}")
                    var_registry.add(agent_slot_present_var, type="agent_slot_present",
                                        agent=agent["id"],
                                        day=day,
                                        slot=slot)
                    for skill in agent["skills"]:
                        agent_skill_slot_present_var = self._model.NewBoolVar(f"agent_skill_slot_present_{agent['id']}_{skill}_{day}_{slot}")
                        var_registry.add(agent_skill_slot_present_var, type="agent_skill_slot_present", 
                                         agent=agent["id"], 
                                         skill=skill, 
                                         day=day, 
                                         slot=slot)
                        agent_slot_intensity_var = var_registry.query(type="agent_slot_intensity", agent=agent["id"], day=day, slot=slot)[0]
                        agent_skill_slot_intensity_var = self._model.NewIntVar(0, 2, f"agent_skill_slot_intensity_{agent['id']}_{skill}_{day}_{slot}")
                        var_registry.add(agent_skill_slot_intensity_var, type="agent_skill_slot_intensity",
                                            agent=agent["id"], 
                                            skill=skill, 
                                            day=day, 
                                            slot=slot)
                        self._model.AddMultiplicationEquality(agent_skill_slot_intensity_var, [agent_slot_intensity_var, agent_skill_slot_present_var])

                    # tie intensity to chosen schedule variant
                    self._model.Add(
                        agent_slot_intensity_var
                        == sum(
                            var_registry.query(type="schedule_variant", agent=agent["id"], schedule_variant=variant.variant_id)[0]
                            * var_registry.query(type="intensity_const", schedule_variant=variant.variant_id, day=day, slot=slot)[0]
                            for variant in schedule_variants
                        )
                    )

                    self._model.Add(agent_slot_intensity_var >= agent_slot_present_var)
                    self._model.Add(agent_slot_intensity_var <= 2 * agent_slot_present_var)

                    skill_vars = var_registry.query(type="agent_skill_slot_present", agent=agent["id"], day=day, slot=slot)
                    self._model.Add(agent_slot_present_var == sum(skill_vars))
        
        print("exit heavy duty loop, enter coverage loop")

        for skill in skills:
            for day in DAYS:
                for slot in SLOTS:
                    coverage_var = self._model.NewIntVar(0, SCALED_UB, f"coverage_{skill}_{day}_{slot}")
                    var_registry.add(coverage_var, type="coverage", skill=skill, day=day, slot=slot)
                    skill_coverage_vars = var_registry.query(type="agent_skill_slot_intensity", skill=skill, day=day, slot=slot)
                    self._model.Add(coverage_var == sum(skill_coverage_vars))

                    demand_const = var_registry.query(type="demand_const", day=day, slot=slot, skill=skill)[0]
                    shortfall_var = self._model.NewIntVar(0, SCALED_UB, f"shortfall_{skill}_{day}_{slot}")
                    var_registry.add(shortfall_var, type="shortfall", skill=skill, day=day, slot=slot)
                    self._model.Add(shortfall_var >= demand_const - coverage_var)
                    self._model.Add(shortfall_var >= 0)
        
        all_shortfalls = var_registry.query(type="shortfall")
        self._model.Minimize(sum(all_shortfalls))

        solver = CpSolver()
        solver.parameters.max_time_in_seconds = 120
        solver.parameters.num_search_workers = 8 
        solver.parameters.log_search_progress = True
        solver.parameters.cp_model_presolve = True

        status = solver.Solve(self._model)
        supply = SlotMatrix(label="supply", values={})
        shortfall = SlotMatrix(label="shortfall", values={})
        if status in (OPTIMAL, FEASIBLE):
            for skill in skills:
                for day in DAYS:
                    for slot in SLOTS:
                        coverage_var = var_registry.query(type="coverage", skill=skill, day=day, slot=slot)[0]
                        coverage_val = solver.Value(coverage_var)
                        supply.values[(day, slot, skill)] = coverage_val // 2 # HALF-SLOT SCALING

                        shortfall_var = var_registry.query(type="shortfall", skill=skill, day=day, slot=slot)[0]
                        shortfall_val = solver.Value(shortfall_var)
                        shortfall.values[(day, slot, skill)] = shortfall_val // 2 # HALF-SLOT SCALING
        else:
            print("No solution found.")
        solve_run = SolveRun(
            run_id="test_run_001",
            label="Test Run 001",
            demand=demand,
            supply=supply,
            shortfall=shortfall,
            roster=roster
        )
        return solve_run


        

