"""
High-Performance Visual Media Diffing Engine
Supports:
- Swipe curtain / slider
- Onion-skin transparency overlay
- Tolerance-based pixel difference heatmap
- Flicker / blink comparison
- Image metadata inspection
"""

import os
from dataclasses import dataclass, field
from typing import Tuple, Dict, Any, Optional
from PIL import Image, ImageChops, ImageDraw, ExifTags


@dataclass
class ImageDiffResult:
    img1: Image.Image
    img2: Image.Image
    heatmap_img: Image.Image
    diff_percentage: float
    diff_pixel_count: int
    total_pixels: int
    dimensions_match: bool
    meta1: Dict[str, Any]
    meta2: Dict[str, Any]
    exif1: Dict[str, str] = field(default_factory=dict)
    exif2: Dict[str, str] = field(default_factory=dict)
    text1: str = ""
    text2: str = ""
    page_num: int = 0
    total_pages_1: int = 1
    total_pages_2: int = 1


class ImageDiffEngine:
    """Core image comparison, PDF rasterization, and metadata engine."""

    @staticmethod
    def get_page_count(path: str) -> int:
        if not path or not os.path.exists(path):
            return 0
        if path.lower().endswith(".pdf"):
            try:
                import fitz
                doc = fitz.open(path)
                count = doc.page_count
                doc.close()
                return count
            except Exception:
                return 1
        return 1

    @staticmethod
    def get_extracted_text(path: str, page_num: int = 0) -> str:
        if not path or not os.path.exists(path):
            return ""
        ext = os.path.splitext(path)[1].lower()
        if ext == ".pdf":
            try:
                import fitz
                doc = fitz.open(path)
                text = ""
                if 0 <= page_num < doc.page_count:
                    text = doc[page_num].get_text()
                doc.close()
                return text
            except Exception:
                return ""
        elif ext == ".svg":
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    return f.read()
            except Exception:
                return ""
        return ""

    @staticmethod
    def get_exif_metadata(path: str) -> Dict[str, str]:
        """Extracts photographic EXIF data or document metadata."""
        if not path or not os.path.exists(path):
            return {}
        ext = os.path.splitext(path)[1].lower()
        if ext == ".pdf":
            try:
                import fitz
                doc = fitz.open(path)
                meta = {}
                for k, v in doc.metadata.items():
                    if v:
                        meta[k.title()] = str(v)
                meta["Page Count"] = str(doc.page_count)
                doc.close()
                return meta
            except Exception:
                return {}
        try:
            with Image.open(path) as img:
                exif_data = img.getexif()
                if not exif_data:
                    return {}
                result = {}
                for tag_id, val in exif_data.items():
                    tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
                    if isinstance(val, bytes):
                        try:
                            val = val.decode("utf-8", errors="replace")
                        except Exception:
                            val = str(val)
                    result[str(tag_name)] = str(val)
                return result
        except Exception:
            return {}

    @staticmethod
    def get_image_metadata(path: str) -> Dict[str, Any]:
        if not os.path.exists(path):
            return {"exists": False, "size": 0, "dim": (0, 0), "mode": "N/A", "format": "N/A"}
        try:
            stat = os.stat(path)
            ext = os.path.splitext(path)[1].lower()
            if ext == ".pdf":
                try:
                    import fitz
                    doc = fitz.open(path)
                    p0 = doc[0]
                    dim = (int(p0.rect.width), int(p0.rect.height))
                    pages = doc.page_count
                    doc.close()
                    return {
                        "exists": True,
                        "size": stat.st_size,
                        "dim": dim,
                        "mode": f"PDF ({pages} pages)",
                        "format": "PDF Document",
                    }
                except Exception:
                    pass
            elif ext == ".svg":
                return {
                    "exists": True,
                    "size": stat.st_size,
                    "dim": (0, 0),
                    "mode": "Vector DOM",
                    "format": "SVG Graphic",
                }

            with Image.open(path) as img:
                return {
                    "exists": True,
                    "size": stat.st_size,
                    "dim": img.size,
                    "mode": img.mode,
                    "format": img.format or "Unknown",
                }
        except Exception as e:
            return {"exists": True, "size": 0, "dim": (0, 0), "mode": "Error", "format": str(e)}

    @classmethod
    def load_image(cls, path: str, page_num: int = 0, dpi: int = 150) -> Optional[Image.Image]:
        if not path or not os.path.exists(path):
            return None
        ext = os.path.splitext(path)[1].lower()
        if ext == ".pdf":
            try:
                import fitz
                doc = fitz.open(path)
                if doc.page_count == 0:
                    doc.close()
                    return None
                actual_page = min(max(0, page_num), doc.page_count - 1)
                pix = doc[actual_page].get_pixmap(dpi=dpi)
                mode = "RGBA" if pix.alpha else "RGB"
                img = Image.frombytes(mode, [pix.width, pix.height], pix.samples).convert("RGBA")
                doc.close()
                return img
            except Exception:
                return None
        elif ext == ".svg":
            try:
                import fitz
                with open(path, "rb") as f:
                    content = f.read()
                doc = fitz.open(stream=content, filetype="svg")
                pix = doc[0].get_pixmap(dpi=dpi)
                mode = "RGBA" if pix.alpha else "RGB"
                img = Image.frombytes(mode, [pix.width, pix.height], pix.samples).convert("RGBA")
                doc.close()
                return img
            except Exception:
                return None
        else:
            try:
                return Image.open(path).convert("RGBA")
            except Exception:
                return None

    @classmethod
    def compare_images(
        cls,
        path1: str,
        path2: str,
        tolerance: int = 8,
        highlight_color: Tuple[int, int, int, int] = (255, 0, 110, 255),
        page_num: int = 0
    ) -> Optional[ImageDiffResult]:
        """Compares two images or document pages and computes difference statistics and difference heatmap."""
        if not os.path.exists(path1) or not os.path.exists(path2):
            return None

        raw_img1 = cls.load_image(path1, page_num=page_num)
        raw_img2 = cls.load_image(path2, page_num=page_num)
        if raw_img1 is None or raw_img2 is None:
            return None

        meta1 = cls.get_image_metadata(path1)
        meta2 = cls.get_image_metadata(path2)
        exif1 = cls.get_exif_metadata(path1)
        exif2 = cls.get_exif_metadata(path2)
        text1 = cls.get_extracted_text(path1, page_num=page_num)
        text2 = cls.get_extracted_text(path2, page_num=page_num)
        pages1 = cls.get_page_count(path1)
        pages2 = cls.get_page_count(path2)

        dim_match = raw_img1.size == raw_img2.size
        # Canvas size: maximum bounding box
        max_w = max(raw_img1.width, raw_img2.width)
        max_h = max(raw_img1.height, raw_img2.height)

        # Pad to equal bounds on transparent background
        img1 = Image.new("RGBA", (max_w, max_h), (0, 0, 0, 0))
        img2 = Image.new("RGBA", (max_w, max_h), (0, 0, 0, 0))
        img1.paste(raw_img1, (0, 0))
        img2.paste(raw_img2, (0, 0))

        # Pixel delta calculation
        total_pixels = max_w * max_h

        # Fast pixel analysis
        pixels1 = img1.load()
        pixels2 = img2.load()
        heatmap = Image.new("RGBA", (max_w, max_h), (245, 245, 247, 255))
        h_pixels = heatmap.load()

        diff_count = 0

        for y in range(max_h):
            for x in range(max_w):
                p1 = pixels1[x, y]
                p2 = pixels2[x, y]
                dr = abs(p1[0] - p2[0])
                dg = abs(p1[1] - p2[1])
                db = abs(p1[2] - p2[2])
                da = abs(p1[3] - p2[3])

                delta = max(dr, dg, db, da)
                if delta > tolerance:
                    diff_count += 1
                    # Highlight diff in vivid magenta/neon
                    intensity = min(255, 120 + int(delta * 0.5))
                    h_pixels[x, y] = (highlight_color[0], highlight_color[1], highlight_color[2], intensity)
                else:
                    # Muted grayscale background
                    gray = int(0.299 * p1[0] + 0.587 * p1[1] + 0.114 * p1[2])
                    h_pixels[x, y] = (gray, gray, gray, 60)

        diff_pct = (diff_count / total_pixels) * 100.0 if total_pixels > 0 else 0.0

        return ImageDiffResult(
            img1=img1,
            img2=img2,
            heatmap_img=heatmap,
            diff_percentage=diff_pct,
            diff_pixel_count=diff_count,
            total_pixels=total_pixels,
            dimensions_match=dim_match,
            meta1=meta1,
            meta2=meta2,
            exif1=exif1,
            exif2=exif2,
            text1=text1,
            text2=text2,
            page_num=page_num,
            total_pages_1=pages1,
            total_pages_2=pages2,
        )

    @staticmethod
    def render_swipe_curtain(
        img1: Image.Image,
        img2: Image.Image,
        split_ratio: float = 0.5,
        divider_width: int = 2,
        divider_color: Tuple[int, int, int, int] = (9, 105, 218, 255)
    ) -> Image.Image:
        """
        Renders a swipe curtain view:
        Left portion up to split_ratio is img1, right portion is img2, with a divider bar.
        """
        w, h = img1.size
        split_x = int(w * split_ratio)
        split_x = max(0, min(w, split_x))

        composite = Image.new("RGBA", (w, h))
        # Left slice from img1
        if split_x > 0:
            box_l = (0, 0, split_x, h)
            composite.paste(img1.crop(box_l), (0, 0))
        # Right slice from img2
        if split_x < w:
            box_r = (split_x, 0, w, h)
            composite.paste(img2.crop(box_r), (split_x, 0))

        # Draw vertical separator line
        draw = ImageDraw.Draw(composite)
        draw.line([(split_x, 0), (split_x, h)], fill=divider_color, width=divider_width)

        return composite

    @staticmethod
    def render_onion_skin(img1: Image.Image, img2: Image.Image, alpha: float = 0.5) -> Image.Image:
        """Renders an alpha transparency blend of img1 and img2."""
        clamped_alpha = max(0.0, min(1.0, alpha))
        return Image.blend(img1, img2, clamped_alpha)
