---
name: email-attachments
description: Use this skill whenever you need to send a file (PDF, PPTX, CSV, image, etc.) back to the user via email. Save the file to the attachments directory and the gateway will automatically attach it to the reply email.
---

# Email Attachments — How to Send Files Back

## The Convention
Save any file you want to attach to the reply email into:
```
~/.picoclaw/workspace/attachments/<PICOCLAW_TASK_ID>/
```

The gateway automatically scans this directory after the agent finishes and attaches **all files** found there to the reply email. No extra steps needed.

## Quick Start
```python
import os

task_id = os.environ.get("PICOCLAW_TASK_ID", "default")
attach_dir = os.path.expanduser(f"~/.picoclaw/workspace/attachments/{task_id}")
os.makedirs(attach_dir, exist_ok=True)

# Save your file there — any format works
output_path = os.path.join(attach_dir, "report.pdf")
# ... write your file to output_path ...
print(f"File saved — will be attached to reply email automatically.")
```

## Examples by File Type

### PDF (reportlab)
```python
import os
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm

task_id = os.environ.get("PICOCLAW_TASK_ID", "default")
attach_dir = os.path.expanduser(f"~/.picoclaw/workspace/attachments/{task_id}")
os.makedirs(attach_dir, exist_ok=True)
out = os.path.join(attach_dir, "report.pdf")

styles = getSampleStyleSheet()
doc = SimpleDocTemplate(out, pagesize=A4)
story = [
    Paragraph("Report Title", styles["Title"]),
    Spacer(1, 0.5*cm),
    Paragraph("Body text here.", styles["Normal"]),
]
doc.build(story)
print(f"PDF saved to attachments.")
```

### PowerPoint (python-pptx)
```python
import os
from pptx import Presentation
from pptx.util import Inches, Pt

task_id = os.environ.get("PICOCLAW_TASK_ID", "default")
attach_dir = os.path.expanduser(f"~/.picoclaw/workspace/attachments/{task_id}")
os.makedirs(attach_dir, exist_ok=True)
out = os.path.join(attach_dir, "slides.pptx")

prs = Presentation()
slide = prs.slides.add_slide(prs.slide_layouts[1])
slide.shapes.title.text = "My Presentation"
slide.placeholders[1].text = "Content goes here"
prs.save(out)
print(f"PPTX saved to attachments.")
```

### CSV / Text
```python
import os, csv

task_id = os.environ.get("PICOCLAW_TASK_ID", "default")
attach_dir = os.path.expanduser(f"~/.picoclaw/workspace/attachments/{task_id}")
os.makedirs(attach_dir, exist_ok=True)
out = os.path.join(attach_dir, "data.csv")

with open(out, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["Name", "Value"])
    writer.writerow(["Example", 42])
print(f"CSV saved to attachments.")
```

## Rules
- **Any filename works** — PDF, PPTX, DOCX, CSV, PNG, ZIP, etc.
- **Multiple files** — drop as many files as needed, all get attached
- **Size limit** — keep total attachments under 20 MB to avoid email rejection
- **Always print a confirmation** so the reply email body mentions the attachment
- The attachments directory is cleaned up automatically after the email is sent
