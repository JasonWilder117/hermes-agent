import sys
import re
import argparse
from PIL import Image
import os

def render_ansi_to_image(ansi_path: str, output_path: str, target_res: str = None, style: str = 'smooth'):
    if not os.path.exists(ansi_path):
        print(f"[Error] File not found: {ansi_path}")
        sys.exit(1)
        
    try:
        with open(ansi_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        with open(ansi_path, 'r', encoding='utf-16') as f:
            content = f.read()
            
    # Normalize literal escape sequences that the LLM might have written as strings
    content = content.replace('\\033', '\x1B').replace('\\x1b', '\x1B').replace('\\e', '\x1B')
    # Also replace actual \033 in case they are there
    content = content.replace('\033', '\x1B')
        
    # Strip clear screen and cursor home and background colors if any
    content = content.replace("\033[2J", "").replace("\033[H", "").replace("\033[40m", "")
    content = content.replace("\033[?25l", "").replace("\033[?7l", "")
    
    # We parse True Color ANSI: \033[38;2;R;G;Bm
    # And Reset: \033[0m
    
    # Split content into lines
    lines = content.split('\n')
        
    # Find max width
    max_cols = 0
    clean_lines = []
    
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    
    for line in lines:
        clean_line = ansi_escape.sub('', line)
        if len(clean_line) > max_cols:
            max_cols = len(clean_line)
        clean_lines.append(clean_line)
        
    max_rows = len(lines)
    
    if max_cols == 0 or max_rows == 0:
        print("[Error] No text found to render.")
        sys.exit(1)
        
    img_width = max_cols
    img_height = max_rows
    
    # Create black canvas (1 pixel per character)
    img = Image.new('RGB', (img_width, img_height), color=(0, 0, 0))
    
    # Parse and draw
    # We use a regex to find all ANSI color codes and text segments
    # The pattern matches \033[...m or just text
    token_pattern = re.compile(r'(\x1B\[[0-9;]*m)|([^\x1B]+)')
    
    current_color = (255, 255, 255) # Default white
    
    y = 0
    for line in lines:
        x = 0
        for match in token_pattern.finditer(line):
            ansi_code = match.group(1)
            text_seg = match.group(2)
            
            if ansi_code:
                # Parse the color
                if ansi_code == '\x1B[0m':
                    current_color = (255, 255, 255)
                else:
                    color_match = re.match(r'\x1B\[38;2;(\d+);(\d+);(\d+)m', ansi_code)
                    if color_match:
                        r, g, b = map(int, color_match.groups())
                        current_color = (r, g, b)
            
            if text_seg:
                for char in text_seg:
                    if x < img_width and y < img_height:
                        img.putpixel((x, y), current_color)
                    x += 1
        y += 1
        
    # ── Check if --res switch was provided by the user/Hermes ─────────────
    # This catches the --res switch (e.g. "1028x720"). If provided, it forces 
    # the final rendered image to scale perfectly to these exact pixel dimensions.
    if target_res:
        try:
            w_str, h_str = target_res.lower().split('x')
            w, h = int(w_str), int(h_str)
            # Use requested resampling style
            resample_filter = Image.Resampling.LANCZOS if style == 'smooth' else Image.Resampling.NEAREST
            img = img.resize((w, h), resample_filter)
            print(f"[Info] Resized final image to {w}x{h} using {style} scaling")
        except Exception as e:
            print(f"[Warning] Could not parse or apply --res {target_res}: {e}")
            
    img.save(output_path)
    print(f"[Success] Rendered {max_cols}x{max_rows} ASCII grid to {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Render colored ANSI text back to a solid pixel PNG image")
    parser.add_argument("input", help="Path to input .ansi or .txt file")
    parser.add_argument("output", help="Path to output .png file")
    parser.add_argument("--res", type=str, default=None, help="Target output resolution (e.g. 1920x1080)")
    parser.add_argument("--style", type=str, choices=['smooth', 'pixel'], default='smooth', help="Upscaling style: smooth (Lanczos) or pixel (Nearest Neighbor)")
    args = parser.parse_args()
    
    render_ansi_to_image(args.input, args.output, target_res=args.res, style=args.style)
