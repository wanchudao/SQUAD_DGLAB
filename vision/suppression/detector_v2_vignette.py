# ============================================================
# vision/suppression/detector_v2_vignette.py
#
# Suppression detector v2: vignette + corner darkness.
#
# Designed for modded SQUAD servers where suppression shows
# up as a heavy black vignette around the screen edges with
# the center still relatively visible. No blur, no chroma
# shift in this scenario.
#
# Calibrated on 2026-05-23 against 18 sample frames (6 heavy
# suppression, 12 non-suppression). Achieved 18/18 correct
# classification with the thresholds below.
#
# IMPORTANT - EXPERIMENTAL:
# This detector is specifically for modded servers. It will
# NOT detect vanilla SQUAD suppression (which uses chromatic
# aberration + blur, see detector_v1_blur).
#
# Interface:
#     detector = VignetteSuppressionDetector()
#     result = detector.update(frame)
#     # result is a dict with keys:
#     #   event        : None / "suppression_light" / "suppression_heavy"
#     #   score        : float        (vignette_score for compat)
#     #   blur_ratio   : float        (always 0.0, v2 does not use blur)
#     #   chroma_shift : float        (always 0.0, v2 does not use chroma)
#     #   state        : "idle" / "active_light" / "active_heavy"
#     #   debug_text   : str
#     detector.reset()
# ============================================================

from __future__ import annotations

import cv2
import numpy as np


# ----- Region geometry -----
CENTER_RATIO = 0.40       # central square side as fraction of min(W, H)
CORNER_RATIO = 0.25       # corner patch side as fraction of min(W, H)

# UI mask: ignore the bottom strip to avoid HUD elements
UI_BOTTOM_RATIO = 0.15
UI_LEFT_RATIO = 0.20
UI_RIGHT_RATIO = 0.20

# ----- Classification thresholds (verified 18/18 on samples) -----
CORNERS_DARK_MAX = 8           # corners 30th-percentile brightness ceiling
VIGNETTE_HEAVY = 0.90          # heavy suppression vignette floor
VIGNETTE_LIGHT = 0.70          # light suppression vignette floor
CENTROID_OFFSET_MAX = 0.10     # luminance centroid offset ceiling
EDGE_RATIO_MAX = 0.025         # canny edge ratio ceiling (excludes UI)

# ----- State machine timing -----
HEAVY_FRAMES_REQUIRED = 4      # ~2.0s at 0.5s/frame
LIGHT_FRAMES_REQUIRED = 2      # ~1.0s at 0.5s/frame
EXIT_FRAMES_REQUIRED = 3       # ~1.5s of normal frames to drop back to idle


class VignetteSuppressionDetector(object):
    """
    SQUAD suppression detector v2 (vignette based).
    """

    def __init__(self):
        self.state = "idle"
        self.heavy_streak = 0
        self.light_streak = 0
        self.normal_streak = 0

    def reset(self):
        self.state = "idle"
        self.heavy_streak = 0
        self.light_streak = 0
        self.normal_streak = 0

    # --------------------------------------------------------
    # Region helpers
    # --------------------------------------------------------
    def _split_regions(self, gray):
        """
        Return (center_patch, list_of_4_corner_patches).
        center_patch is a square at the geometric center.
        corner patches are squares at the 4 corners.
        """
        h, w = gray.shape[:2]
        side = int(min(w, h) * CENTER_RATIO)
        cx = w // 2
        cy = h // 2
        x1 = max(cx - side // 2, 0)
        y1 = max(cy - side // 2, 0)
        x2 = min(x1 + side, w)
        y2 = min(y1 + side, h)
        center = gray[y1:y2, x1:x2]

        cside = int(min(w, h) * CORNER_RATIO)
        c_tl = gray[0:cside, 0:cside]
        c_tr = gray[0:cside, w - cside:w]
        c_bl = gray[h - cside:h, 0:cside]
        c_br = gray[h - cside:h, w - cside:w]

        return center, [c_tl, c_tr, c_bl, c_br]

    def _compute_vignette_score(self, gray):
        """
        vignette = (center_brightness - corners_brightness) / center_brightness
        Higher means corners are darker relative to center.
        """
        center, corners = self._split_regions(gray)

        # 50th percentile for center, 30th percentile for corners
        center_b = float(np.percentile(center, 50)) if center.size > 0 else 0.0
        corner_vals = []
        for c in corners:
            if c.size == 0:
                continue
            corner_vals.append(float(np.percentile(c, 30)))

        if not corner_vals:
            return 0.0, center_b, 0.0

        corners_b = float(np.mean(corner_vals))

        if center_b <= 0.0:
            return 0.0, center_b, corners_b

        vignette = (center_b - corners_b) / center_b
        if vignette < 0.0:
            vignette = 0.0

        return vignette, center_b, corners_b

    def _compute_centroid_offset(self, gray):
        """
        Distance from luminance centroid to image center,
        normalized to image diagonal length 1.0.
        Big offset means the bright area is off-center
        (e.g. a flashlight, a window, a bright UI on one side),
        which is NOT modded suppression.
        """
        h, w = gray.shape[:2]
        if h == 0 or w == 0:
            return 0.0

        total = float(gray.sum())
        if total <= 0.0:
            return 0.0

        ys = np.arange(h, dtype=np.float32).reshape(-1, 1)
        xs = np.arange(w, dtype=np.float32).reshape(1, -1)

        cy = float((gray * ys).sum()) / total
        cx = float((gray * xs).sum()) / total

        norm_x = cx / float(w)
        norm_y = cy / float(h)

        dx = norm_x - 0.5
        dy = norm_y - 0.5
        offset = float(np.sqrt(dx * dx + dy * dy))
        return offset

    def _compute_edge_ratio(self, gray):
        """
        Canny edge density, with the bottom HUD strip excluded.
        Modded suppression frames are smooth (low edges).
        Cockpits / vehicles / heavy UI frames have high edges.
        """
        h, w = gray.shape[:2]
        if h == 0 or w == 0:
            return 0.0

        ui_top = int(h * (1.0 - UI_BOTTOM_RATIO))
        masked = gray[0:ui_top, :]

        if masked.size == 0:
            return 0.0

        edges = cv2.Canny(masked, 60, 160)
        ratio = float((edges > 0).sum()) / float(edges.size)
        return ratio

    def _compute_dark_ratio(self, gray):
        """
        Fraction of pixels with brightness < 25.
        Reported for debug only.
        """
        if gray.size == 0:
            return 0.0
        return float((gray < 25).sum()) / float(gray.size)

    # --------------------------------------------------------
    # Single-frame classification
    # --------------------------------------------------------
    def _classify(self, vignette, corners_b, centroid_off, edge_ratio):
        """
        Returns one of:
            "SUPPRESSION_HEAVY"
            "SUPPRESSION_LIGHT"
            "OFFCENTER_LIGHT"   (rejected: bright area off-center)
            "VEHICLE_OR_UI"     (rejected: too many edges)
            "NORMAL"
        """
        if centroid_off > CENTROID_OFFSET_MAX:
            return "OFFCENTER_LIGHT"
        if edge_ratio > EDGE_RATIO_MAX:
            return "VEHICLE_OR_UI"
        if corners_b <= CORNERS_DARK_MAX and vignette >= VIGNETTE_HEAVY:
            return "SUPPRESSION_HEAVY"
        if corners_b <= CORNERS_DARK_MAX and vignette >= VIGNETTE_LIGHT:
            return "SUPPRESSION_LIGHT"
        return "NORMAL"

    # --------------------------------------------------------
    # Main entry
    # --------------------------------------------------------
    def update(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        vignette, center_b, corners_b = self._compute_vignette_score(gray)
        centroid_off = self._compute_centroid_offset(gray)
        edge_ratio = self._compute_edge_ratio(gray)
        dark_ratio = self._compute_dark_ratio(gray)

        single = self._classify(vignette, corners_b, centroid_off, edge_ratio)

        is_heavy = (single == "SUPPRESSION_HEAVY")
        is_light = (single == "SUPPRESSION_LIGHT")
        is_normal_like = (single in ("NORMAL", "OFFCENTER_LIGHT", "VEHICLE_OR_UI"))

        # Streak counters
        if is_heavy:
            self.heavy_streak += 1
            self.light_streak += 1
            self.normal_streak = 0
        elif is_light:
            self.heavy_streak = 0
            self.light_streak += 1
            self.normal_streak = 0
        else:
            self.heavy_streak = 0
            self.light_streak = 0
            self.normal_streak += 1

        # State transitions
        event = None
        prev_state = self.state

        if self.state == "idle":
            if self.heavy_streak >= HEAVY_FRAMES_REQUIRED:
                self.state = "active_heavy"
                event = "suppression_heavy"
            elif self.light_streak >= LIGHT_FRAMES_REQUIRED:
                self.state = "active_light"
                event = "suppression_light"

        elif self.state == "active_light":
            if self.heavy_streak >= HEAVY_FRAMES_REQUIRED:
                self.state = "active_heavy"
                event = "suppression_heavy"
            elif self.normal_streak >= EXIT_FRAMES_REQUIRED:
                self.state = "idle"
            else:
                # Still suppressed, re-emit light only when the single-frame
                # result currently classifies as suppression. This keeps the
                # event tied to real frames, not to a stuck state.
                if is_heavy or is_light:
                    event = "suppression_light"

        elif self.state == "active_heavy":
            if self.normal_streak >= EXIT_FRAMES_REQUIRED:
                self.state = "idle"
            else:
                if is_heavy:
                    event = "suppression_heavy"
                elif is_light:
                    event = "suppression_light"

        debug_text = (
            "state=" + self.state
            + ", vignette=" + "{:.2f}".format(vignette)
            + ", cob=" + "{:.0f}".format(corners_b)
            + ", off=" + "{:.2f}".format(centroid_off)
            + ", edge=" + "{:.3f}".format(edge_ratio)
        )

        return {
            "event": event,
            "score": float(vignette),
            "blur_ratio": 0.0,
            "chroma_shift": 0.0,
            "state": self.state,
            "debug_text": debug_text,
        }
