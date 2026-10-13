"""
Comex Browser Nervous System: viewport and coordinate geometry.

A screenshot the model looks at lives in its own pixel space. Mouse events live in CSS viewport pixels.
This module owns the conversion between them and the rule that makes it safe: a coordinate taken from
one screenshot is only valid while the viewport it was taken from is unchanged. Pure functions, no I/O.

Spaces:
    screenshot pixels  - what the model sees and points at (possibly downscaled)
    CSS viewport px    - what Input.dispatchMouseEvent expects (already includes browser zoom)
Device-pixel ratio does not enter the click maths: CDP input and Page.getLayoutMetrics both use CSS
pixels, so DPR is recorded for diagnostics only.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Optional, Tuple

# Largest image we hand to the model: bounds token cost and keeps small text legible.
DEFAULT_MAX_IMAGE_DIM = 1280
DEFAULT_MAX_IMAGE_AREA = 1_150_000


@dataclass(frozen=True)
class ViewportInfo:
    """Geometry of one screenshot, captured together with the page it describes."""

    screenshot_id: str
    viewport_width: int          # CSS px
    viewport_height: int         # CSS px
    screenshot_width: int        # px of the image the model sees
    screenshot_height: int
    device_pixel_ratio: float = 1.0
    scroll_x: float = 0.0
    scroll_y: float = 0.0
    document_generation: int = 0  # world-state counter: changes on every document replacement
    taken_at_mono: float = field(default_factory=time.monotonic)

    @property
    def scale(self) -> float:
        """Screenshot pixels per CSS pixel."""
        return self.screenshot_width / self.viewport_width if self.viewport_width else 1.0


def scale_for(width: int, height: int,
              max_dim: int = DEFAULT_MAX_IMAGE_DIM,
              max_area: int = DEFAULT_MAX_IMAGE_AREA) -> float:
    """Downscale factor (<= 1.0) that fits a width x height viewport inside the image budget."""
    if width <= 0 or height <= 0:
        return 1.0
    scale = 1.0
    area = width * height
    if area > max_area:
        scale = math.sqrt(max_area / area)
    longest = max(width, height) * scale
    if longest > max_dim:
        scale *= max_dim / longest
    return min(1.0, scale)


def build_viewport_info(
    screenshot_id: str,
    viewport_width: float,
    viewport_height: float,
    *,
    device_pixel_ratio: float = 1.0,
    scroll_x: float = 0.0,
    scroll_y: float = 0.0,
    document_generation: int = 0,
    max_dim: int = DEFAULT_MAX_IMAGE_DIM,
    max_area: int = DEFAULT_MAX_IMAGE_AREA,
) -> ViewportInfo:
    vw, vh = int(round(viewport_width)), int(round(viewport_height))
    s = scale_for(vw, vh, max_dim, max_area)
    return ViewportInfo(
        screenshot_id=screenshot_id,
        viewport_width=vw,
        viewport_height=vh,
        screenshot_width=max(1, int(round(vw * s))),
        screenshot_height=max(1, int(round(vh * s))),
        device_pixel_ratio=float(device_pixel_ratio or 1.0),
        scroll_x=float(scroll_x),
        scroll_y=float(scroll_y),
        document_generation=int(document_generation),
    )


def screenshot_to_viewport(x: float, y: float, info: ViewportInfo) -> Tuple[float, float]:
    """Convert a point in screenshot pixels to CSS viewport pixels."""
    sx = info.viewport_width / info.screenshot_width
    sy = info.viewport_height / info.screenshot_height
    return x * sx, y * sy


def viewport_to_screenshot(x: float, y: float, info: ViewportInfo) -> Tuple[float, float]:
    """Inverse of screenshot_to_viewport (used for reporting back what was targeted)."""
    return x * info.screenshot_width / info.viewport_width, y * info.screenshot_height / info.viewport_height


def in_viewport(x: float, y: float, viewport_width: float, viewport_height: float) -> bool:
    return 0 <= x <= viewport_width and 0 <= y <= viewport_height


def drift_reason(old: Optional[ViewportInfo], current_width: float, current_height: float,
                 current_generation: int, current_scroll: Optional[Tuple[float, float]] = None) -> Optional[str]:
    """
    Why a coordinate taken from `old` can no longer be trusted, or None if it still can.

    A coordinate is stale if the viewport was resized, the document was replaced (navigation or reload),
    or the page scrolled. Scroll matters because a screenshot-space point is relative to what was visible
    at capture time.
    """
    if old is None:
        return "no screenshot has been taken for this tab, so there is nothing to take coordinates from"
    if int(round(current_width)) != old.viewport_width or int(round(current_height)) != old.viewport_height:
        return (f"the viewport changed from {old.viewport_width}x{old.viewport_height} "
                f"to {int(round(current_width))}x{int(round(current_height))}")
    if current_generation != old.document_generation:
        return "the page navigated or reloaded since the screenshot"
    if current_scroll is not None and (
        abs(current_scroll[0] - old.scroll_x) > 1.0 or abs(current_scroll[1] - old.scroll_y) > 1.0
    ):
        return "the page scrolled since the screenshot"
    return None
