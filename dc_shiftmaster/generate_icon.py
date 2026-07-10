"""Generate a modern app icon for DC-ShiftMaster Pro."""

from PIL import Image, ImageDraw, ImageFont
import os
import struct
import io

SIZE = 256
OUT = os.path.join(os.path.dirname(__file__), "app_icon.ico")

BG = "#0F172A"
SURFACE = "#1E293B"
INDIGO = "#6366F1"
CYAN = "#22D3EE"
WHITE = "#F1F5F9"
SLATE = "#334155"


def _make_icon_image(size: int) -> Image.Image:
    """Create the icon at a specific size."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    r = max(size // 5, 4)

    # Background
    draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=r, fill=BG)
    draw.rounded_rectangle([1, 1, size - 2, size - 2], radius=r - 1,
                           fill=None, outline=SLATE, width=1)

    # 3x3 grid of rounded squares
    margin = size // 5
    grid_area = size - 2 * margin
    cell = grid_area // 3
    dot_r = max(cell // 3, 2)
    corner = max(dot_r // 3, 1)

    for row in range(3):
        for col in range(3):
            cx = margin + col * cell + cell // 2
            cy = margin + row * cell + cell // 2
            color = INDIGO if (row + col) % 2 == 0 else CYAN
            draw.rounded_rectangle(
                [cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r],
                radius=corner, fill=color)

    # Bottom accent bar
    bar_h = max(size // 40, 2)
    bar_y = size - margin + margin // 3
    if bar_y + bar_h < size - 2:
        draw.rounded_rectangle(
            [margin, bar_y, size - margin, bar_y + bar_h],
            radius=max(bar_h // 2, 1), fill=INDIGO)

    return img


def _write_ico(images: list[Image.Image], path: str) -> None:
    """Write a proper ICO file manually for reliable Windows icon embedding."""
    count = len(images)
    # ICO header: 6 bytes
    header = struct.pack("<HHH", 0, 1, count)

    # Each directory entry: 16 bytes
    # Then image data (PNG format for each)
    entries = []
    png_data_list = []

    for img in images:
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        png_bytes = buf.getvalue()
        png_data_list.append(png_bytes)

        w = img.width if img.width < 256 else 0
        h = img.height if img.height < 256 else 0

        entries.append({
            "width": w,
            "height": h,
            "colors": 0,
            "reserved": 0,
            "planes": 1,
            "bpp": 32,
            "size": len(png_bytes),
        })

    # Calculate offsets: header(6) + entries(16 * count) + data
    data_offset = 6 + 16 * count
    current_offset = data_offset

    with open(path, "wb") as f:
        f.write(header)

        # Write directory entries
        for i, entry in enumerate(entries):
            f.write(struct.pack(
                "<BBBBHHII",
                entry["width"],
                entry["height"],
                entry["colors"],
                entry["reserved"],
                entry["planes"],
                entry["bpp"],
                entry["size"],
                current_offset,
            ))
            current_offset += entry["size"]

        # Write PNG data
        for png_bytes in png_data_list:
            f.write(png_bytes)


def generate():
    sizes = [16, 24, 32, 48, 64, 128, 256]
    images = [_make_icon_image(s) for s in sizes]
    _write_ico(images, OUT)
    fsize = os.path.getsize(OUT)
    print(f"Icon saved to {OUT} ({fsize} bytes, {len(sizes)} sizes)")


if __name__ == "__main__":
    generate()
