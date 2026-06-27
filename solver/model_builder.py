from core.domain import Roster, QueueProfile
from core.slot_matrix import SlotMatrix
from core.solve_run import SolveRun
from solver.var_registry import VarRegistry
from solver.shifts import generate_variants
from ortools.sat.python.cp_model import CpModel, CpSolver, OPTIMAL, FEASIBLE
from pydantic import BaseModel, model_validator


#schedule.days[i].slots[j] -> activity level 0,1,2
#schedule.uid = f"pattern{pattern_index}_variant{variant_index}"
class ScheduleVariant(BaseModel):
    schedule_uid: str
    workweek_pattern: tuple[int, ...]
    shift_variant_id: str
    schedule: list[list[int]]  # [DAY][SLOT] -> activity level 0,1,2


class ModelBuilder:
    """Builds and solves a CP-SAT scheduling model from a completed ScenarioContext.

    MVP implementation is intentionally monolithic — all model construction,
    constraint generation, and solving happens inside build_and_solve().
    Internal structure is deferred until the engine layer above it is complete.
    """

    def build_and_solve(self, roster: Roster, queues: dict[str, QueueProfile], demand: SlotMatrix) -> SolveRun:
        """Read context, build CP-SAT model, solve, return result."""

        DEBUG = True

        if DEBUG:
            print("Entered build_and_solve", flush=True)

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
        #schedule_variants = (pattern, variant) -> [DAY][SLOT]        

        self._model = CpModel()

        schedule_variants = []
        schedule_variant_slots = []

        for pattern_index, pattern in enumerate(VALID_WORK_WEEK_PATTERNS):
            for variant_index, variant in enumerate(shift_variants):
                schedule_uid = f"pattern{pattern_index}_variant{variant_index}"
                schedule_variants.append({
                    "schedule_uid": schedule_uid,
                })

                schedule = []
                for day in DAYS:
                    if day in pattern:
                        schedule.append(list(variant.slot_activity))
                    else:
                        schedule.append([0] * 48)

                for day in DAYS:
                    for slot in SLOTS:
                        activity = schedule[day][slot]
                        schedule_variant_slots.append({
                            "schedule_uid": schedule_uid,
                            "day": day,
                            "slot": slot,
                            "activity": activity,
                        })
        import pandas as pd

        df_schedule_variants = pd.DataFrame(schedule_variants)
        df_schedule_variant_slots = pd.DataFrame(schedule_variant_slots)

        #agents df
        agents = []
        id_counter = 0
        for entry in roster.entries:
            for i in range(entry.count):
                agents.append({
                    "agent_id": f"agent_{id_counter}",
                    "skill": entry.skills[0],
                })
                if len(entry.skills) > 1:
                    agents.append({
                        "agent_id": f"agent_{id_counter}",
                        "skill": entry.skills[1],
                    })
                id_counter += 1
        
        df_agents = pd.DataFrame(agents)

        #demand df
        demand_rows = []
        for (day, slot, skill), dem in demand.values.items():
            demand_rows.append({
                "day": day,
                "slot": slot,
                "skill": skill,
                "demand": dem,
            })
        
        df_demand = pd.DataFrame(demand_rows)
        crossproduct = (pd.merge(df_agents.assign(key=1), df_schedule_variants.assign(key=1), on="key").drop("key", axis=1)
                          .merge(df_schedule_variant_slots, on="schedule_uid")
                          .merge(df_demand, on=["day", "slot", "skill"], how="left")
                          .fillna({"demand": 0})
        )
        #get distinct agent/schedule_uid pairs, add bool var for each
        df_decision_agent_schedule = (crossproduct[["agent_id", "schedule_uid"]].drop_duplicates().reset_index(drop=True)
                                      .assign(decision_agent_schedule=lambda df: df.apply(lambda row: self._model.NewBoolVar(f"agent_{row['agent_id']}_schedule_{row['schedule_uid']}"), axis=1))
        )
        #at max, one schedule variant can be chosen per agent
        (df_decision_agent_schedule
            .groupby("agent_id")["decision_agent_schedule"]
            .apply(lambda vars: self._model.Add(sum(vars) <= 1))
        )
        #get distinct agent/day/slot pairs, add bool var for each
        df_decision_agent_slot_skill = (crossproduct[["agent_id", "day", "slot"]].drop_duplicates().reset_index(drop=True)
                                        .assign(decision_agent_slot=lambda df: df.apply(lambda row: self._model.NewBoolVar(f"agent_{row['agent_id']}_day_{row['day']}_slot_{row['slot']}"), axis=1))
        )
         #at max, agent can only be present once per day/slot
        (df_decision_agent_slot_skill
            .groupby(["agent_id", "day", "slot"])["decision_agent_slot"]
            .apply(lambda vars: self._model.Add(sum(vars) <= 1))
        )

        #merge crossproduct with decision vars to get problem space, do not include redundant columns
        problem_space = (pd.merge(crossproduct, df_decision_agent_schedule, on=["agent_id", "schedule_uid"])
                           .merge(df_decision_agent_slot_skill, on=["agent_id", "day", "slot"])
                           #add helper var, if either decision var is 1
                           .assign(decision_vars_active=lambda df: df.apply(lambda row: self._model.NewBoolVar(f"agent_{row['agent_id']}_day_{row['day']}_slot_{row['slot']}_schedule_{row['schedule_uid']}"), axis=1))
        )
        (problem_space
            .apply(lambda row: self._model.Add(row["decision_vars_active"] == 1).OnlyEnforceIf([row["decision_agent_schedule"], row["decision_agent_slot"]]), axis=1)
        )

        #Add supply var - multiplication equality, activity x decision_vars_active
        problem_space = (problem_space
            .assign(supply=lambda df: df.apply(lambda row: self._model.NewIntVar(0, 2, f"supply_{row['skill']}_{row['day']}_{row['slot']}_schedule_{row['schedule_uid']}"), axis=1))
        )
        (problem_space
            .apply(lambda row: self._model.AddMultiplicationEquality(row["supply"], [row["decision_vars_active"], row["activity"]]), axis=1)
        )
        
        #first IR - collapse to one row per skill/day/slot, sum supply, max demand, add shortfall var (max 0, demand - supply)
        df_supply_shortfall = (problem_space
            .groupby(["skill", "day", "slot"])
            .agg(supply_sum=("supply", "sum"), demand_max=("demand", "max"))
            .reset_index()
            .assign(shortfall=lambda df: df.apply(lambda row: self._model.NewIntVar(0, SCALED_UB, f"shortfall_{row['skill']}_{row['day']}_{row['slot']}"), axis=1))
        )
        (df_supply_shortfall
            .apply(lambda row: self._model.Add(row["shortfall"] >= row["demand_max"] - row["supply_sum"]), axis=1)
            .apply(lambda row: self._model.Add(row["shortfall"] >= 0), axis=1)
        )
        #objective - minimize sum of shortfall
        self._model.Minimize(df_supply_shortfall["shortfall"].sum())
        solver = CpSolver()
        solver.parameters.max_time_in_seconds = 120
        solver.parameters.num_search_workers = 8
        solver.parameters.log_search_progress = True
        solver.parameters.cp_model_presolve = True
        status = solver.Solve(self._model)
        print(f"Solver status: {solver.StatusName(status)}")
        




#         for pattern_index, pattern in enumerate(VALID_WORK_WEEK_PATTERNS):
#             for variant_index, variant in enumerate(shift_variants):
#                 schedule_uid = f"pattern{pattern_index}_variant{variant_index}"

#                 schedule = []
#                 for day in DAYS:
#                     if day in pattern:
#                         schedule.append(list(variant.slot_activity))
#                     else:
#                         schedule.append([0] * 48)

#                 var_registry.add(
#                     schedule,
#                     type="schedule_variant",
#                     schedule_uid=schedule_uid,
#                     workweek_pattern=pattern,
#                     shift_variant_id=variant.variant_id,
#                 )

#                 for day in DAYS:
#                     for slot in SLOTS:
#                         activity = schedule[day][slot]
#                         #force activity to int
#                         activity = int(activity)
#                         var_registry.add(
#                             activity,
#                             type="schedule_variant_slot",
#                             schedule_uid=schedule_uid,
#                             day=day,
#                             slot=slot,
#                             activity=activity,
#                         )
#         if DEBUG:
#             print("Beginning agent variable generation", flush=True)

#         #query all schedule variants with tags , print to csv
#         schedule_vars = var_registry.query_with_tags(type="schedule_variant")
#         print_schedules = []
#         print_shifts = []
#         for row in schedule_vars:
#             print_schedules.append({
#                 "schedule_uid": row["schedule_uid"],
#                 "workweek_pattern": row["workweek_pattern"],
#                 "shift_variant_id": row["shift_variant_id"],
#             })
#         shift_vars = var_registry.query_with_tags(type="schedule_variant_slot")
#         for row in shift_vars:
#             print_shifts.append({
#                 "schedule_uid": row["schedule_uid"],
#                 "day": row["day"],
#                 "slot": row["slot"],
#                 "activity": row["activity"],
#             })
#         #print to csv
#         import pandas as pd
#         df_schedules = pd.DataFrame(print_schedules)
#         df_schedules.to_csv("schedule_variants.csv", index=False)
#         df_shifts = pd.DataFrame(print_shifts)
#         df_shifts.to_csv("schedule_variant_slots.csv", index=False)

#         agents = []
#         for entry in roster.entries:
#             primary = entry.skills[0]
#             secondary = entry.skills[1] if len(entry.skills) > 1 else None

#             for i in range(entry.count):
#                 skill_key = "_".join(entry.skills)
#                 agents.append({
#                     "id": f"{skill_key}_{i + 1}",
#                     "primary": primary,
#                     "secondary": secondary,
#                     "skills": entry.skills,
#                 })
#         #add demand consts to registry
#         #print demand curve and flush


#         if DEBUG:
#             print("Beginning agent schedule variant assignment", flush=True)
#         for agent in agents:
#             for row in var_registry.query_with_tags(type="schedule_variant"):
#                 schedule_uid = row["schedule_uid"]

#                 agent_schedule_variant_var = self._model.NewBoolVar(f"agent_{agent['id']}_schedule_{schedule_uid}")

#                 var_registry.add(
#                     agent_schedule_variant_var,
#                     type="agent_schedule_variant",
#                     agent=agent["id"],
#                     schedule_uid=schedule_uid,
#                 )
#             print("activity=2 index size:", len(var_registry._index["activity"][2]))
#             print("activity=1 index size:", len(var_registry._index["activity"][1]))
#             print("activity=0 index size:", len(var_registry._index["activity"][0]))
#             # 1. raw index lookup — bypass query entirely
#             raw = var_registry._index["activity"][2]
#             print("raw index hits for activity=2:", len(raw))
#             first_idx = next(iter(raw))
#             print("first entry:", var_registry._entries[first_idx])
#             # 2. query with just activity=2, no other filters
#             results = var_registry.query_with_tags(activity=2)
#             print("query activity=2 only:", len(results))
#             # 3. add type filter
#             results = var_registry.query_with_tags(type="schedule_variant_slot", activity=2)
#             print("query type+activity=2:", len(results))            
#             # 4. add day
#             results = var_registry.query_with_tags(type="schedule_variant_slot", day=2, activity=2)
#             print("query type+day+activity=2:", len(results))
#             # 5. add slot
#             results = var_registry.query_with_tags(type="schedule_variant_slot", day=2, slot=20, activity=2)
#             print("query type+day+slot+activity=2:", len(results))
#             agent_schedule_vars = var_registry.query(type="agent_schedule_variant", agent=agent["id"])
#             self._model.Add(sum(agent_schedule_vars) == 1)
#         if DEBUG:
#             print("Beginning agent slot activity variable generation", flush=True)
#         for day in DAYS:
#             if DEBUG:
#                 print(f"Generating agent slot activity variables for day {day}", flush=True)
#             for slot in SLOTS:
#                 if DEBUG:
#                     print(f"Generating agent slot activity variables for day {day}, slot {slot}", flush=True)
#                 for activity in [0, 1, 2]:
#                     relevant_schedule_vars = var_registry.query_with_tags(type="schedule_variant_slot", 
#                                                                           day=day, 
#                                                                           slot=slot, 
#                                                                           activity=activity)
#                     relevant_schedule_uids = [row["schedule_uid"] for row in relevant_schedule_vars]
#                     #if no relevant schedule uids, skip to next activity
#                     if not relevant_schedule_uids:
#                         continue
                    
#                     if activity != 0:
#                         raise ValueError(f"Actually found nonzero activity for day {day}, slot {slot}: {relevant_schedule_uids}")
#                     for agent in agents:
#                         any_var = self._model.NewBoolVar(f"agent_{agent['id']}_day{day}_slot{slot}_activity{activity}")
#                         var_registry.add(
#                             any_var,
#                             type="agent_slot_activity",
#                             agent=agent["id"],
#                             day=day,
#                             slot=slot,
#                             activity=activity,
#                         )
#                         relevant_agent_schedule_vars = var_registry.query(type="agent_schedule_variant", 
#                                                                           agent=agent["id"], 
#                                                                           schedule_uid=relevant_schedule_uids)
#                         self._model.Add(sum(relevant_agent_schedule_vars) >= 1).OnlyEnforceIf(any_var)
#                         self._model.Add(sum(relevant_agent_schedule_vars) == 0).OnlyEnforceIf(any_var.Not())
#         if DEBUG:
#             print("Beginning agent slot presence and intensity variable generation", flush=True)
#         for agent in agents:
#             for day in DAYS:
#                 for slot in SLOTS:
#                     present_var = self._model.NewBoolVar(
#                         f"agent_{agent['id']}_day{day}_slot{slot}_present"
#                     )
#                     var_registry.add(
#                         present_var,
#                         type="agent_slot_present",
#                         agent=agent["id"],
#                         day=day,
#                         slot=slot,
#                     )

#                     intensity_var = self._model.NewIntVar(
#                         0, 2,
#                         f"agent_{agent['id']}_day{day}_slot{slot}_intensity"
#                     )
#                     var_registry.add(
#                         intensity_var,
#                         type="agent_slot_intensity",
#                         agent=agent["id"],
#                         day=day,
#                         slot=slot,
#                     )

#                     # skill-level vars
#                     skill_present_vars = {}
#                     skill_intensity_vars = {}

#                     for skill in agent["skills"]:
#                         skill_present_var = self._model.NewBoolVar(
#                             f"agent_{agent['id']}_day{day}_slot{slot}_skill_{skill}_present"
#                         )
#                         var_registry.add(
#                             skill_present_var,
#                             type="agent_skill_slot_present",
#                             agent=agent["id"],
#                             day=day,
#                             slot=slot,
#                             skill=skill,
#                         )
#                         skill_present_vars[skill] = skill_present_var

#                         skill_intensity_var = self._model.NewIntVar(
#                             0, 2,
#                             f"agent_{agent['id']}_day{day}_slot{slot}_skill_{skill}_intensity"
#                         )
#                         var_registry.add(
#                             skill_intensity_var,
#                             type="agent_skill_slot_intensity",
#                             agent=agent["id"],
#                             day=day,
#                             slot=slot,
#                             skill=skill,
#                         )
#                         skill_intensity_vars[skill] = skill_intensity_var

#                         self._model.AddMultiplicationEquality(
#                             skill_intensity_var,
#                             [intensity_var, skill_present_var],
#                         )

#                     # enforce skill selection logic
#                     if agent["secondary"] is None:
#                         # only one skill: if agent is present, skill is present
#                         only_skill = next(iter(skill_present_vars.values()))
#                         self._model.Add(only_skill == present_var)
#                     else:
#                         primary_skill = agent["primary"]
#                         secondary_skill = agent["secondary"]

#                         primary_present = skill_present_vars[primary_skill]
#                         secondary_present = skill_present_vars[secondary_skill]

#                         # if agent absent -> both skills absent
#                         # if agent present -> exactly one of these skills is active
#                         self._model.Add(primary_present + secondary_present == present_var)
#                     any2_var = var_registry.query_one(
#                         default=None,
#                         type="agent_slot_activity",
#                         agent=agent["id"],
#                         day=day,
#                         slot=slot,
#                         activity=2,
#                     )
#                     any1_var = var_registry.query_one(
#                         default=None,
#                         type="agent_slot_activity",
#                         agent=agent["id"],
#                         day=day,
#                         slot=slot,
#                         activity=1,
#                     )
#                     any0_var = var_registry.query_one(
#                         default=None,
#                         type="agent_slot_activity",
#                         agent=agent["id"],
#                         day=day,
#                         slot=slot,
#                         activity=0,
#                     )
#                     #See if a single one of these queries every produces something other than None
#                     #print and crash if any are not none
#                     if any2_var is not None or any1_var is not None or any0_var is not None:
#                         print(f"Agent {agent['id']} Day {day} Slot {slot}: any2_var={any2_var}, any1_var={any1_var}, any0_var={any0_var}", flush=True)
#                         raise ValueError("Actually found an anyvar")

#                     if any2_var is not None:
#                         self._model.Add(intensity_var == 2).OnlyEnforceIf(any2_var)
#                     if any1_var is not None:
#                         self._model.Add(intensity_var == 1).OnlyEnforceIf(any1_var)
#                     if any0_var is not None:
#                         self._model.Add(intensity_var == 0).OnlyEnforceIf(any0_var)

#                     if any2_var is not None:
#                         self._model.Add(present_var == 1).OnlyEnforceIf(any2_var)
#                     if any1_var is not None:
#                         self._model.Add(present_var == 1).OnlyEnforceIf(any1_var)
#                     if any0_var is not None:
#                         self._model.Add(present_var == 0).OnlyEnforceIf(any0_var)
#         skills = set(skill for agent in agents for skill in agent["skills"])
#         if DEBUG:
#             print("Beginning coverage and shortfall variable generation", flush=True)
#         for skill in skills:
#             for day in DAYS:
#                 for slot in SLOTS:
#                     coverage_var = self._model.NewIntVar(
#                         0, SCALED_UB,
#                         f"coverage_{skill}_{day}_{slot}"
#                     )
#                     var_registry.add(
#                         coverage_var,
#                         type="coverage",
#                         skill=skill,
#                         day=day,
#                         slot=slot,
#                     )

#                     skill_coverage_vars = var_registry.query(
#                         type="agent_skill_slot_intensity",
#                         skill=skill,
#                         day=day,
#                         slot=slot,
#                     )

#                     self._model.Add(coverage_var == sum(skill_coverage_vars))

#                     demand_const = demand.get(day, slot, skill)
#                     print(f"Demand const: Day {day}, Slot {slot}, Skill {skill}: Found {demand_const}", flush=True)
#                     #print(f"Searched for demand const: Day {day}, Slot {slot}, Skill {skill}: Found {demand_const}")

#                     shortfall_var = self._model.NewIntVar(
#                         0, SCALED_UB,
#                         f"shortfall_{skill}_{day}_{slot}"
#                     )
#                     var_registry.add(
#                         shortfall_var,
#                         type="shortfall",
#                         skill=skill,
#                         day=day,
#                         slot=slot,
#                     )

#                     self._model.Add(shortfall_var >= demand_const - coverage_var)
#                     self._model.Add(shortfall_var >= 0)

#         all_shortfalls = var_registry.query(type="shortfall")
#         self._model.Minimize(sum(all_shortfalls))
#         if DEBUG:
#             print("Model built, beginning solve", flush=True)

      
#         all_supply = var_registry.query(type="coverage")
        
#         solver = CpSolver()
#         solver.parameters.max_time_in_seconds = 120
#         solver.parameters.num_search_workers = 8
#         solver.parameters.log_search_progress = True
#         solver.parameters.cp_model_presolve = True

#         status = solver.Solve(self._model)

#         print(f"Solver status: {solver.StatusName(status)}")
#         if status in (OPTIMAL, FEASIBLE):
#             print(f"Objective value: {solver.ObjectiveValue()}")

#         supply = SlotMatrix(label="supply", values={})
#         shortfall = SlotMatrix(label="shortfall", values={})
#         if status in (OPTIMAL, FEASIBLE):
#             for skill in skills:
#                 for day in DAYS:
#                     for slot in SLOTS:
#                         coverage_var = var_registry.query_one(type="coverage", default = 0, skill=skill, day=day, slot=slot)
#                         coverage_val = solver.Value(coverage_var)
#                         supply.values[(day, slot, skill)] = coverage_val // 2 # HALF-SLOT SCALING

#                         shortfall_var = var_registry.query_one(type="shortfall", default = 0, skill=skill, day=day, slot=slot)
#                         shortfall_val = solver.Value(shortfall_var)
#                         shortfall.values[(day, slot, skill)] = shortfall_val // 2 # HALF-SLOT SCALING
#         else:
#             print("No solution found.")
#         solve_run = SolveRun(
#             run_id="test_run_001",
#             label="Test Run 001",
#             demand=demand,
#             supply=supply,
#             shortfall=shortfall,
#             roster=roster
#         )
#         return solve_run

        

