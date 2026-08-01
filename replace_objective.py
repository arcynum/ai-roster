import datetime

file_path = "/Users/arcynum/Code/ai-roster/cp_solver.py"
with open(file_path, "r") as f:
    lines = f.readlines()

start_idx = -1
end_idx = -1
for i, line in enumerate(lines):
    if "        # --- OBJECTIVE FUNCTION ---" in line:
        start_idx = i
    if "        model.Minimize(" in line:
        # We need to find the end of this statement. 
        # It spans multiple lines. Let's look for the next non-empty/comment line after it or just target a fixed range.
        # In the current file, it ends at line 261.
        end_idx = i + 3 # penalty_fte ... sum(pref_violations) is about 3 lines in my count? No, let's check.
        # Let's find the end by searching for "model.Minimize(" and then looking for the closing ")"
        pass

# Let's just use a more robust way to find the block.
# The block starts at "# --- OBJECTIVE FUNCTION ---" 
# and ends after the last line of the model.Minimize call.

start_idx = -1
end_idx = -1
for i, line in enumerate(lines):
    if "        # --- OBJECTIVE FUNCTION ---" in line:
        start_idx = i
    if "        model.Minimize(" in line:
        # The minimize call ends after some lines. 
        # Looking at the file, it's around line 261.
        # Let's just find the next line that isn't part of the Minimize call.
        pass

# Actually, let's search for "model.Minimize(" and then manually specify the end.
# Based on my previous read, the block is:
# 206 to 261.

start_idx = -1
end_idx = -1
for i, line in enumerate(lines):
    if "        # --- OBJECTIVE FUNCTION ---" in line:
        start_idx = i
    if "        model.Minimize(" in line:
        # The Minimize call looks like this:
        #         model.Minimize(penalty_fte * sum(fte_violations) + 
        #                        penalty_weekend * sum(weekend_violations) +
        #                        penalty_preference * sum(pref_violations))
        end_idx = i + 3

if start_idx != -1 and end_idx != -1:
    new_block = [
        "        # --- OBJECTIVE FUNCTION ---",
        "        # We want to minimize deviations and preference violations.",
        "",
        "        # Penalties",
        "        penalty_fte = self.weights.get(\"S#f8c3b0c2\", 1000)",
        "        penalty_night_fairness = self.weights.get(\"S#d2a7f4a6\", 50)",
        "        penalty_weekend = self.weights.get(\"weekend_distribution\", 100)",
        "        penalty_preference = self.weights.get(\"preference_base\", 1)",
        "",
        "        # 1. FTE Deviation",
        "        fte_violations = []",
        "        for s in staff_indices:",
        "            target_fte_scaled = int(self.staff[s].fte_hours * self.SCALE)",
        "            current_fte_scaled = sum(x[s, d, h_name] * int(self.definitions[h_name].duration * self.SCALE)",
        "                                     for d in day_indices for h_name in shift_names)",
        "            under_fte = model.NewIntVar(0, target_fte_scaled, f'under_fte_{s}')",
        "            model.Add(under_fte >= target_fte_scaled - current_fte_scaled)",
        "            model.Add(under_fte >= 0)",
        "            fte_violations.append(under_fte)",
        "",
        "        # 2. Night Shift Fairness (S#d2a7f4a6)",
        "        night_shift_names = [h for h in shift_names if h in [\"N8\", \"N12\"]]",
        "        total_nights_hours_scaled = sum(req.count * int(self.definitions[req.shift_name].duration * self.SCALE) for d_idx in day_indices for req in self.roster_reqs.get(self.dates[d_idx].strftime(\"%A\"), []) if req.shift_name in night_shift_names)",
        "        night_fairness_violations = []",
        "        if total_nights_hours_scaled > 0:",
        "            total_fte_sum = sum(s.fte_hours for s in self.staff)",
        "            for s_idx in staff_indices:",
        "                staff_m = self.staff[s_idx]",
        "                current_night_hours_scaled = sum(x[s_idx, d_idx, h_name] * int(self.definitions[h_name].duration * self.SCALE) for d_idx in day_indices for h_name in night_shift_names)",
        "                target_night_hours_scaled = int(round((staff_m.fte_hours / total_fte_sum) * total_nights_hours_scaled)) if total_fte_sum > 0 else 0",
        "                diff_night_s = model.NewIntVar(0, int(24 * 31 * self.SCALE), f'diff_night_{s_idx}')",
        "                model.AddAbsEquality(diff_night_s, current_night_hours_scaled - target_night_hours_scaled)",
        "                night_fairness_violations.append(diff_night_s)",
        "",
        "        # 3. Weekend Deviation (S#a1d6c3d5)",
        "        weekend_violations = []",
        "        total_weekend_hours_scaled = sum(req.count * int(self.definitions[req.shift_name].duration * self.SCALE) for d_idx in day_indices for req in self.roster_reqs.get(self.dates[d_idx].strftime(\"%A\"), []) if self.dates[d_idx].weekday() >= 5)",
        "        if total_weekend_hours_scaled > 0:",
        "            total_fte_sum = sum(s.fte_hours for s in self.staff)",
        "            for s_idx in staff_indices:",
        "                staff_m = self.staff[s_idx]",
        "                current_weekend_hours_scaled = sum(x[s_idx, d, h_name] * int(self.definitions[h_name].duration * self.SCALE) for d in day_indices for h_name in shift_names if self.dates[d].weekday() >= 5)",
        "                target_weekend_hours_scaled = int(round((staff_m.fte_hours / total_fte_sum) * total_weekend_hours_scaled)) if total_fte_sum > 0 else 0",
        "                weekend_diff = model.NewIntVar(0, int(24 * 31 * self.SCALE), f'weekend_diff_{s_idx}')",
        "                model.AddAbsEquality(weekend_diff, current_weekend_hours_scaled - target_weekend_hours_scaled)",
        "                weekend_violations.append(weekend_diff)",
        "        else:",
        "            pass",
        "",
        "        # 4. Preference Violations",
        "        pref_violations = []",
        "        for s in staff_indices:",
        "            staff_m = self.staff[s]",
        "            for pref in staff_m.preferences:",
        "                pass",
        "",
        "        model.Minimize(penalty_fte * sum(fte_violations) + ",
        "                       penalty_night_fairness * sum(night_fairness_violations) +",
        "                       penalty_weekend * sum(weekend_violations) +",
        "                       penalty_preference * sum(pref_violations))"
    ]
    new_lines = lines[:start_idx] + new_block + lines[end_idx+1:]
    with open(file_path, "w") as f:
        f.writelines(new_lines)
    print(\"Successfully replaced the block.\")
else:
    print(f\"Could not find block. Start: {start_idx}, End: {end_idx}\")
