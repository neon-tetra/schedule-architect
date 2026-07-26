
#a schedule is a len-17 list representing 30min blocks
#schedules have a break, lunch, and break, denoted b1 l and b2
#the schedule is also assumed to begin at the index before the list and end after
#there must be 3 W blocks between each event
#enumerate all possible combinations that meet the constraints - add the 3 event positions to a list

valid_positions = []

for b1 in range(0, 17):
    for l in range(0, 17):
        for b2 in range(0, 17):
            if (b1 > 2) and (l - b1 > 3) and (b2 - l > 3) and (17 - b2 > 3):
                valid_positions.append((b1, l, b2))
print(valid_positions)

#take the list of valid positions, generate for each a list of 9 hour-blocks
#iterating 2 at a time - if the pair contains no break or lunch, then its a work hour worth 4 - w4

#if it contains a break, its a break hour worth 3 - w3
#if it contains a lunch, or its the last hour block, its w2

valid_schedules = []
for pos in valid_positions:
    schedule = []
    for i in range(0, 17, 2):
        if (i == 16) | (i == pos[1]) | (i+1 == pos[1]):
            schedule.append("w2")
        elif (i == pos[0]) | (i+1 == pos[0]) | (i == pos[2]) | (i+1 == pos[2]):
            schedule.append("w3")
        else:
            schedule.append("w4")
        
    valid_schedules.append(schedule)



#make unique
unique_schedules = []
for schedule in valid_schedules:
    if schedule not in unique_schedules:
        unique_schedules.append(schedule)
print(unique_schedules)
"""
[['w3', 'w4', 'w2', 'w4', 'w3', 'w4', 'w4', 'w4', 'w2'], 
['w3', 'w4', 'w2', 'w4', 'w4', 'w3', 'w4', 'w4', 'w2'], 
['w3', 'w4', 'w2', 'w4', 'w4', 'w4', 'w3', 'w4', 'w2'], 
['w3', 'w4', 'w4', 'w2', 'w4', 'w3', 'w4', 'w4', 'w2'], 
['w3', 'w4', 'w4', 'w2', 'w4', 'w4', 'w3', 'w4', 'w2'], 
['w3', 'w4', 'w4', 'w4', 'w2', 'w4', 'w3', 'w4', 'w2'], 
['w4', 'w3', 'w4', 'w2', 'w4', 'w3', 'w4', 'w4', 'w2'], 
['w4', 'w3', 'w4', 'w2', 'w4', 'w4', 'w3', 'w4', 'w2'], 
['w4', 'w3', 'w4', 'w4', 'w2', 'w4', 'w3', 'w4', 'w2']]
"""