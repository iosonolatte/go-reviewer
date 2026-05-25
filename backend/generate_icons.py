"""
生成 Go-Reviewer 应用图标 (围棋棋盘风格)
输出: src-tauri/icons/  下的 PNG / ICO / ICNS 文件
"""
from PIL import Image, ImageDraw
from pathlib import Path
import struct
import zlib


def draw_logo(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    pad = max(2, size // 16)
    board_color = (220, 179, 92, 255)
    edge_color = (102, 71, 32, 255)

    d.rounded_rectangle(
        [pad, pad, size - pad, size - pad],
        radius=size // 8,
        fill=board_color,
        outline=edge_color,
        width=max(1, size // 64),
    )

    inner = size - 2 * pad
    grid_pad = pad + inner // 8
    grid_size = size - 2 * grid_pad
    cells = 6
    step = grid_size / cells
    line_w = max(1, size // 96)
    for i in range(cells + 1):
        x = grid_pad + step * i
        d.line(
            [(x, grid_pad), (x, grid_pad + grid_size)],
            fill=edge_color,
            width=line_w,
        )
        y = grid_pad + step * i
        d.line(
            [(grid_pad, y), (grid_pad + grid_size, y)],
            fill=edge_color,
            width=line_w,
        )

    stone_r = step * 0.42
    def stone(cx, cy, color):
        if color == "black":
            shadow_off = max(1, size // 128)
            d.ellipse(
                [cx - stone_r + shadow_off, cy - stone_r + shadow_off,
                 cx + stone_r + shadow_off, cy + stone_r + shadow_off],
                fill=(0, 0, 0, 80),
            )
            d.ellipse(
                [cx - stone_r, cy - stone_r, cx + stone_r, cy + stone_r],
                fill=(20, 20, 24, 255),
                outline=(0, 0, 0, 255),
                width=max(1, size // 256),
            )
        else:
            d.ellipse(
                [cx - stone_r, cy - stone_r, cx + stone_r, cy + stone_r],
                fill=(248, 244, 232, 255),
                outline=(120, 100, 70, 255),
                width=max(1, size // 256),
            )

    def grid_pos(c, r):
        return grid_pad + step * c, grid_pad + step * r

    stone(*grid_pos(2, 2), "black")
    stone(*grid_pos(3, 2), "white")
    stone(*grid_pos(2, 3), "white")
    stone(*grid_pos(3, 3), "black")
    stone(*grid_pos(4, 4), "black")

    return img


def write_ico(images, path: Path):
    icon_sizes = [16, 32, 48, 64, 128, 256]
    pngs = [im.resize((s, s), Image.LANCZOS) for s, im in zip(icon_sizes, images)]
    pngs[0].save(
        path,
        format="ICO",
        sizes=[(s, s) for s in icon_sizes],
    )


def write_icns_fallback(img: Image.Image, path: Path):
    img.save(path, format="PNG")


def main():
    out = Path(__file__).resolve().parent.parent / "src-tauri" / "icons"
    out.mkdir(parents=True, exist_ok=True)

    base_sizes = {
        "32x32.png": 32,
        "128x128.png": 128,
        "128x128@2x.png": 256,
        "icon.png": 512,
        "Square30x30Logo.png": 30,
        "Square44x44Logo.png": 44,
        "Square71x71Logo.png": 71,
        "Square89x89Logo.png": 89,
        "Square107x107Logo.png": 107,
        "Square142x142Logo.png": 142,
        "Square150x150Logo.png": 150,
        "Square284x284Logo.png": 284,
        "Square310x310Logo.png": 310,
        "StoreLogo.png": 50,
    }

    masters = {}
    for fname, sz in base_sizes.items():
        img = draw_logo(sz)
        masters[sz] = img
        img.save(out / fname)
        print(f"  wrote {fname} ({sz}x{sz})")

    icon_sizes = [16, 32, 48, 64, 128, 256]
    icon_imgs = [draw_logo(s) for s in icon_sizes]
    write_ico(icon_imgs, out / "icon.ico")
    print(f"  wrote icon.ico (multi-resolution)")

    write_icns_fallback(draw_logo(512), out / "icon.icns")
    print(f"  wrote icon.icns (PNG fallback)")

    print(f"\nDone. Icons in {out}")


if __name__ == "__main__":
    main()
