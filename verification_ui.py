# verification_ui.py
import tkinter as tk
import cv2
from PIL import Image, ImageTk

def center_window(win):
    # GUI centering

    win.update_idletasks()
    width = win.winfo_width()
    height = win.winfo_height()
    x = (win.winfo_screenwidth() // 2) - (width // 2)
    y = (win.winfo_screenheight() // 2) - (height // 2)
    win.geometry(f'{width}x{height}+{x}+{y}')


def verify_part_size(pw, ph):
  #Step 1: Verify part dimension

    dialog = tk.Toplevel()
    dialog.title("Sanity Check: Part Dimensions")
    dialog.geometry("380x220")
    dialog.grab_set()

    result = {'proceed': False}

    tk.Label(dialog, text="Detected Overall Part Size", font=('Arial', 12, 'bold')).pack(pady=10)

    dim_frame = tk.Frame(dialog)
    dim_frame.pack(pady=10)

    tk.Label(dim_frame, text="Width (X):", font=('Arial', 11, 'bold')).grid(row=0, column=0, sticky="e", padx=5)
    tk.Label(dim_frame, text=f"{pw:.2f} mm", font=('Arial', 11)).grid(row=0, column=1, sticky="w", padx=5)

    tk.Label(dim_frame, text="Height (Y):", font=('Arial', 11, 'bold')).grid(row=1, column=0, sticky="e", padx=5)
    tk.Label(dim_frame, text=f"{ph:.2f} mm", font=('Arial', 11)).grid(row=1, column=1, sticky="w", padx=5)

    def on_confirm():
        result['proceed'] = True
        dialog.destroy()

    def on_abort():
        result['proceed'] = False
        dialog.destroy()

    btn_frame = tk.Frame(dialog)
    btn_frame.pack(pady=15)

    tk.Button(btn_frame, text="Abort & Re-shoot", command=on_abort, bg="#f44336", fg="white",
              font=('Arial', 10, 'bold'), padx=10).pack(side=tk.LEFT, padx=10)
    tk.Button(btn_frame, text="Confirm Size", command=on_confirm, bg="#4CAF50", fg="white", font=('Arial', 10, 'bold'),
              padx=10).pack(side=tk.LEFT, padx=10)

    center_window(dialog)
    dialog.wait_window()
    return result['proceed']


def verify_features(features, labeled_img):
   # Step 2: Feature verification

    dialog = tk.Toplevel()
    dialog.title("Engineering Dimension & Position Verification")
    dialog.geometry("1050x600")
    dialog.grab_set()

    left_frame = tk.Frame(dialog, width=520)
    left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)

    right_frame = tk.Frame(dialog)
    right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=10)

    if labeled_img is not None:
        rgb_img = cv2.cvtColor(labeled_img, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb_img)

        pil_img.thumbnail((500, 500))

        photo = ImageTk.PhotoImage(pil_img)
        img_label = tk.Label(left_frame, image=photo)
        img_label.image = photo
        img_label.pack(expand=True)
    else:
        tk.Label(left_frame, text="Reference map not found", font=('Arial', 12, 'italic')).pack(expand=True)

    # Data Table
    tk.Label(right_frame, text="CNC coordinate verification (Center = X0 Y0)", font=('Arial', 11, 'bold')).pack(pady=10)

    table_container = tk.Frame(right_frame)
    table_container.pack(fill=tk.BOTH, expand=True)

    # Table Headers
    headers = ["ID", "Type", "X (mm)", "Y (mm)", "Ø (mm)"]
    for col, text in enumerate(headers):
        tk.Label(table_container, text=text, font=('Arial', 9, 'bold')).grid(row=0, column=col, padx=8, pady=5)

    entries = []

    for i, f in enumerate(features):
        # Feature #ID
        tk.Label(table_container, text=f"#{i + 1}").grid(row=i + 1, column=0, pady=3)

        # Shape naming
        display_shape = f['shape'].replace('circle', 'boss').replace('non-circle', 'pocket').title()
        tk.Label(table_container, text=display_shape).grid(row=i + 1, column=1, pady=3)

        # X Coordinate entry
        entry_x = tk.Entry(table_container, width=9, justify='center')
        entry_x.insert(0, f"{f['cnc_x']:.3f}")
        entry_x.grid(row=i + 1, column=2, padx=2)

        # Y Coordinate entry
        entry_y = tk.Entry(table_container, width=9, justify='center')
        entry_y.insert(0, f"{f['cnc_y']:.3f}")
        entry_y.grid(row=i + 1, column=3, padx=2)

        # Diameter Entry (Only if it's a boss)
        if f['shape'] in ['circle', 'hole']:
            entry_d = tk.Entry(table_container, width=9, justify='center', bg="#ffffff")  #
            entry_d.insert(0, f"{f['raw_dia']:.3f}")
            entry_d.grid(row=i + 1, column=4, padx=2)
        else:
            tk.Label(table_container, text="N/A", fg="gray").grid(row=i + 1, column=4)
            entry_d = None

        entries.append((f, entry_x, entry_y, entry_d))

    def on_confirm():
        for f, ex, ey, ed in entries:
            try:
                f['cnc_x'] = float(ex.get().replace(',', '.'))
                f['cnc_y'] = float(ey.get().replace(',', '.'))
                if ed is not None:
                    f['raw_dia'] = float(ed.get().replace(',', '.'))
            except ValueError:
                pass  # Keeps previous value if user enters text
        dialog.destroy()

    tk.Button(right_frame, text="Confirm CNC Data & Export",
              command=on_confirm, bg="#4CAF50", fg="white",
              font=('Arial', 10, 'bold'), pady=10, padx=20).pack(pady=20)

    center_window(dialog)
    dialog.wait_window()
    return features