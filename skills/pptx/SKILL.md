---
name: pptx
description: Use this skill whenever the user wants to create, edit, or read PowerPoint presentations (.pptx). Covers creating slides from scratch, adding text/images/charts/tables, modifying existing files, and exporting.
---

# PowerPoint (PPTX) Guide

## Limitation — What the agent CAN and CANNOT do

**CAN do (programmatic generation):**

- Create structured PPTX or PDF files with text, tables, charts, bullet points, and basic formatting
- Produce clean, well-organized documents from research or data
- Attach the file to the reply email automatically

**CANNOT do:**

- Generate pixel-perfect designer layouts with custom fonts, images, or brand assets
- Embed AI-generated images (no image generation tool available in this container)
- Match a specific visual template unless given an existing `.pptx` to modify

**Best practice:** When asked to create a presentation or report, always:

1. Create the PPTX/PDF programmatically with full content
2. Also write the same content as Markdown in the reply body — so the user gets the content even if they can't open the file
3. Mention in the reply that the file is attached

## Quick Start — Create a presentation

```python
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

prs = Presentation()
slide_layout = prs.slide_layouts[1]  # Title and Content
slide = prs.slides.add_slide(slide_layout)

slide.shapes.title.text = "My Title"
slide.placeholders[1].text = "Body content here"

prs.save("output.pptx")
```

## Slide Layouts (prs.slide_layouts[N])

| Index | Name                  |
| ----- | --------------------- |
| 0     | Title Slide           |
| 1     | Title and Content     |
| 2     | Title and Two Content |
| 5     | Title Only            |
| 6     | Blank                 |

## Text Formatting

```python
from pptx.util import Pt
from pptx.dml.color import RGBColor

tf = shape.text_frame
tf.word_wrap = True
p = tf.add_paragraph()
run = p.add_run()
run.text = "Bold red text"
run.font.bold = True
run.font.size = Pt(24)
run.font.color.rgb = RGBColor(0xFF, 0x00, 0x00)
p.alignment = PP_ALIGN.CENTER
```

## Add Image

```python
from pptx.util import Inches
slide.shapes.add_picture("image.png", Inches(1), Inches(1), Inches(4), Inches(3))
```

## Add Table

```python
from pptx.util import Inches
rows, cols = 3, 4
table = slide.shapes.add_table(rows, cols, Inches(1), Inches(2), Inches(8), Inches(3)).table
table.cell(0, 0).text = "Header"
table.columns[0].width = Inches(2)
```

## Add Chart

```python
from pptx.chart.data import ChartData
from pptx.enum.chart import XL_CHART_TYPE
from pptx.util import Inches

chart_data = ChartData()
chart_data.categories = ["Q1", "Q2", "Q3", "Q4"]
chart_data.add_series("Revenue", (100, 150, 120, 200))

chart = slide.shapes.add_chart(
    XL_CHART_TYPE.COLUMN_CLUSTERED,
    Inches(1), Inches(2), Inches(8), Inches(4),
    chart_data
).chart
chart.has_title = True
chart.chart_title.text_frame.text = "Quarterly Revenue"
```

## Slide Background Color

```python
from pptx.dml.color import RGBColor
from pptx.oxml.ns import qn
from lxml import etree

background = slide.background
fill = background.fill
fill.solid()
fill.fore_color.rgb = RGBColor(0x1E, 0x1E, 0x2E)  # dark bg
```

## Read Existing PPTX

```python
prs = Presentation("existing.pptx")
for slide in prs.slides:
    for shape in slide.shapes:
        if shape.has_text_frame:
            print(shape.text_frame.text)
```

## Email Attachment Convention

Save the file to the attachments directory so the gateway auto-attaches it:

```python
import os
task_id = os.environ.get("PICOCLAW_TASK_ID", "default")
attach_dir = os.path.expanduser(f"~/.picoclaw/workspace/attachments/{task_id}")
os.makedirs(attach_dir, exist_ok=True)
prs.save(os.path.join(attach_dir, "presentation.pptx"))
print(f"Saved presentation to attachments — will be emailed automatically.")
```

## Quick Reference

| Task         | Method                                           |
| ------------ | ------------------------------------------------ |
| Create blank | `Presentation()`                                 |
| Add slide    | `prs.slides.add_slide(layout)`                   |
| Add text box | `slide.shapes.add_textbox(l, t, w, h)`           |
| Add image    | `slide.shapes.add_picture(path, l, t, w, h)`     |
| Add table    | `slide.shapes.add_table(rows, cols, l, t, w, h)` |
| Add chart    | `slide.shapes.add_chart(type, l, t, w, h, data)` |
| Save         | `prs.save("file.pptx")`                          |
