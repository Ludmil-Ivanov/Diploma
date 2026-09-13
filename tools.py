# tools.py
import os

# --- Directories ---
DRILLS_DIR = "Drills"
MILLS_DIR = "Mills"
OUTPUT_DIR = "Output_nc"

# Ensure directories exist
for directory in [DRILLS_DIR, MILLS_DIR, OUTPUT_DIR]:
    if not os.path.exists(directory):
        os.makedirs(directory)