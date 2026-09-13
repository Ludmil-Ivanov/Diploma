# vision.py
import cv2
import numpy as np
import math

CIRCULARITY_THRESHOLD = 0.82

def calibrate_and_warp(image_path):
    """
    Detects 4 ArUco markers to correct perspective.
    Calculates the dynamic scale (pixels per mm),
    """
    # Real distance between the calibration markers in mm
    W, H = 150.0, 237.0 

    img = cv2.imread(image_path)
    if img is None: 
        raise ValueError("Image file not found.")

    if len(img.shape) == 3:
        gray_original = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray_original = img

    params = cv2.aruco.DetectorParameters()
    params.adaptiveThreshWinSizeMax = 53
    params.adaptiveThreshWinSizeStep = 10

    dicts = [
        cv2.aruco.DICT_4X4_50, cv2.aruco.DICT_4X4_250,
        cv2.aruco.DICT_5X5_50, cv2.aruco.DICT_5X5_250,
        cv2.aruco.DICT_6X6_50, cv2.aruco.DICT_6X6_250,
        cv2.aruco.DICT_7X7_50, cv2.aruco.DICT_7X7_250,
        cv2.aruco.DICT_ARUCO_ORIGINAL
    ]

    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    preprocessing_steps = [
        gray_original,
        clahe.apply(gray_original),
        cv2.GaussianBlur(gray_original, (5, 5), 0)
    ]

    corners, ids = None, None

    for gray in preprocessing_steps:
        for d_id in dicts:
            detector = cv2.aruco.ArucoDetector(cv2.aruco.getPredefinedDictionary(d_id), params)
            c, i, _ = detector.detectMarkers(gray)

            if i is not None and len(i) >= 4:
                corners, ids = c[:4], i[:4]
                break
        if ids is not None and len(ids) == 4:
            break

    if ids is None or len(ids) < 4:
        raise ValueError("Markers not found! Make sure all 4 markers are visible and clear.")

    centers = np.array([np.mean(c[0], axis=0) for c in corners])
    s = centers.sum(axis=1)
    diff = np.diff(centers, axis=1)

    src_pts = np.array([
        centers[np.argmin(s)],    # Top-Left
        centers[np.argmin(diff)], # Top-Right
        centers[np.argmax(s)],    # Bottom-Right
        centers[np.argmax(diff)]  # Bottom-Left
    ], dtype="float32")

    width_px = max(np.linalg.norm(src_pts[1] - src_pts[0]), np.linalg.norm(src_pts[2] - src_pts[3]))
    height_px = max(np.linalg.norm(src_pts[3] - src_pts[0]), np.linalg.norm(src_pts[2] - src_pts[1]))

    dw, dh = int(width_px), int(height_px)
    
    scale_x = dw / W
    scale_y = dh / H

    dst_pts = np.array([[0, 0], [dw - 1, 0], [dw - 1, dh - 1], [0, dh - 1]], dtype="float32")
    matrix = cv2.getPerspectiveTransform(src_pts, dst_pts)
    warped = cv2.warpPerspective(img, matrix, (dw, dh))

    return warped, scale_x, scale_y


def analyze_part(warped, scale_x=1.0, scale_y=1.0, part_thickness_mm=0.0):

    if warped is None: return None, [], 0, 0, 'rectangle', 0, 0, None

    labeled_image = warped.copy()
    if len(warped.shape) == 3:
        gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)
    else:
        gray = warped

    total_warp_area = warped.shape[0] * warped.shape[1]

    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray = clahe.apply(cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY) if len(warped.shape) == 3 else warped)
    blurred = cv2.GaussianBlur(gray, (7, 7), 0)

    otsu_val, _ = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    strict_val = otsu_val * 0.75

    min_allowable_area = total_warp_area * 0.05
    max_allowable_area = total_warp_area * 0.40

    # Initial contour detection for mask testing
    _, mask_solid = cv2.threshold(blurred, strict_val, 255, cv2.THRESH_BINARY_INV)
    kernel_solid = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 25))
    mask_solid = cv2.morphologyEx(mask_solid, cv2.MORPH_CLOSE, kernel_solid)
    contours_solid, _ = cv2.findContours(mask_solid, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    valid_solid = [c for c in contours_solid if min_allowable_area < cv2.contourArea(c) < max_allowable_area]
    if not valid_solid: 
        raise ValueError("Part contour not found or invalid size.")
    outer_cnt_solid = max(valid_solid, key=cv2.contourArea)

    M = cv2.moments(outer_cnt_solid)
    if M['m00'] == 0: return None, [], 0, 0, 'rectangle', 0, 0, None

    peri = cv2.arcLength(outer_cnt_solid, True)
    circ = (4 * math.pi * M['m00']) / (peri ** 2) if peri > 0 else 0
    shape_type = 'circle' if circ > 0.82 else 'rectangle'

    if len(labeled_image.shape) == 2:
        labeled_image = cv2.cvtColor(labeled_image, cv2.COLOR_GRAY2BGR)

    # Boss detection
    mask_holes = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                       cv2.THRESH_BINARY_INV, 41, 5)

    kernel_open_h = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    mask_holes = cv2.morphologyEx(mask_holes, cv2.MORPH_OPEN, kernel_open_h)

    contours_all, hierarchy = cv2.findContours(mask_holes, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    raw_candidates = []
    if hierarchy is not None:
        hierarchy = hierarchy[0]
        for i, cnt in enumerate(contours_all):
            m = cv2.moments(cnt)
            
            if m['m00'] < M['m00'] * 0.002 or m['m00'] > M['m00'] * 0.08: 
                continue

            fx, fy = m['m10'] / m['m00'], m['m01'] / m['m00']

            f_peri = cv2.arcLength(cnt, True)
            f_circ = (4 * math.pi * m['m00']) / (f_peri ** 2) if f_peri > 0 else 0
            f_rect = cv2.minAreaRect(cnt)
            f_ar = min(f_rect[1]) / max(f_rect[1]) if max(f_rect[1]) > 0 else 0

            if (f_circ > 0.50 or f_ar > 0.60) and cv2.pointPolygonTest(outer_cnt_solid, (fx, fy), False) >= 0:
                if hierarchy[i][3] != -1:
                    raw_candidates.append({'cnt': cnt, 'px_x': fx, 'px_y': fy, 'px_area': m['m00']})

    raw_candidates = sorted(raw_candidates, key=lambda c: c['px_area'], reverse=True)
    
    features_px = []
    fid = 1

    selected_holes = raw_candidates[:2]
    selected_holes = sorted(selected_holes, key=lambda c: c['px_y'])

    for cand in selected_holes:
        features_px.append({
            'id': fid, 'px_x': cand['px_x'], 'px_y': cand['px_y'], 'px_area': cand['px_area'], 'is_hole': True
        })
        cv2.drawContours(labeled_image, [cand['cnt']], -1, (255, 0, 0), 2)
        cv2.putText(labeled_image, f"#{fid}", (int(cand['px_x']) - 15, int(cand['px_y']) + 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3)
        fid += 1

    # Centering
    bx, by, bw, bh = cv2.boundingRect(outer_cnt_solid)
    w_px = bw
    pcx = bx + (bw / 2.0)
    pcy = by + (bh / 2.0)
    h_px = bh

    if len(features_px) == 2:
        h1, h2 = features_px[0], features_px[1]
        top_margin_px = h1['px_y'] - by
        bottom_edge_y = h2['px_y'] + top_margin_px
    
        h_px = bottom_edge_y - by
        pcy = by + (h_px / 2.0)

    # Z compensation
    CAMERA_HEIGHT_MM = 240.0  # The distance between the camera and the markers plane
    if CAMERA_HEIGHT_MM > part_thickness_mm and part_thickness_mm > 0:
        height_correction_factor = 1.0 - (part_thickness_mm / CAMERA_HEIGHT_MM)
        w_px = w_px * height_correction_factor
        h_px = h_px * height_correction_factor
        bx = pcx - (w_px / 2.0)
        by = pcy - (h_px / 2.0)

    # Draw Final Geometry
    if shape_type == 'rectangle':
        perfect_cnt = np.array([
            [[int(bx), int(by)]], 
            [[int(bx + w_px), int(by)]], 
            [[int(bx + w_px), int(by + h_px)]], 
            [[int(bx), int(by + h_px)]]
        ], dtype=np.int32)
        cv2.drawContours(labeled_image, [perfect_cnt], 0, (0, 255, 0), 2)
    else:
        radius = (w_px + h_px) / 4.0
        cv2.circle(labeled_image, (int(pcx), int(pcy)), int(radius), (0, 255, 0), 2)

    # G54 origin marking (X0 Y0)
    origin_x, origin_y = int(pcx), int(pcy)
    cv2.drawMarker(labeled_image, (origin_x, origin_y), (0, 0, 255), markerType=cv2.MARKER_CROSS, markerSize=90, thickness=6)
    cv2.putText(labeled_image, "X0 Y0", (origin_x + 30, origin_y - 30),
                cv2.FONT_HERSHEY_SIMPLEX, 3, (0, 0, 255), 6)

    return outer_cnt_solid, features_px, w_px, h_px, shape_type, pcx, pcy, labeled_image
