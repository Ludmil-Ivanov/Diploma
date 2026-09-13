# main.py
import os
#import sys
import cv2
import math
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk

import vision
import gcode_generator
import cam_logic
import tools


class CNCVerificationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("CNC vision & Verification system")
        
        # Window dimensions and screen centering
        width, height = 1100, 750
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.root.minsize(950, 700)

        # Application variables
        self.file_path = None
        self.warped_img = None
        self.scale_x = 1.0
        self.scale_y = 1.0
        self.part_thickness = 0.0
        self.outer = None
        self.f_px = []
        self.w_px = 0.0
        self.h_px = 0.0
        self.shape = 'rectangle'
        self.pcx = 0.0
        self.pcy = 0.0
        self.labeled_img = None
        self.final_features = []
        self.real_w = 0.0
        self.real_h = 0.0
        self.current_cv_img = None
        self.photo_img = None

        # Create Tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Initialize Tabs
        self.tab_setup = ttk.Frame(self.notebook)
        self.tab_dim = ttk.Frame(self.notebook)
        self.tab_features = ttk.Frame(self.notebook)
        self.tab_export = ttk.Frame(self.notebook)

        self.notebook.add(self.tab_setup, text=" 1. Setup ")
        self.notebook.add(self.tab_dim, text=" 2. Dimension review ")
        self.notebook.add(self.tab_features, text=" 3. Feature verification ")
        self.notebook.add(self.tab_export, text=" 4. G-Code export ")

        # Restrict progression until steps are completed
        self.notebook.tab(1, state="disabled")
        self.notebook.tab(2, state="disabled")
        self.notebook.tab(3, state="disabled")

        self.build_setup_tab()
        self.build_dimension_tab()
        self.build_features_tab()
        self.build_export_tab()

    def build_setup_tab(self):
        container = tk.Frame(self.tab_setup)
        container.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        tk.Label(container, text="Step 1: Select part image & Enter thickness", font=("Arial", 14, "bold")).pack(pady=15)

        f_frame = tk.Frame(container)
        f_frame.pack(pady=10)
        
        tk.Button(f_frame, text="Browse image...", command=self.select_image, font=("Arial", 11, "bold"),
                  bg="#4a90e2", fg="white", width=15, relief=tk.FLAT).pack(side=tk.LEFT, padx=5)
        
        self.lbl_filepath = tk.Label(f_frame, text="No file selected", font=("Arial", 10, "italic"), fg="gray")
        self.lbl_filepath.pack(side=tk.LEFT, padx=5)

        t_frame = tk.Frame(container)
        t_frame.pack(pady=20)
        
        tk.Label(t_frame, text="Enter part thickness (Z mm):", font=("Arial", 11, "bold")).pack(pady=5)
        self.entry_thickness = tk.Entry(t_frame, font=("Arial", 11), width=15, justify=tk.CENTER)
        self.entry_thickness.pack(pady=5)

        tk.Button(container, text="Process image & Continue ->", command=self.process_setup,
                  font=("Arial", 12, "bold"), bg="#2ecc71", fg="white", padx=15, pady=5, relief=tk.FLAT).pack(pady=20)

    def build_dimension_tab(self):
        container = tk.Frame(self.tab_dim)
        container.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        tk.Label(container, text="Step 2: Detected part dimensions review", font=("Arial", 14, "bold")).pack(pady=15)

        card = tk.LabelFrame(container, text=" Optical measurement results ", font=("Arial", 11, "bold"), padx=25, pady=20)
        card.pack(pady=10)

        self.lbl_shape_info = tk.Label(card, text="Detected shape: -", font=("Arial", 11))
        self.lbl_shape_info.pack(anchor="w", pady=5)

        self.lbl_width_info = tk.Label(card, text="Calculated width (X): - mm", font=("Arial", 11))
        self.lbl_width_info.pack(anchor="w", pady=5)

        self.lbl_height_info = tk.Label(card, text="Calculated height (Y): - mm", font=("Arial", 11))
        self.lbl_height_info.pack(anchor="w", pady=5)

        btn_frame = tk.Frame(container)
        btn_frame.pack(pady=20)

        tk.Button(btn_frame, text="Abort & Reshoot", command=self.abort_and_reshoot, 
                  font=("Arial", 11, "bold"), bg="#e74c3c", fg="white", padx=12, pady=8, relief=tk.FLAT).pack(side=tk.LEFT, padx=10)

        tk.Button(btn_frame, text="Continue ->", command=self.proceed_to_features, 
                  font=("Arial", 11, "bold"), bg="#2ecc71", fg="white", padx=15, pady=8, relief=tk.FLAT).pack(side=tk.LEFT, padx=10)

    def build_features_tab(self):
        frame = tk.Frame(self.tab_features, padx=15, pady=15)
        frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(frame, text="Step 3: Feature inspection & Direct table editing", font=("Arial", 14, "bold")).pack(anchor="w", pady=5)
        tk.Label(frame, text="Tip: Double-click any row to edit coordinates (X, Y) or diameter directly.", font=("Arial", 9, "italic"), fg="gray").pack(anchor="w", pady=2)

        split_frame = tk.Frame(frame)
        split_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        left_sub = tk.Frame(split_frame)
        left_sub.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

        right_sub = tk.Frame(split_frame)
        right_sub.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5)

        # Canvas with dynamic resize & center binding
        self.canvas = tk.Canvas(left_sub, bg="#2c3e50", width=450, height=500)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Configure>", self.redraw_image)

        columns = ("ID", "Type", "X (mm)", "Y (mm)", "Ø (mm)")
        self.tree = ttk.Treeview(right_sub, columns=columns, show="headings", height=14)
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=80, anchor=tk.CENTER)
        self.tree.pack(fill=tk.BOTH, expand=True, pady=5)
        self.tree.bind("<Double-1>", self.on_table_double_click)

        edit_frame = tk.LabelFrame(right_sub, text=" Edit selected feature ", font=("Arial", 10, "bold"), padx=10, pady=10)
        edit_frame.pack(fill=tk.X, pady=5)

        lbl_row = tk.Frame(edit_frame)
        lbl_row.pack(fill=tk.X, pady=2)
        tk.Label(lbl_row, text="X:", width=4).pack(side=tk.LEFT)
        self.edit_x = tk.Entry(lbl_row, width=8)
        self.edit_x.pack(side=tk.LEFT, padx=5)

        tk.Label(lbl_row, text="Y:", width=4).pack(side=tk.LEFT)
        self.edit_y = tk.Entry(lbl_row, width=8)
        self.edit_y.pack(side=tk.LEFT, padx=5)

        tk.Label(lbl_row, text="Ø:", width=4).pack(side=tk.LEFT)
        self.edit_dia = tk.Entry(lbl_row, width=8)
        self.edit_dia.pack(side=tk.LEFT, padx=5)

        tk.Button(edit_frame, text="Update row", command=self.update_selected_row, bg="#f39c12", fg="white", font=("Arial", 9, "bold")).pack(anchor="e", pady=5)

        tk.Button(right_sub, text="Confirm & Continue to export ->", command=self.proceed_to_export,
                  font=("Arial", 11, "bold"), bg="#2ecc71", fg="white", padx=10, relief=tk.FLAT).pack(anchor="e", pady=10)

    def build_export_tab(self):
        container = tk.Frame(self.tab_export)
        container.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        tk.Label(container, text="Step 4: Tooling selection & G-Code generation", font=("Arial", 14, "bold")).pack(pady=5)

        drill_frame = tk.LabelFrame(container, text=" Compatible drills selection ", font=("Arial", 10, "bold"), padx=12, pady=5)
        drill_frame.pack(pady=4, fill=tk.X)

        tk.Label(drill_frame, text="Select drill (Filtered ≤ Hole Diameter):", font=("Arial", 9)).pack(anchor="w")
        self.drill_combo_var = tk.StringVar()
        self.drill_combo = ttk.Combobox(drill_frame, textvariable=self.drill_combo_var, font=("Arial", 10), state="readonly", width=25)
        self.drill_combo.pack(pady=2)

        bore_frame = tk.LabelFrame(container, text=" Boss boring End Mill (Optional) ", font=("Arial", 10, "bold"), padx=12, pady=5)
        bore_frame.pack(pady=4, fill=tk.X)

        self.skip_bore_var = tk.BooleanVar(value=False)
        tk.Checkbutton(bore_frame, text="Skip boss bring (Drill only)", variable=self.skip_bore_var,
                       font=("Arial", 9), command=self.toggle_skip_bore).pack(anchor="w", pady=1)

        tk.Label(bore_frame, text="Select End Mill for boss:", font=("Arial", 9)).pack(anchor="w")
        self.mill_combo_var = tk.StringVar()
        self.mill_combo = ttk.Combobox(bore_frame, textvariable=self.mill_combo_var, font=("Arial", 10), state="readonly", width=25)
        self.mill_combo.pack(pady=2)

        outer_frame = tk.LabelFrame(container, text=" Outer profile milling ", font=("Arial", 10, "bold"), padx=12, pady=5)
        outer_frame.pack(pady=4, fill=tk.X)

        self.skip_outer_var = tk.BooleanVar(value=False)
        tk.Checkbutton(outer_frame, text="Skip outer profile milling", variable=self.skip_outer_var,
                       font=("Arial", 9), command=self.toggle_skip_outer).pack(anchor="w", pady=1)

        self.same_mill_var = tk.BooleanVar(value=True)
        self.chk_same_mill = tk.Checkbutton(outer_frame, text="Use same end mill for outer profile as boss",
                                            variable=self.same_mill_var, font=("Arial", 9), command=self.toggle_outer_mill)
        self.chk_same_mill.pack(anchor="w", pady=1)

        sub_outer = tk.Frame(outer_frame)
        sub_outer.pack(fill=tk.X, pady=1)
        tk.Label(sub_outer, text="Different outer mill Ø:", font=("Arial", 9)).pack(side=tk.LEFT)
        self.mill_outer_combo_var = tk.StringVar()
        self.mill_outer_combo = ttk.Combobox(sub_outer, textvariable=self.mill_outer_combo_var, font=("Arial", 10), state="disabled", width=15)
        self.mill_outer_combo.pack(side=tk.LEFT, padx=5)

        tk.Button(container, text="Generate & Export G-Code", command=self.export_gcode, 
                  font=("Arial", 11, "bold"), bg="#2ecc71", fg="white", padx=12, pady=6, relief=tk.FLAT).pack(pady=10)

    def toggle_skip_bore(self):
        if self.skip_bore_var.get():
            self.mill_combo.config(state="disabled")
            self.same_mill_var.set(False)
            self.chk_same_mill.config(state="disabled")
        else:
            self.mill_combo.config(state="readonly")
            self.chk_same_mill.config(state="normal")
            self.toggle_outer_mill()

    def toggle_skip_outer(self):
        if self.skip_outer_var.get():
            self.chk_same_mill.config(state="disabled")
            self.mill_outer_combo.config(state="disabled")
        else:
            if not self.skip_bore_var.get():
                self.chk_same_mill.config(state="normal")
            self.toggle_outer_mill()

    def toggle_outer_mill(self):
        if self.skip_outer_var.get():
            return
        if self.same_mill_var.get():
            self.mill_outer_combo.config(state="disabled")
        else:
            self.mill_outer_combo.config(state="readonly")

    def select_image(self):
        photos_dir = "Photos"
        if not os.path.exists(photos_dir):
            os.makedirs(photos_dir, exist_ok=True)

        path = filedialog.askopenfilename(
            title="Select Part Image",
            initialdir=photos_dir,
            filetypes=[("Image Files", "*.jpg *.jpeg *.png *.bmp")]
        )
        if path:
            self.file_path = path
            self.lbl_filepath.config(text=os.path.basename(path), fg="black")

    def process_setup(self):
        if not self.file_path:
            messagebox.showerror("Error", "Please select an image file first.")
            return

        try:
            thickness_str = self.entry_thickness.get().strip()
            if not thickness_str:
                raise ValueError("Thickness field cannot be empty.")
            self.part_thickness = float(thickness_str)
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter a valid numeric value for part thickness.")
            return

        try:
            self.warped_img, self.scale_x, self.scale_y = vision.calibrate_and_warp(self.file_path)

            self.outer, self.f_px, self.w_px, self.h_px, self.shape, self.pcx, self.pcy, self.labeled_img = vision.analyze_part(
                self.warped_img, self.scale_x, self.scale_y, part_thickness_mm=self.part_thickness
            )

            if self.outer is None:
                messagebox.showerror("Error", "No part detected.")
                return

            self.real_w = self.w_px / self.scale_x
            self.real_h = self.h_px / self.scale_y

            self.lbl_shape_info.config(text=f"Detected shape: {self.shape.upper()}")
            self.lbl_width_info.config(text=f"Calculated width (X): {self.real_w:.3f} mm")
            self.lbl_height_info.config(text=f"Calculated height (Y): {self.real_h:.3f} mm")

            self.notebook.tab(1, state="normal")
            self.notebook.select(1)

        except Exception as e:
            messagebox.showerror("Processing error", str(e))

    def abort_and_reshoot(self):
        self.notebook.tab(1, state="disabled")
        self.notebook.tab(2, state="disabled")
        self.notebook.tab(3, state="disabled")
        self.notebook.select(0)
        self.file_path = None
        self.lbl_filepath.config(text="No file selected", fg="gray")
        self.entry_thickness.delete(0, tk.END)

    def proceed_to_features(self):
        try:
            self.final_features = []
            for f in self.f_px:
                cnc_x = (f['px_x'] - self.pcx) / self.scale_x
                cnc_y = -(f['px_y'] - self.pcy) / self.scale_y
                dia_mm = (2 * math.sqrt(f['px_area'] / math.pi)) / ((self.scale_x + self.scale_y) / 2.0)

                self.final_features.append({
                    'id': f['id'], 'shape': 'hole' if f['is_hole'] else 'pocket',
                    'cnc_x': cnc_x, 'cnc_y': cnc_y, 'raw_dia': dia_mm,
                    'cx_px': f['px_x'], 'cy_px': f['px_y']
                })

            TOLERANCE_MM = 1.5
            for i in range(len(self.final_features)):
                for j in range(i + 1, len(self.final_features)):
                    if abs(self.final_features[i]['cnc_x'] - self.final_features[j]['cnc_x']) <= TOLERANCE_MM:
                        avg_x = (self.final_features[i]['cnc_x'] + self.final_features[j]['cnc_x']) / 2.0
                        self.final_features[i]['cnc_x'] = avg_x
                        self.final_features[j]['cnc_x'] = avg_x
                    if abs(self.final_features[i]['cnc_y'] - self.final_features[j]['cnc_y']) <= TOLERANCE_MM:
                        avg_y = (self.final_features[i]['cnc_y'] + self.final_features[j]['cnc_y']) / 2.0
                        self.final_features[i]['cnc_y'] = avg_y
                        self.final_features[j]['cnc_y'] = avg_y

            self.refresh_table()
            self.display_image(self.labeled_img)

            self.notebook.tab(2, state="normal")
            self.notebook.select(2)

        except Exception as e:
            messagebox.showerror("Error", str(e))

    def refresh_table(self):
        for row in self.tree.get_children():
            self.tree.delete(row)

        for feat in self.final_features:
            self.tree.insert("", tk.END, values=(
                f"#{feat['id']}", feat['shape'],
                f"{feat['cnc_x']:.3f}", f"{feat['cnc_y']:.3f}", f"{feat['raw_dia']:.3f}"
            ))

    def on_table_double_click(self, event):
        selected_item = self.tree.selection()
        if not selected_item:
            return
        item_values = self.tree.item(selected_item, "values")
        if item_values:
            self.edit_x.delete(0, tk.END)
            self.edit_x.insert(0, item_values[2])
            self.edit_y.delete(0, tk.END)
            self.edit_y.insert(0, item_values[3])
            self.edit_dia.delete(0, tk.END)
            self.edit_dia.insert(0, item_values[4])

    def update_selected_row(self):
        selected_item = self.tree.selection()
        if not selected_item:
            messagebox.showwarning("Selection warning", "Please select a row from the table to update.")
            return

        idx = self.tree.index(selected_item[0])
        try:
            new_x = float(self.edit_x.get())
            new_y = float(self.edit_y.get())
            new_dia = float(self.edit_dia.get())

            self.final_features[idx]['cnc_x'] = new_x
            self.final_features[idx]['cnc_y'] = new_y
            self.final_features[idx]['raw_dia'] = new_dia

            self.refresh_table()
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter valid numeric values for X, Y, and Diameter.")

    def display_image(self, cv_img):
        self.current_cv_img = cv_img
        self.redraw_image()

    def redraw_image(self, event=None):
        if self.current_cv_img is None:
            return
        
        c_width = self.canvas.winfo_width()
        c_height = self.canvas.winfo_height()
        if c_width < 10 or c_height < 10:
            return

        max_w = max(100, c_width - 20)
        max_h = max(100, c_height - 20)

        cv_img_rgb = cv2.cvtColor(self.current_cv_img, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(cv_img_rgb)
        pil_img.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
        self.photo_img = ImageTk.PhotoImage(pil_img)
        
        self.canvas.delete("all")
        self.canvas.create_image(c_width // 2, c_height // 2, image=self.photo_img, anchor=tk.CENTER)

    def proceed_to_export(self):
        self.notebook.tab(3, state="normal")
        self.notebook.select(3)

        drill_path = os.path.join("Drills", "HSS_Drills")
        all_drills = []
        if os.path.exists(drill_path):
            with open(drill_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            all_drills.append(float(line))
                        except ValueError:
                            pass
        else:
            drill_dir = getattr(tools, 'DRILLS_DIR', 'tools/drills')
            all_drills = cam_logic.load_tools(drill_dir)

        max_hole_dia = max([f['raw_dia'] for f in self.final_features], default=10.0)
        filtered_drills = [d for d in all_drills if d <= max_hole_dia]
        self.drill_combo['values'] = filtered_drills
        if filtered_drills:
            self.drill_combo.current(0)

        mill_dir = getattr(tools, 'MILLS_DIR', 'tools/mills')
        all_mills = cam_logic.load_tools(mill_dir)
        filtered_mills = [m for m in all_mills if m <= max_hole_dia]
        if not filtered_mills:
            filtered_mills = all_mills
        
        self.mill_combo['values'] = filtered_mills
        if filtered_mills:
            self.mill_combo.current(0)

        self.mill_outer_combo['values'] = all_mills
        if all_mills:
            self.mill_outer_combo.current(0)

    def export_gcode(self):
        skip_outer = self.skip_outer_var.get()
        skip_bore = self.skip_bore_var.get()

        if skip_bore:
            bore_mill = None
        else:
            try:
                bore_mill = float(self.mill_combo_var.get())
            except ValueError:
                bore_mill = None

        if skip_outer:
            outer_mill = None
        else:
            if self.same_mill_var.get():
                outer_mill = bore_mill
            else:
                try:
                    outer_mill = float(self.mill_outer_combo_var.get())
                except ValueError:
                    outer_mill = bore_mill

        drill_dir = getattr(tools, 'DRILLS_DIR', 'tools/drills')
        drills = cam_logic.load_tools(drill_dir)
        planned, needs_mill, report = cam_logic.plan_operations(self.final_features, drills)

        out_path = gcode_generator.export_haas(
            self.outer, planned, bore_mill, outer_mill, skip_outer, skip_bore,
            self.scale_x, self.pcx, self.pcy, self.shape, self.part_thickness
        )
        
        messagebox.showinfo("Success", f"G-code successfully generated and saved to:\n{out_path}")
        self.reset_application()

    def reset_application(self):
        self.file_path = None
        self.warped_img = None
        self.scale_x = 1.0
        self.scale_y = 1.0
        self.part_thickness = 0.0
        self.outer = None
        self.f_px = []
        self.final_features = []
        self.real_w = 0.0
        self.real_h = 0.0
        self.current_cv_img = None

        self.lbl_filepath.config(text="No file selected", fg="gray")
        self.entry_thickness.delete(0, tk.END)
        self.canvas.delete("all")
        
        for row in self.tree.get_children():
            self.tree.delete(row)

        self.edit_x.delete(0, tk.END)
        self.edit_y.delete(0, tk.END)
        self.edit_dia.delete(0, tk.END)

        self.skip_bore_var.set(False)
        self.skip_outer_var.set(False)
        self.same_mill_var.set(True)
        self.mill_combo.config(state="readonly")
        self.chk_same_mill.config(state="normal")
        self.mill_outer_combo.config(state="disabled")

        self.notebook.tab(1, state="disabled")
        self.notebook.tab(2, state="disabled")
        self.notebook.tab(3, state="disabled")
        self.notebook.select(0)


if __name__ == "__main__":
    root = tk.Tk()
    app = CNCVerificationApp(root)
    root.mainloop()
