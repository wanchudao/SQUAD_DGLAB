"""
vision/suppression/__init__.py

Suppression detector factory.

Mode is controlled by env var SQUAD_SUPPRESSION_MODE:
    off       default, no suppression detection (returns NullDetector)
    blur      v1 detector (BlurSuppressionDetector), vanilla SQUAD
    vignette  v2 detector (VignetteSuppressionDetector), modded SQUAD

Usage:
    from suppression import get_detector
    detector = get_detector(verbose=True)
    result = detector.update(frame)
"""

import os


__all__ = ["get_detector"]


# =========================
# Null detector (off mode)
# =========================

class _NullDetector(object):
    """
    No-op detector used when SQUAD_SUPPRESSION_MODE=off (default).

    update() always returns a "no event" result so the vision main loop
    can call it unconditionally without None checks.
    """

    def update(self, frame):
        return {
            "event": None,
            "score": 0.0,
            "blur_ratio": 0.0,
            "chroma_shift": 0.0,
            "state": "off",
            "debug_text": "off",
        }

    def reset(self):
        # No state to reset.
        pass


# =========================
# Factory
# =========================

def get_detector(verbose=False):
    """
    Return a suppression detector instance based on env var
    SQUAD_SUPPRESSION_MODE.

    Args:
        verbose: print which mode was selected.

    Returns:
        An object with .update(frame) -> dict and .reset() methods.
    """
    mode = os.environ.get("SQUAD_SUPPRESSION_MODE", "off").strip().lower()

    if mode == "blur":
        # v1: blur + chroma shift, vanilla SQUAD
        from .detector_v1_blur import BlurSuppressionDetector
        if verbose:
            print("[SUPPRESSION] mode=blur (v1, vanilla SQUAD), "
                  "class=BlurSuppressionDetector")
        return BlurSuppressionDetector()

    if mode == "vignette":
        # v2: corner-darkness + vignette, modded SQUAD
        from .detector_v2_vignette import VignetteSuppressionDetector
        if verbose:
            print("[SUPPRESSION] mode=vignette (v2, modded SQUAD), "
                  "class=VignetteSuppressionDetector")
        return VignetteSuppressionDetector()

    # default / off / unknown
    if verbose:
        if mode in ("", "off"):
            print("[SUPPRESSION] mode=off (default, no detection)")
        else:
            print("[SUPPRESSION] unknown mode '" + mode
                  + "', fallback to off")

    return _NullDetector()
