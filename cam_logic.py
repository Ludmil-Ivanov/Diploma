# cam_logic.py
import os

# Tool load
def load_tools(directory_path):
    tools = []
    if os.path.exists(directory_path) and os.path.isdir(directory_path):
        for filename in os.listdir(directory_path):
            file_path = os.path.join(directory_path, filename)
            if os.path.isfile(file_path):
                with open(file_path, 'r') as f:
                    for line in f:
                        try:
                            val = float(line.strip())
                            if val > 0: tools.append(val)
                        except ValueError: pass
    return sorted(list(set(tools)))

def plan_operations(features, drills):

    report_lines = []
    error_log = []
    needs_mill = False

    if not drills:
        return None, False, "Tool library is empty!"

    min_drill = min(drills)

    for f in features:
        f_id = f.get('id', '?')
        target_dia = f.get('raw_dia', 0)
        shape = f.get('shape', 'unknown')

        # Step 1: Tool size check
        if target_dia < min_drill:
            error_log.append(f"• Feature #{f_id} ({shape}): Detected Ø{target_dia:.2f} mm (Min tool Ø{min_drill})")
            continue

        # Step 2: Tool assignment (if Step 1 passed)
        if shape == 'hole':
            valid_drills = [d for d in drills if d <= target_dia]
            if not valid_drills:
                error_log.append(f"• Hole #{f_id}: No valid drill for Ø{target_dia:.2f}")
                continue

            best_drill = max(valid_drills)
            f['assigned_drill'] = best_drill

            if abs(target_dia - best_drill) <= 0.05:
                f['needs_milling'] = False
                report_lines.append(f"Hole #{f_id}: Drill Ø{best_drill} -> Finish")
            else:
                f['needs_milling'] = True
                needs_mill = True
                report_lines.append(f"Hole #{f_id}: Pre-drill Ø{best_drill} -> Mill to Ø{target_dia:.2f}")

        else: # Non-circle
            f['needs_milling'] = True
            needs_mill = True
            f['assigned_drill'] = min_drill
            report_lines.append(f"Feature #{f_id}: Pocket Milling (Pilot Ø{min_drill})")

    # Step 3: Final report
    if error_log:
        full_error_msg = "🚨 CRITICAL MANUFACTURING ERRORS FOUND:\n\n"
        full_error_msg += "\n".join(error_log)
        full_error_msg += "\n\nACTION: Update tool library or dimensions."
        return None, False, full_error_msg

    return features, needs_mill, "\n".join(report_lines)