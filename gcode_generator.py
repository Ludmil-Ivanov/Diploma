# gcode_generator.py
import os
import cv2
#import numpy as np
import math

def export_haas(outer_contour, features, bore_mill, outer_mill, skip_outer, skip_bore, pixels_per_mm, center_x_px, center_y_px, outer_shape, part_thickness):

    output_dir = "Output_nc"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    file_name = "haas_vf2_output.nc"
    out_path = os.path.join(output_dir, file_name)

    # Depth clearence
    drill_z_depth = -(part_thickness + 5.0)        # Drill depth clearence
    profile_z_depth = -(part_thickness + 2)        # Mill depth clearence

    # Cancel any active compensations with G40
    gcode = ["%", "O0032", "G00 G40 G80 G90 G54", "G00 Z50.0"]
    tool_num = 1
    current_tool_num = None

    # Drilling
    holes = [f for f in features if f['shape'] == 'hole']
    if holes:
        gcode.append("(--- DRILLING ---)")
        gcode.append(f"T{tool_num} M06\nS2500 M03\nG43 H{tool_num} Z50.0 M08")
        current_tool_num = tool_num
        tool_num += 1
        
        first = True
        for h in holes:
            if first:
                gcode.append(f"G00 X{h['cnc_x']:.3f} Y{h['cnc_y']:.3f}")
                gcode.append(f"G81 Z{drill_z_depth:.3f} R2.0 F200.")
                first = False
            else:
                gcode.append(f"X{h['cnc_x']:.3f} Y{h['cnc_y']:.3f}")
        gcode.append("G80 M09\nG00 Z50.0")

    # Internal boss milling
    bore_tool_num = None
    if not skip_bore and bore_mill and bore_mill > 0 and holes:
        gcode.append("(--- INTERNAL HOLE MILLING ---)")
        gcode.append(f"T{tool_num} M06")
        gcode.append(f"S4500 M03\nG43 H{tool_num} Z50.0 M08")
        current_tool_num = tool_num
        bore_tool_num = tool_num
        tool_num += 1

        for h in holes:
            hx, hy = h['cnc_x'], h['cnc_y']
            hole_dia = h.get('raw_dia', 10.0)
            hole_rad = hole_dia / 2.0

            if bore_mill < hole_dia:
                gcode.append(f"G00 X{hx:.3f} Y{hy:.3f} (Rapid to center of the boss #{h['id']})")
                gcode.append(f"G01 Z{profile_z_depth:.3f} F200. (Plunge at center)")
                gcode.append(f"G41 D{bore_tool_num} G01 X{hx + hole_rad:.3f} Y{hy:.3f} F400. (Lead-in with G41)")
                gcode.append(f"G03 X{hx + hole_rad:.3f} Y{hy:.3f} I{-hole_rad:.3f} J0.0 (Full circle boring CCW)")
                gcode.append(f"G40 G01 X{hx:.3f} Y{hy:.3f} (Lead-out and cancel G41 with G40)")
                gcode.append("G00 Z50.0")
            elif bore_mill == hole_dia:
                gcode.append(f"G00 X{hx:.3f} Y{hy:.3f}")
                gcode.append(f"G01 Z{profile_z_depth:.3f} F200.")
                gcode.append("G00 Z50.0")

    # Outer profile milling
    if not skip_outer and outer_contour is not None:
        gcode.append(f"(--- OUTER PROFILE: {outer_shape.upper()} ---)")
        
        use_same_tool = (outer_mill == bore_mill) and (bore_tool_num is not None) and (not skip_bore)
        
        if use_same_tool:
            active_tool_num = bore_tool_num
            if current_tool_num != active_tool_num:
                gcode.append(f"T{active_tool_num} M06")
                gcode.append(f"S4500 M03\nG43 H{active_tool_num} Z50.0 M08")
                current_tool_num = active_tool_num
        else:
            gcode.append(f"T{tool_num} M06")
            gcode.append(f"S4500 M03\nG43 H{tool_num} Z50.0 M08")
            active_tool_num = tool_num
            current_tool_num = tool_num
            tool_num += 1

        safe_clearance = 5.0
        rect = cv2.minAreaRect(outer_contour)

        if outer_shape == 'circle':
            real_radius = (max(rect[1]) / pixels_per_mm) / 2.0
            start_x = real_radius + safe_clearance
            
            gcode.append(f"G00 X{start_x:.3f} Y0.0 (Safe position)")
            gcode.append(f"G01 Z{profile_z_depth:.3f} F200.")
            gcode.append(f"G41 D{active_tool_num} X{real_radius:.3f} Y0.0 F600. (Lead-in with G41)")
            gcode.append(f"G02 X{real_radius:.3f} Y0.0 I{-real_radius:.3f} J0.0 (Full circle CW)")
            gcode.append(f"G40 G01 X{start_x:.3f} Y0.0 (Lead-out and cancel G41)")

        else:
            box = cv2.boxPoints(rect)
            cnc_pts = []
            for pt in box:
                mx = (pt[0] - center_x_px) / pixels_per_mm
                my = -((pt[1] - center_y_px) / pixels_per_mm)
                cnc_pts.append((mx, my))

            cnc_pts.sort(key=lambda p: math.atan2(p[1], p[0]), reverse=True)
            
            p0_x, p0_y = cnc_pts[0]
            dist = math.hypot(p0_x, p0_y)
            if dist == 0: dist = 1
            app_x = p0_x + (p0_x / dist) * safe_clearance
            app_y = p0_y + (p0_y / dist) * safe_clearance

            gcode.append(f"G00 X{app_x:.3f} Y{app_y:.3f} (Safe position)")
            gcode.append(f"G01 Z{profile_z_depth:.3f} F200.")
            gcode.append(f"G41 D{active_tool_num} X{p0_x:.3f} Y{p0_y:.3f} F600. (Lead-in with G41)")
            
            for i in range(1, 4):
                gcode.append(f"G01 X{cnc_pts[i][0]:.3f} Y{cnc_pts[i][1]:.3f}")
                
            gcode.append(f"G01 X{p0_x:.3f} Y{p0_y:.3f} (Close contour)")
            gcode.append(f"G40 G01 X{app_x:.3f} Y{app_y:.3f} (Lead-out and cancel G41)")

        gcode.append("G01 Z5.0 F1000.\nM09")

    gcode.extend(["G00 Z50.0 M05", "G00 G40 G80 G90 G53 ZO", "G53 Y0", "M30", "%"])

    with open(out_path, "w") as f:
        f.write("\n".join(gcode))
        
    return out_path


