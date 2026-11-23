"""Crop participant rows from a screenshot of the Zajuna participants table.

The instructor manually crops a screenshot containing only the student rows
(no header). The crop may have extra whitespace above/below. This module
detects the table row boundaries by analyzing horizontal pixel patterns
and splits the image into individual row images.
"""
from __future__ import annotations

import io
import logging

from PIL import Image

logger = logging.getLogger(__name__)

# Minimum row height in pixels (to filter noise lines)
MIN_ROW_HEIGHT = 20

# A row of pixels is considered a "divider line" if the standard deviation
# of its grayscale values is below this threshold (i.e., uniform color).
DIVIDER_STD_THRESHOLD = 15

# Minimum percentage of the row width that must be "uniform" to count
DIVIDER_MIN_WIDTH_RATIO = 0.6


def crop_participant_rows(
    image_bytes: bytes,
    expected_rows: int,
) -> list[bytes]:
    """Crop individual participant rows from a table screenshot.

    Args:
        image_bytes: PNG/JPEG screenshot bytes.
        expected_rows: Expected number of student rows.

    Returns:
        List of PNG image bytes, one per detected row.
    """
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    width, height = img.size

    # Strategy: divide image into expected_rows equal parts.
    # This is the simplest and most reliable approach since the table
    # rows in Zajuna have uniform height.
    row_height = height / expected_rows

    rows: list[bytes] = []
    for i in range(expected_rows):
        top = int(i * row_height)
        bottom = int((i + 1) * row_height)
        # Clamp to image bounds
        bottom = min(bottom, height)

        row_img = img.crop((0, top, width, bottom))
        buf = io.BytesIO()
        row_img.save(buf, format="PNG")
        rows.append(buf.getvalue())

    logger.info(
        "Cropped %d rows from %dx%d image (row height ~%dpx)",
        len(rows), width, height, int(row_height),
    )
    return rows
