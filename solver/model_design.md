
## Inputs:

queues - only needed as canonical list of skills
|  skill_id  |  ...
|------------|-----
|  str       |  ...
height = num skills

roster
|  primary_skill_id  |  secondary_skill_id  |  num_agents
|--------------------|----------------------|-------------
|  str               |  str                 |  int
height = num (primary skill, secondary skill)

demand - 
|  skill_id  |  day_id  |  slot_idx  |  demand  | {supply_val} | {shortfall_obj}
|------------|----------|------------|----------|--------------|----------
|   str      |  0..6    |  0..47     |  int     |  None        |  None
height = num skills x (7 days x 48 slots)


## Constants / Derived Inputs:
schedules - 7 day-off patterns x 4 start times x 5 shift patterns = 140 schedule variants
|  schedule_id  |  workweek_id  |  start_time_id  |  shift_pattern_id  |  day_id  |
|---------------|---------------|-----------------|--------------------|----------|
|  0..139*      |   0..6        |  0..3           |  0..4              |  0..6    |
height = 140 


schedule_slots - 140 schedule variants x 7 days x 48 slots = 47,040 schedule slots
[...schedules cols...]|  block_idx  |  slot_idx  |  activity  |
                      |-------------|------------|------------|
                      |  0..19      |  0..47     |  0,1,2

schedule_blocks - 140 schedule variants x 20 blocks = 2,800 schedule blocks
[...schedules cols...]|  block_idx  |
                      |-------------|
                      |  0..19      |
height = 2,800

## Derived Views:
roster_schedules
|  skillgroup  |  roster_schedule_idx  |  num_agents  |  workweek_id_var  |   start_time_id_var  |  shift_pattern_id_var  |  schedule_id_val  |  agents_assigned_schedule_var
|--------------|-----------------------|--------------|-------------------|----------------------|------------------------|-------------------|-----------------------------
|  str         |  0..agent_count-1     |  int         |  0..6             |  0..3                |  0..4                  |  0..139           |  0..n
height = total agent count (max possible unique schedules)

roster_schedule_blocks
[...roster_schedules cols...]|  skill_id  |  block_idx  |  agents_assigned_block_var
                             |------------|-------------|---------------------------
                             |  str       |  0..19      |  0..n
height = roster_schedules x skills in skillgroup x 20 blocks

skill_slots
|  skill_id  |  day_id  |  block_idx  |  slot_idx  |  demand  |  supply_val  |  shortfall_obj
|------------|----------|-------------|------------|----------|--------------|----------
|   str      |  0..6    |  0..19      |  0..47     |  int     |  int         |  int
height = 47,040

roster_schedule_gates
|  skillgroup  |  roster_schedule_idx  |  schedule_id  |  roster_schedule_gate
|--------------|-----------------------|---------------|-------------------------------
|  str         |  0..agent_count-1     |  0..139       |  0,1
height = roster schedules x schedules

roster_schedule_block_gates
[...roster_schedule_gats cols...]|  block_idx  |  roster_schedule_block_gate
                                 |-------------|-------------------------------
                                 |  0..19      |  0,1
height = roster schedule gates x 20 blocks

## Outputs:
Sum of shortfall

Shortfall is calculated as max(0, demand - supply) for each interval, across all skills. Supply is calculated as the sum of agents assigned to that skill in that interval, with a x1 modifier if they're scheduled for break, or x2 modifier if they're scheduled for work.

## Solver Methodology:
Decision variables:
- workweek_id_var, start_time_id_var, shift_pattern_id_var, agents_assigned_schedule_var, all per roster_schedule_idx over skillgroup
- agents_assigned_block_var, per roster_schedule_idx over skillgroup and block_idx

Per roster_schedule_idx over skillgroup, solver selects workweek_id_var, start_time_id_var, shift_pattern_id_var, agents_assigned_schedule_var
    ...schedule_id_val is derived from those composite vars
        ...which activates gate in roster_schedule_gates
            ...which activates gates in roster_schedule_block_gates
Sum of agents_assigned_block_var over skillgroup must equal num_agents in roster for that skillgroup
For dual-skill skillgroups, per block_idx over skill, solver selects agents_assigned_block_var
    ...sum of agents_assigned_block_var for block over skill must equal agents_assigned_schedule_var that agents_assigned_schedule_var
For single-skill skillgroups, agents_assigned_block_var equals agents_assigned_schedule_var for all blocks



