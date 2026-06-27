from solver.var_registry import VarRegistry

#add a var with a few tags
v = VarRegistry()
v.add("test_value", type="test_type", skill="skill1", day=1, slot=2)
v.add("test_value2", type="test_type", skill="skill2", day=1, slot=2)
v.add("test_value3", type="test_type", skill="skill1", day=2, slot=2)
v.add("test_value4", type="test_type", skill="skill1", day=1, slot=3)

#query with tags
skill_2 = v.query_with_tags(type="test_type", skill="skill2")
assert len(skill_2) == 1
skill_2_day_1 = v.query_with_tags(type="test_type", skill="skill2", day=1)
assert len(skill_2_day_1) == 1
skill_2_day_3 = v.query_with_tags(type="test_type", skill="skill2", day=3)
assert len(skill_2_day_3) == 0
