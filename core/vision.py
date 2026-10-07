# ============================================================
# DULB ENGINEERING QA POC - VISION & DRAWING REGION COMPARISON
# ============================================================

import cv2
import numpy as np
import fitz
from core.utils import json_safe, normalize_text


def normalize_rect(rect, page_rect):
    """Normalizes coordinate rectangle relative to page dimensions (0.0 to 1.0)."""
    pw = max(float(page_rect.width), 1.0)
    ph = max(float(page_rect.height), 1.0)
    return {
        "x0": rect.x0 / pw,
        "y0": rect.y0 / ph,
        "x1": rect.x1 / pw,
        "y1": rect.y1 / ph,
    }


def denormalize_rect(normalized, page_rect):
    """Converts normalized relative rectangle back to absolute page coordinates."""
    return fitz.Rect(
        normalized["x0"] * page_rect.width,
        normalized["y0"] * page_rect.height,
        normalized["x1"] * page_rect.width,
        normalized["y1"] * page_rect.height,
    )


def expand_rect(bbox, page_rect, factor=2.5, min_padding=100):
    """
    Expands a bounding box around a consultant comment to capture surrounding context.
    Clamps the result within the page bounds. Ensures non-empty rectangle.
    """
    if not bbox or len(bbox) != 4:
        return page_rect

    rect = fitz.Rect(*bbox)
    rect.normalize()

    # Guarantee minimum dimensions even if comment bbox was a point or line
    width = max(rect.width, 20.0)
    height = max(rect.height, 20.0)

    pad_x = max(width * factor, min_padding)
    pad_y = max(height * factor, min_padding)

    expanded = fitz.Rect(
        rect.x0 - pad_x,
        rect.y0 - pad_y,
        rect.x1 + pad_x,
        rect.y1 + pad_y,
    )
    result = expanded & page_rect
    if result.is_empty or result.width <= 1.0 or result.height <= 1.0:
        return page_rect
    return result


def text_from_region(page, rect):
    """Extracts text contained within or intersecting a specified rectangular region."""
    if rect is None or rect.is_empty:
        return ""
    words = page.get_text("words", sort=True)
    found = []
    for word in words:
        if len(word) < 5:
            continue
        word_rect = fitz.Rect(word[:4])
        if rect.intersects(word_rect):
            found.append(word[4])
    return normalize_text(" ".join(found))


def vectors_in_region(page, rect):
    """Counts vector CAD drawing elements that intersect a specified region."""
    if rect is None or rect.is_empty:
        return 0
    count = 0
    try:
        drawings = page.get_drawings()
    except Exception:
        drawings = []
    for drawing in drawings:
        drawing_rect = drawing.get("rect")
        if not drawing_rect:
            continue
        if rect.intersects(drawing_rect):
            count += 1
    return count


def render_region(page, rect, zoom=2.5):
    """
    Renders a high-resolution RGB image of a clipped region on a PDF page.
    Returns None if the region is invalid or has zero size.
    """
    try:
        if rect is None or rect.is_empty or rect.width <= 1.0 or rect.height <= 1.0:
            return None
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=rect, alpha=False)
        if pix.width <= 0 or pix.height <= 0 or not pix.samples:
            return None
        data = np.frombuffer(pix.samples, dtype=np.uint8)
        if data.size == 0:
            return None
        data = data.reshape(pix.height, pix.width, pix.n)
        if pix.n == 4:
            data = cv2.cvtColor(data, cv2.COLOR_RGBA2RGB)
        elif pix.n == 1:
            data = cv2.cvtColor(data, cv2.COLOR_GRAY2RGB)
        return data
    except Exception:
        return None


def visual_similarity(image1, image2):
    """Calculates absolute grayscale pixel similarity ratio (0.0 to 1.0) between two images."""
    try:
        if image1 is None or image2 is None:
            return None
        if not isinstance(image1, np.ndarray) or not isinstance(image2, np.ndarray):
            return None
        if image1.size == 0 or image2.size == 0 or image1.ndim < 2 or image2.ndim < 2:
            return None

        gray1 = cv2.cvtColor(image1, cv2.COLOR_RGB2GRAY)
        gray2 = cv2.cvtColor(image2, cv2.COLOR_RGB2GRAY)
        width = min(gray1.shape[1], gray2.shape[1], 1200)
        height = min(gray1.shape[0], gray2.shape[0], 1200)
        if width < 10 or height < 10:
            return None
        gray1 = cv2.resize(gray1, (width, height))
        gray2 = cv2.resize(gray2, (width, height))
        difference = cv2.absdiff(gray1, gray2)
        mean_difference = np.mean(difference)
        similarity = 1 - mean_difference / 255
        similarity = max(0, min(1, similarity))
        return float(similarity)
    except Exception:
        return None


def create_difference_image(old_image, new_image):
    """Highlights visual differences by outlining contour deltas on the new revision image."""
    try:
        if old_image is None or new_image is None:
            return None
        if not isinstance(old_image, np.ndarray) or not isinstance(new_image, np.ndarray):
            return None
        if old_image.size == 0 or new_image.size == 0:
            return None

        height = min(old_image.shape[0], new_image.shape[0])
        width = min(old_image.shape[1], new_image.shape[1])
        if height < 10 or width < 10:
            return None

        old_resized = cv2.resize(old_image, (width, height))
        new_resized = cv2.resize(new_image, (width, height))
        difference = cv2.absdiff(old_resized, new_resized)
        gray = cv2.cvtColor(difference, cv2.COLOR_RGB2GRAY)
        _, threshold = cv2.threshold(gray, 30, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(threshold, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        output = new_resized.copy()
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            if w * h < 100:
                continue
            cv2.rectangle(output, (x, y), (x + w, y + h), (255, 0, 0), 2)
        return output
    except Exception:
        return None


def compare_comment_region(old_pdf, new_pdf, comment):
    """
    Extracts, renders, and compares the physical drawing region affected by a consultant comment
    between the old revision and the new revision.
    """
    if not comment.get("bbox"):
        return {"error": "Comment does not have a usable bounding box."}

    old_doc = fitz.open(old_pdf)
    new_doc = fitz.open(new_pdf)
    page_index = comment["page"] - 1

    if page_index >= len(old_doc) or page_index >= len(new_doc):
        old_doc.close()
        new_doc.close()
        return {"error": "Matching page is unavailable."}

    old_page = old_doc[page_index]
    new_page = new_doc[page_index]

    old_region = expand_rect(comment["bbox"], old_page.rect)
    normalized_region = normalize_rect(old_region, old_page.rect)
    new_region = denormalize_rect(normalized_region, new_page.rect)

    old_text = text_from_region(old_page, old_region)
    new_text = text_from_region(new_page, new_region)

    old_vectors = vectors_in_region(old_page, old_region)
    new_vectors = vectors_in_region(new_page, new_region)

    old_image = render_region(old_page, old_region)
    new_image = render_region(new_page, new_region)

    similarity = None
    difference_image = None
    if old_image is not None and new_image is not None:
        similarity = visual_similarity(old_image, new_image)
        difference_image = create_difference_image(old_image, new_image)

    old_doc.close()
    new_doc.close()

    return {
        "old_text": old_text,
        "new_text": new_text,
        "old_vectors": old_vectors,
        "new_vectors": new_vectors,
        "visual_similarity": similarity,
        "old_image": old_image,
        "new_image": new_image,
        "difference_image": difference_image,
        "old_bbox": json_safe(old_region),
        "new_bbox": json_safe(new_region),
    }
