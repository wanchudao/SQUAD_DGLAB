# ============================================================
# vision/suppression/detector_v1_blur.py
#
# Suppression detector v1: blur + chroma shift.
#
# Original algorithm by the SQUAD_DGLAB project, integrated on
# 2026-05-19. Designed for vanilla SQUAD where suppression shows
# up as chromatic aberration plus motion blur.
#
# IMPORTANT - EXPERIMENTAL:
# This detector was tested for ~1 hour in a modded SQUAD server
# on 2026-05-23 and produced heavy false triggers. It is kept
# here as the "vanilla SQUAD mode" but is NOT recommended for
# modded servers.
#
# For modded servers, use detector_v2_vignette instead.
#
# Interface:
#     detector = BlurSuppressionDetector()
#     result = detector.update(frame)
#     # result is a dict with keys:
#     #   event        : None / "suppression_light" / "suppression_heavy"
#     #   score        : float
#     #   blur_ratio   : float
#     #   chroma_shift : float
#     #   state        : "idle" / "active_light" / "active_heavy"
#     #   debug_text   : str
#     detector.reset()
# ============================================================

from __future__ import annotations

from typing import Optional, Dict, Any

import cv2
import numpy as np


class BlurSuppressionDetector(object):
    """
    SQUAD suppression detector v1.

    Uses Laplacian variance as the main blur signal, and B/G/R
    channel mean differences as a chroma-shift safety check.
    Heavy suppression in vanilla SQUAD shows both high blur and
    noticeable chroma shift.
    """

    def __init__(
        self,
        light_threshold=4.0,
        heavy_threshold=6.5,
        exit_threshold=3.2,
        chroma_hard_cap=0.045,
    ):
        self.light_threshold = light_threshold
        self.heavy_threshold = heavy_threshold
        self.exit_threshold = exit_threshold
        self.chroma_hard_cap = chroma_hard_cap

        self.state = "idle"

    def reset(self):
        self.state = "idle"

    def _calc_blur_ratio(self, frame):
        """
        Laplacian variance based blur measure.
        Lower lap_var means blurrier image.
        blur_ratio is inverted so higher means blurrier.
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        lap_var = cv2.Laplacian(gray, cv2.CV_64F).var()

        if lap_var <= 0:
            return 10.0

        blur_ratio = 1000.0 / (lap_var + 1.0)
        return float(blur_ratio)

    def _calc_chroma_shift(self, frame):
        """
        Mean absolute difference between B/G/R channels.
        Heavy suppression in vanilla SQUAD produces a clear
        chromatic aberration that lifts this value.
        Plain motion blur, reflections, and dark scenes usually
        do NOT lift this value.
        """
        b, g, r = cv2.split(frame.astype(np.float32))

        bg = np.mean(np.abs(b - g))
        gr = np.mean(np.abs(g - r))
        rb = np.mean(np.abs(r - b))

        chroma_shift = (bg + gr + rb) / 3.0 / 255.0
        return float(chroma_shift)

    def _calc_score(self, blur_ratio, chroma_shift):
        """
        suppression_score v1.
        blur_score separates normal from heavy.
        chroma_score confirms it is real suppression rather
        than ordinary blur.
        """
        if blur_ratio < 1.5:
            blur_score = 0.0
        elif blur_ratio < 2.5:
            blur_score = 1.0
        elif blur_ratio < 3.5:
            blur_score = 2.0
        elif blur_ratio < 4.5:
            blur_score = 3.5
        elif blur_ratio < 5.5:
            blur_score = 4.8
        elif blur_ratio < 6.5:
            blur_score = 5.8
        elif blur_ratio < 7.5:
            blur_score = 6.8
        else:
            blur_score = 7.6

        if chroma_shift < 0.040:
            chroma_score = 0.0
        elif chroma_shift < 0.060:
            chroma_score = 0.3
        elif chroma_shift < 0.080:
            chroma_score = 0.8
        elif chroma_shift < 0.100:
            chroma_score = 1.2
        elif chroma_shift < 0.130:
            chroma_score = 1.6
        else:
            chroma_score = 2.0

        score = blur_score + chroma_score
        return float(score)

    def _apply_hard_cap(self, score, blur_ratio, chroma_shift):
        """
        Low chroma cap.
        If chroma is too low, refuse to trigger suppression even
        if blur is high. Prevents reflections, black screens,
        plain motion blur from firing.
        """
        if chroma_shift < self.chroma_hard_cap:
            return min(score, 3.9)

        if chroma_shift < 0.060 and blur_ratio < 6.0:
            return min(score, 4.2)

        return score

    def update(self, frame):
        """
        Input a BGR frame, output a result dict.
        See module docstring for the dict schema.
        """
        blur_ratio = self._calc_blur_ratio(frame)
        chroma_shift = self._calc_chroma_shift(frame)

        score = self._calc_score(blur_ratio, chroma_shift)
        score = self._apply_hard_cap(score, blur_ratio, chroma_shift)

        event = None

        if self.state == "idle":
            if score >= self.heavy_threshold:
                self.state = "active_heavy"
                event = "suppression_heavy"
            elif score >= self.light_threshold:
                self.state = "active_light"
                event = "suppression_light"

        elif self.state == "active_light":
            if score >= self.heavy_threshold:
                self.state = "active_heavy"
                event = "suppression_heavy"
            elif score >= self.exit_threshold:
                event = "suppression_light"
            else:
                self.state = "idle"

        elif self.state == "active_heavy":
            if score >= self.heavy_threshold:
                event = "suppression_heavy"
            elif score >= self.exit_threshold:
                self.state = "active_light"
                event = "suppression_light"
            else:
                self.state = "idle"

        debug_text = (
            "state=" + self.state
            + ", score=" + "{:.2f}".format(score)
            + ", blur=" + "{:.2f}".format(blur_ratio)
            + ", chroma=" + "{:.3f}".format(chroma_shift)
        )

        return {
            "event": event,
            "score": score,
            "blur_ratio": blur_ratio,
            "chroma_shift": chroma_shift,
            "state": self.state,
            "debug_text": debug_text,
        }
