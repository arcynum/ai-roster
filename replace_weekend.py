import datetime

file_path = "/Users/arcynum/Code/ai-roster/cp_solver.py"
with open(file_path, "r") as f:
    lines = f.readlines()

start_idx = -1
end_idx = -1
for i, line in enumerate(lines):
    if "        # Weekend Deviation" in line:
        start_idx = i
    if "            weekend_violations.append(weekend_under)" in line:
        end_idx = i

if start_idx != -1 and end_idx != -1:
    new_block = [
        "        # 3. Weekend Deviation (S#a1d6c3d5)\n",
        "        weekend_violations = []\n",
        "        total_weekend_hours_requested = sum(req.count * self.definitions[req.shift_name].duration for d_idx in day_indices for req in self.roster_reqs.get(self.dates[d_idx].strftime(\"%A\"), []) if self.dates[d_idx].weekday() >= 5)\n",
        "        if total_weekend_hours_requested > 0:\n",
        "            total_fte_sum = sum(s.fte_hours for s in self.staff)\n",
        "            for s_idx in staff_indices:\n",
        "                staff_m = self.staff[s_idx]\n",
        "                current_weekend_scaled = sum(x[s_idx, d, h_name] * int(self.definitions[h_name].duration * self.SCALE)\n",
        "                                             for d in day_indices for h_name in shift_names\n",
        "                                             if self.dates[d].weekday() >= 5)\n",
        "                target_weekend_scaled = int(round((staff_m.fte_hours / total_fte_sum) * total_weekend_hours_requested * self.SCALE)) if total_fte_sum > 0 else 0\n",
        "                weekend_diff = model.NewIntVar(0, int(24 * 31 * self.SCALE), f'weekend_diff_{s_idx}')\n",
        "                model.AddAbsEquality(weekend_diff, current_weekend_scaled - target_weekend_scaled)\n",
        "                weekend_violations.append(weekend_diff)\n",
        "        else:\n",
        "            pass\n"
    ]
    new_lines = lines[:start_idx] + new_block + lines[end_idx+1:]
    with open(file_path, "w") as f:
        f.writelines(new_lines)
    print("Successfully replaced the block.")
else:
    print(f"Could not find block. Start: {start_idx}, End: {end_idx}")
