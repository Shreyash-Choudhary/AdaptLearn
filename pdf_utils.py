"""
pdf_utils.py - PDF Text Extraction Module
Uses pdfplumber to extract all text from a PDF file.
"""

import pdfplumber


def extract_text_from_pdf(filepath: str) -> str:
    """
    Extract and return all text from a PDF file.

    Parameters
    ----------
    filepath : str
        Absolute or relative path to the PDF file.

    Returns
    -------
    str
        Concatenated text from every page of the PDF.
    """
    all_text = []

    with pdfplumber.open(filepath) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            page_text = page.extract_text()

            if page_text:                         # some pages may be images / blank
                all_text.append(page_text)
                print(f"  [pdf_utils] Page {page_number}: extracted {len(page_text)} characters")
            else:
                print(f"  [pdf_utils] Page {page_number}: no text found (possibly an image page)")

    combined_text = "\n\n".join(all_text)
    print(f"[pdf_utils] Total extracted text length: {len(combined_text)} characters")
    return combined_text
