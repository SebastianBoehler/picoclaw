---
name: pdf
description: Use this skill whenever the user wants to do anything with PDF files — reading, extracting text/tables, merging, splitting, rotating, watermarking, creating, encrypting, or OCR on scanned PDFs.
---

# PDF Processing Guide

## Quick Start
```python
from pypdf import PdfReader, PdfWriter

reader = PdfReader("document.pdf")
print(f"Pages: {len(reader.pages)}")
text = "".join(page.extract_text() for page in reader.pages)
```

## Python Libraries

### pypdf — Basic Operations
```python
# Merge
writer = PdfWriter()
for f in ["doc1.pdf", "doc2.pdf"]:
    for page in PdfReader(f).pages:
        writer.add_page(page)
with open("merged.pdf", "wb") as out: writer.write(out)

# Split
for i, page in enumerate(PdfReader("input.pdf").pages):
    w = PdfWriter(); w.add_page(page)
    with open(f"page_{i+1}.pdf", "wb") as out: w.write(out)

# Rotate
page = PdfReader("input.pdf").pages[0]
page.rotate(90)

# Password protect
writer.encrypt("userpass", "ownerpass")

# Watermark
watermark = PdfReader("watermark.pdf").pages[0]
for page in PdfReader("doc.pdf").pages:
    page.merge_page(watermark)
    writer.add_page(page)
```

### pdfplumber — Text and Table Extraction
```python
import pdfplumber, pandas as pd

with pdfplumber.open("document.pdf") as pdf:
    # Text
    for page in pdf.pages:
        print(page.extract_text())

    # Tables → DataFrame
    all_tables = []
    for page in pdf.pages:
        for table in page.extract_tables():
            if table:
                all_tables.append(pd.DataFrame(table[1:], columns=table[0]))
    pd.concat(all_tables).to_excel("tables.xlsx", index=False)
```

### reportlab — Create PDFs
```python
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet

doc = SimpleDocTemplate("report.pdf", pagesize=letter)
styles = getSampleStyleSheet()
doc.build([Paragraph("Hello World!", styles['Title'])])
```

**IMPORTANT:** Never use Unicode subscript/superscript chars (₀₁₂, ⁰¹²) — use XML tags instead:
```python
Paragraph("H<sub>2</sub>O and x<super>2</super>", styles['Normal'])
```

### OCR — Scanned PDFs
```python
import pytesseract
from pdf2image import convert_from_path

images = convert_from_path('scanned.pdf')
text = "\n\n".join(pytesseract.image_to_string(img) for img in images)
```

## Command-Line Tools
```bash
# pdftotext
pdftotext -layout input.pdf output.txt
pdftotext -f 1 -l 5 input.pdf output.txt  # pages 1-5

# qpdf
qpdf --empty --pages file1.pdf file2.pdf -- merged.pdf
qpdf input.pdf --pages . 1-5 -- pages1-5.pdf
qpdf --password=mypass --decrypt encrypted.pdf decrypted.pdf

# Extract images
pdfimages -j input.pdf output_prefix
```

## Quick Reference
| Task | Best Tool |
|------|-----------|
| Merge/Split/Rotate | pypdf |
| Extract text | pdfplumber |
| Extract tables | pdfplumber → pandas |
| Create PDFs | reportlab |
| CLI merge | qpdf |
| OCR scanned | pytesseract + pdf2image |
| Extract images | pdfimages (poppler) |
