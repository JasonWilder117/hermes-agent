import sys
import shutil
import numpy as np
import cv2
import os
import argparse

# Enable ANSI color codes on PowerShell/CMD (Windows):
os.system("")

# ─────────────────────────────────────────────
#  AsciiMapper (from ascii_video_player2.py)
# ─────────────────────────────────────────────
class AsciiMapper:
    DEFAULT_PALETTE = list(
        " `.-':_,^=;><+!rc*/z?sLTv)J7(|Fi{C}fI31tlu[neoZ5Yxjya]2ESwqkP6h9d4VpOGbUAKXHm8RD#$Bg0MNWQ%&@"
    )
    _RESET = "\033[0m"

    def __init__(self, palette: list[str] | None = None, quantize_bits: int = 0) -> None:
        p = palette or self.DEFAULT_PALETTE
        self._n   = len(p)
        self._lut = np.array(p, dtype='U1')
        self._qb  = quantize_bits

    def convert(self, gray: np.ndarray, bgr: np.ndarray) -> str:
        H, W = gray.shape

        # Step 1: Pixel intensity -> character index
        indices = np.floor_divide(gray, max(1, 256 // self._n))
        np.clip(indices, 0, self._n - 1, out=indices)
        char_matrix = self._lut[indices]

        # Step 2: Color quantization
        rgb = bgr[:, :, ::-1] # BGR -> RGB view
        if self._qb > 0:
            qb = self._qb
            rgb = (rgb >> qb) << qb

        # Step 3: RLE and colored string construction
        lines = []
        prev_r = prev_g = prev_b = -1

        for row_idx in range(H):
            row_chars  = char_matrix[row_idx]
            row_colors = rgb[row_idx]
            buf = []

            for col_idx in range(W):
                r, g, b = int(row_colors[col_idx, 0]), \
                          int(row_colors[col_idx, 1]), \
                          int(row_colors[col_idx, 2])

                if r != prev_r or g != prev_g or b != prev_b:
                    buf.append(f"\033[38;2;{r};{g};{b}m")
                    prev_r, prev_g, prev_b = r, g, b

                buf.append(row_chars[col_idx])

            lines.append("".join(buf))

        return self._RESET + "\n".join(lines) + self._RESET

# ─────────────────────────────────────────────
#  Image Processing & Rendering
# ─────────────────────────────────────────────
def render_image(image_path: str, cols: int = 0, quantize_bits: int = 0, target_res: str = None):
    # Read the image
    bgr_frame = cv2.imread(image_path)
    if bgr_frame is None:
        print(f"[Error] Could not read image at {image_path}")
        sys.exit(1)
        
    img_h, img_w = bgr_frame.shape[:2]
    
    # ── Check if --res switch was provided by the user/Hermes ─────────────
    # If a specific resolution like "1028x720" is requested, we bypass the
    # aspect ratio auto-fitting and calculate the exact character grid needed.
    if target_res:
        try:
            w_str, h_str = target_res.lower().split('x')
            target_w, target_h = int(w_str), int(h_str)
            # Default PIL monospace font (size 12) is roughly 6x12 pixels.
            # We divide the target pixel resolution by the font dimensions to get rows/cols.
            final_cols = max(1, target_w // 6)
            final_rows = max(1, target_h // 12)
        except Exception as e:
            print(f"[Warning] Could not parse --res {target_res}: {e}")
            sys.exit(1)
    else:
        # ── Terminal dimensions ────────────────────────────────────────────
        term    = shutil.get_terminal_size(fallback=(220, 50))
        t_cols  = term.columns
        t_lines = term.lines - 2

        # Aspect ratio correction for terminals (characters are taller than wide)
        CHAR_RATIO = 0.45 
        aspect = img_h / img_w

        if cols > 0:
            # User specified fixed width
            final_cols = cols
            final_rows = max(1, int(final_cols * aspect * CHAR_RATIO))
        else:
            # Auto-fit to terminal
            safe_cols = min(t_cols, 160)
            if img_h > img_w: # Portrait
                final_rows = t_lines
                final_cols = max(1, int(final_rows / (aspect * CHAR_RATIO)))
                if final_cols > safe_cols:
                    final_cols = safe_cols
                    final_rows = max(1, int(final_cols * aspect * CHAR_RATIO))
            else: # Landscape
                final_cols = safe_cols
                final_rows = max(1, int(final_cols * aspect * CHAR_RATIO))
                if final_rows > t_lines:
                    final_rows = t_lines
                    final_cols = max(1, int(final_rows / (aspect * CHAR_RATIO)))

    # Resize image
    small_bgr = cv2.resize(bgr_frame, (final_cols, final_rows), interpolation=cv2.INTER_LINEAR)
    small_gray = cv2.cvtColor(small_bgr, cv2.COLOR_BGR2GRAY)

    # Convert to ASCII
    mapper = AsciiMapper(quantize_bits=quantize_bits)
    ascii_art = mapper.convert(small_gray, small_bgr)

    # Print with black background
    sys.stdout.write("\033[40m")
    print(ascii_art)
    sys.stdout.write("\033[0m")
    sys.stdout.flush()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Full Color ANSI ASCII Image Viewer")
    parser.add_argument("image", help="Path to image file")
    parser.add_argument("-c", "--cols", type=int, default=0, help="Fixed width in columns. Use 300+ for '1080p' high-res effect. (default: 0 = auto-fit to terminal)")
    parser.add_argument("--res", type=str, default=None, help="Target output resolution (e.g. 1024x720) to auto-calculate required rows/cols")
    args = parser.parse_args()

    render_image(args.image, cols=args.cols, target_res=args.res)
