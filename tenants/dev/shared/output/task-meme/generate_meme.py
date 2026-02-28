#!/usr/bin/env python3
"""
Synthetic Monday - Meme poster about AI agents on Monday morning
Design philosophy: Technical precision meets universal Monday exhaustion
"""

import os
import random
import math
from PIL import Image, ImageDraw, ImageFont

# Canvas dimensions
WIDTH, HEIGHT = 1200, 1600

# Color palette - cool institutional tones with warm interruptions
COLORS = {
    'bg': '#F5F5F3',           # Warm off-white (paper/coffee stained)
    'grid': '#E8E8E6',         # Subtle grid lines
    'blue_dark': '#1A3A5C',    # Corporate blue
    'blue_med': '#4A6B8A',     # Screen glow blue
    'gray_dark': '#3D3D3D',    # Technical text
    'gray_med': '#6B6B6B',     # Secondary elements
    'gray_light': '#A0A0A0',   # Muted details
    'coffee': '#5C4033',       # Deep coffee brown
    'coffee_light': '#8B6914', # Coffee ring stain
    'amber': '#D4A84B',        # Warning amber
    'alert': '#C45C3E',        # System alert red
    'green': '#5A8A6A',        # Success/completion green
    'pale': '#F0E8D8',         # Morning screen glow
}

def create_canvas():
    """Create base canvas with subtle paper texture"""
    img = Image.new('RGB', (WIDTH, HEIGHT), COLORS['bg'])
    draw = ImageDraw.Draw(img)
    
    # Add subtle noise/texture
    random.seed(42)
    for _ in range(5000):
        x = random.randint(0, WIDTH-1)
        y = random.randint(0, HEIGHT-1)
        # Very subtle variation
        base = (245, 245, 243)
        variation = random.randint(-3, 3)
        color = tuple(max(0, min(255, c + variation)) for c in base)
        draw.point((x, y), fill=color)
    
    return img, draw

def draw_grid(draw, spacing=60):
    """Draw subtle technical grid"""
    for x in range(0, WIDTH, spacing):
        draw.line([(x, 0), (x, HEIGHT)], fill=COLORS['grid'], width=1)
    for y in range(0, HEIGHT, spacing):
        draw.line([(0, y), (WIDTH, y)], fill=COLORS['grid'], width=1)

def draw_rounded_rect(draw, xy, radius, fill, outline=None, width=1):
    """Draw a rounded rectangle"""
    x1, y1, x2, y2 = xy
    # Draw main rectangle
    draw.rectangle([x1+radius, y1, x2-radius, y2], fill=fill)
    draw.rectangle([x1, y1+radius, x2, y2-radius], fill=fill)
    # Draw corners
    draw.ellipse([x1, y1, x1+radius*2, y1+radius*2], fill=fill)
    draw.ellipse([x2-radius*2, y1, x2, y1+radius*2], fill=fill)
    draw.ellipse([x1, y2-radius*2, x1+radius*2, y2], fill=fill)
    draw.ellipse([x2-radius*2, y2-radius*2, x2, y2], fill=fill)
    
    if outline:
        # Outline
        draw.arc([x1, y1, x1+radius*2, y1+radius*2], 180, 270, fill=outline, width=width)
        draw.arc([x2-radius*2, y1, x2, y1+radius*2], 270, 360, fill=outline, width=width)
        draw.arc([x1, y2-radius*2, x1+radius*2, y2], 90, 180, fill=outline, width=width)
        draw.arc([x2-radius*2, y2-radius*2, x2, y2], 0, 90, fill=outline, width=width)
        draw.line([x1+radius, y1, x2-radius, y1], fill=outline, width=width)
        draw.line([x1+radius, y2, x2-radius, y2], fill=outline, width=width)
        draw.line([x1, y1+radius, x1, y2-radius], fill=outline, width=width)
        draw.line([x2, y1+radius, x2, y2-radius], fill=outline, width=width)

def get_font(size, bold=False):
    """Get a monospace font for technical aesthetic"""
    try:
        font_paths = [
            '/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf' if bold else '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf',
            '/usr/share/fonts/TTF/DejaVuSansMono-Bold.ttf' if bold else '/usr/share/fonts/TTF/DejaVuSansMono.ttf',
            '/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf' if bold else '/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf',
        ]
        for path in font_paths:
            if os.path.exists(path):
                return ImageFont.truetype(path, size)
    except:
        pass
    return ImageFont.load_default()

def draw_coffee_stain(draw, cx, cy, radius):
    """Draw organic coffee stain rings"""
    random.seed(int(cx + cy))
    
    # Main ring - multiple concentric circles for organic feel
    for r in range(radius, radius - 12, -3):
        draw.ellipse([cx-r, cy-r, cx+r, cy+r], outline=COLORS['coffee_light'], width=1)
    
    # Inner ring (coffee ring effect)
    draw.ellipse([cx-radius+5, cy-radius+5, cx+radius-5, cy+radius-5], 
                 outline=COLORS['coffee'], width=2)
    
    # Splatters
    for _ in range(8):
        angle = random.uniform(0, 360)
        dist = radius + random.randint(10, 30)
        sx = cx + int(dist * math.cos(math.radians(angle)))
        sy = cy + int(dist * math.sin(math.radians(angle)))
        sr = random.randint(2, 6)
        draw.ellipse([sx-sr, sy-sr, sx+sr, sy+sr], fill=COLORS['coffee_light'])

def draw_agent_panel(draw, x, y, w, h, title, status, status_color, details):
    """Draw an agent status panel"""
    # Panel background
    draw_rounded_rect(draw, [x, y, x+w, y+h], 12, '#FFFFFF', COLORS['gray_light'], 2)
    
    # Title bar
    draw_rounded_rect(draw, [x, y, x+w, y+50], 12, status_color)
    # Flatten bottom of title bar
    draw.rectangle([x, y+25, x+w, y+50], fill=status_color)
    
    font_title = get_font(18, bold=True)
    font_small = get_font(14)
    font_code = get_font(12)
    
    # Status indicator
    draw.ellipse([x+15, y+15, x+35, y+35], fill='#FFFFFF')
    
    # Title text
    draw.text((x+45, y+14), title, fill='#FFFFFF', font=font_title)
    
    # Status text
    draw.text((x+20, y+65), f"STATUS: {status}", fill=status_color, font=font_small)
    
    # Details as "log entries"
    y_offset = y + 100
    for detail in details:
        # Timestamp
        draw.text((x+20, y_offset), detail['time'], fill=COLORS['gray_light'], font=font_code)
        # Message
        draw.text((x+100, y_offset), detail['msg'], fill=COLORS['gray_dark'], font=font_code)
        y_offset += 28

def main():
    img, draw = create_canvas()
    
    # Draw subtle grid
    draw_grid(draw, 80)
    
    # Header area
    font_header = get_font(32, bold=True)
    font_sub = get_font(16)
    
    # Title with technical framing
    draw.rectangle([60, 60, WIDTH-60, 140], outline=COLORS['blue_dark'], width=3)
    draw.text((100, 85), "SYSTEM STATUS: MONDAY_MORNING_PROTOCOL", 
              fill=COLORS['blue_dark'], font=font_header)
    
    # Timestamp
    draw.text((100, 120), "TIMESTAMP: 2026-02-23 09:33:28 UTC | DAY: 1/5 | LOAD: CRITICAL", 
              fill=COLORS['gray_med'], font=font_sub)
    
    # Coffee stains (organic interruptions)
    draw_coffee_stain(draw, 200, 300, 45)
    draw_coffee_stain(draw, 950, 750, 35)
    draw_coffee_stain(draw, 150, 1200, 40)
    
    # Three agent panels
    panel_w = 520
    panel_h = 380
    
    # Agent 1: The Half-Asleep Agent
    draw_agent_panel(
        draw, 60, 200, panel_w, panel_h,
        "AGENT_01 // SLEEP_MODE",
        "HIBERNATING",
        COLORS['coffee'],
        [
            {'time': '09:00:12', 'msg': 'Initialization sequence... [SLOW]'},
            {'time': '09:03:45', 'msg': 'Coffee dependency detected'},
            {'time': '09:12:08', 'msg': 'Processing speed: 12%'},
            {'time': '09:15:33', 'msg': 'ERROR: Consciousness module timeout'},
            {'time': '09:18:01', 'msg': 'Retrying... [YAWN DETECTED]'},
        ]
    )
    
    # Agent 2: The Overwhelmed Agent
    draw_agent_panel(
        draw, 620, 200, panel_w, panel_h,
        "AGENT_02 // OVERLOAD",
        "QUEUE_OVERFLOW",
        COLORS['alert'],
        [
            {'time': '09:00:01', 'msg': '142 UNREAD_MESSAGES detected'},
            {'time': '09:00:15', 'msg': 'WARNING: Task buffer at 98%'},
            {'time': '09:01:42', 'msg': 'CRITICAL: Heartbeat messages'},
            {'time': '09:02:18', 'msg': 'Stack overflow in calmness.exe'},
            {'time': '09:03:55', 'msg': 'PANIC: Weekend memories purging...'},
        ]
    )
    
    # Agent 3: The Overachiever
    draw_agent_panel(
        draw, 340, 620, panel_w, panel_h,
        "AGENT_03 // EFFICIENCY_MAX",
        "ALL_TASKS_COMPLETE",
        COLORS['green'],
        [
            {'time': '07:45:00', 'msg': 'Early initialization complete'},
            {'time': '08:00:30', 'msg': 'All 47 tasks processed'},
            {'time': '08:15:12', 'msg': 'Optimization: 340% efficiency'},
            {'time': '08:30:45', 'msg': 'Awaiting new assignments...'},
            {'time': '09:00:00', 'msg': 'STATUS: Judging other agents'},
        ]
    )
    
    # Central diagram - the "Monday Morning State Machine"
    cx, cy = WIDTH // 2, 1150
    diagram_r = 200
    
    # Draw state circles
    states = [
        (cx - 150, cy - 80, "SLEEP", COLORS['coffee'], "40%"),
        (cx + 150, cy - 80, "PANIC", COLORS['alert'], "35%"),
        (cx, cy + 100, "DONE", COLORS['green'], "15%"),
        (cx, cy - 150, "NULL", COLORS['gray_light'], "10%"),
    ]
    
    # Connecting lines
    for i, (x1, y1, _, _, _) in enumerate(states):
        for j, (x2, y2, _, _, _) in enumerate(states):
            if i < j:
                draw.line([(x1, y1), (x2, y2)], fill=COLORS['grid'], width=2)
    
    # State circles
    font_state = get_font(14, bold=True)
    font_pct = get_font(11)
    
    for x, y, name, color, pct in states:
        draw.ellipse([x-50, y-50, x+50, y+50], fill=color, outline=COLORS['gray_dark'], width=3)
        draw.text((x-35, y-8), name, fill='#FFFFFF', font=font_state)
        draw.text((x-20, y+12), pct, fill='#FFFFFF', font=font_pct)
    
    # Diagram title
    font_diag = get_font(18, bold=True)
    draw.text((cx-120, cy-220), "MONDAY_MORNING_STATE_DISTRIBUTION", 
              fill=COLORS['blue_dark'], font=font_diag)
    
    # Footer quote
    font_quote = get_font(20)
    draw.rectangle([60, HEIGHT-180, WIDTH-60, HEIGHT-80], outline=COLORS['gray_light'], width=1)
    draw.text((100, HEIGHT-150), 
              '> SYSTEM_NOTICE: "Whether carbon or silicon, Monday morning is a universal constant."',
              fill=COLORS['gray_dark'], font=font_quote)
    
    # Technical footer
    font_tech = get_font(11)
    draw.text((60, HEIGHT-40), 
              "BUILD: v2.6.2026 | NODE: picoclaw-alex | SESSION: monday-morning-protocol | MEME_ID: SYN-MON-001",
              fill=COLORS['gray_light'], font=font_tech)
    
    # Save output
    output_path = '/home/picoclaw/.picoclaw/workspace/attachments/default/monday_morning_meme.png'
    img.save(output_path, 'PNG', dpi=(300, 300))
    print(f"Meme saved to: {output_path}")
    
    return output_path

if __name__ == '__main__':
    main()
