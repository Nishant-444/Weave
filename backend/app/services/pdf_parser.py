import io
import logging
from typing import Dict, List, Any
import fitz  # PyMuPDF
import pytesseract
from PIL import Image

logger = logging.getLogger("uvicorn.error")


class ExtractedPage:
    def __init__(self, page_num: int, text: str):
        self.page_num = page_num  # 1-indexed
        self.text = text


class ExtractedChunk:
    def __init__(self, page_num: int, char_offset: int, content: str):
        self.page_num = page_num
        self.char_offset = char_offset
        self.content = content


def extract_pdf_text_by_pages(pdf_bytes: bytes) -> List[ExtractedPage]:
    """
    Extract clean text per page from a PDF file using PyMuPDF (fitz).
    If page text is sparse/empty (e.g. scanned image, diagram, cover or non-selectable text),
    runs Tesseract OCR on the rendered high-resolution image to extract text accurately.
    Page numbering is 1-indexed for deterministic citation references.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages: List[ExtractedPage] = []

    for page_idx in range(len(doc)):
        page = doc[page_idx]
        text = page.get_text("text") or ""
        cleaned_text = text.replace("\x00", "").strip()

        # Automatic OCR Fallback: If page has very sparse text (< 50 chars) or embedded images
        if len(cleaned_text) < 50:
            try:
                # Render high-resolution pixmap (150 DPI) for OCR
                pix = page.get_pixmap(dpi=150)
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                ocr_text = pytesseract.image_to_string(img)
                cleaned_ocr = ocr_text.replace("\x00", "").strip()
                if len(cleaned_ocr) > len(cleaned_text):
                    cleaned_text = cleaned_ocr
                    logger.info(f"OCR successfully extracted {len(cleaned_ocr)} chars from page {page_idx + 1}")
            except Exception as e:
                logger.warning(f"OCR fallback failed on page {page_idx + 1}: {e}")

        pages.append(ExtractedPage(page_num=page_idx + 1, text=cleaned_text))

    doc.close()
    return pages


def chunk_extracted_pages(
    pages: List[ExtractedPage],
    chunk_size: int = 1500,
    chunk_overlap: int = 200,
) -> List[ExtractedChunk]:
    """
    Create sliding-window chunks from per-page text, preserving strict page boundaries.
    Each chunk records its 1-indexed page_num and start char_offset on that page.
    """
    chunks: List[ExtractedChunk] = []

    for page in pages:
        text = page.text
        if not text:
            continue

        text_len = len(text)
        if text_len <= chunk_size:
            chunks.append(ExtractedChunk(page_num=page.page_num, char_offset=0, content=text))
            continue

        start = 0
        while start < text_len:
            end = min(start + chunk_size, text_len)

            # If not at the end of the text, try to split at a natural sentence or paragraph boundary
            if end < text_len:
                # Look for paragraph or sentence break in the last 20% of the chunk
                search_region = text[start + int(chunk_size * 0.8) : end]
                split_idx = -1
                for delimiter in ["\n\n", "\n", ". ", "; "]:
                    found = search_region.rfind(delimiter)
                    if found != -1:
                        split_idx = int(chunk_size * 0.8) + found + len(delimiter)
                        break
                if split_idx != -1:
                    end = start + split_idx

            chunk_content = text[start:end].strip()
            if chunk_content:
                chunks.append(
                    ExtractedChunk(
                        page_num=page.page_num,
                        char_offset=start,
                        content=chunk_content,
                    )
                )

            # Advance by step (chunk_size - overlap)
            step = max(end - start - chunk_overlap, chunk_size // 2)
            start += step

    return chunks
