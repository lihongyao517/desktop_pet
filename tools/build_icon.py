from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
SCALE = 2
SIZE = 1024


def scaled(value: int | float) -> int:
    return round(value * SCALE)


def points(values: list[tuple[int, int]]) -> list[tuple[int, int]]:
    return [(scaled(x), scaled(y)) for x, y in values]


def line(draw: ImageDraw.ImageDraw, values: list[tuple[int, int]], fill: str, width: int) -> None:
    draw.line(points(values), fill=fill, width=scaled(width), joint="curve")
    radius = scaled(width) // 2
    for x, y in (points(values)[0], points(values)[-1]):
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=fill)


def ellipse(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], **kwargs: object) -> None:
    draw.ellipse(tuple(scaled(value) for value in box), **kwargs)


def polygon(draw: ImageDraw.ImageDraw, values: list[tuple[int, int]], **kwargs: object) -> None:
    draw.polygon(points(values), **kwargs)


def render() -> Image.Image:
    image = Image.new("RGBA", (scaled(SIZE), scaled(SIZE)), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    ink = "#20282f"
    paper = "#f7f9f8"
    amber = "#f4a62a"
    teal = "#65c3cb"

    draw.rounded_rectangle(
        (scaled(42), scaled(42), scaled(982), scaled(982)),
        radius=scaled(190),
        fill=ink,
        outline="#52616a",
        width=scaled(16),
    )
    ellipse(draw, (147, 785, 853, 901), fill="#13191d")

    # Tank, water, plants, fish and bubbles.
    polygon(draw, [(683, 258), (896, 258), (881, 610), (700, 610)], fill=paper)
    polygon(draw, [(699, 278), (879, 278), (866, 592), (715, 592)], fill=teal)
    polygon(draw, [(712, 533), (747, 512), (793, 547), (834, 518), (868, 541), (866, 592), (715, 592)], fill="#f2d37e")
    line(draw, [(740, 551), (740, 469), (716, 440)], "#238d68", 13)
    line(draw, [(740, 487), (770, 452)], "#238d68", 11)
    line(draw, [(838, 551), (838, 486), (816, 460)], "#238d68", 13)
    polygon(draw, [(765, 422), (730, 395), (730, 449)], fill="#ff8c55")
    ellipse(draw, (763, 399, 841, 445), fill="#ff8c55", outline=ink, width=scaled(7))
    ellipse(draw, (818, 410, 829, 421), fill=ink)
    for box in ((742, 378, 760, 396), (718, 350, 730, 362), (843, 466, 865, 488)):
        ellipse(draw, box, outline=paper, width=scaled(6))
    line(draw, [(716, 307), (867, 307)], "#e8ffff", 8)

    # Chair behind the figure.
    draw.rounded_rectangle(
        (scaled(194), scaled(437), scaled(320), scaled(681)),
        radius=scaled(25), fill="#52616a", outline=paper, width=scaled(15)
    )

    # Desk and laptop.
    polygon(draw, [(379, 598), (755, 598), (755, 649), (379, 649)], fill="#aebbc1")
    line(draw, [(411, 648), (385, 836)], paper, 23)
    line(draw, [(718, 648), (743, 836)], paper, 23)
    polygon(draw, [(486, 399), (691, 399), (666, 594), (457, 594)], fill="#303a40")
    polygon(draw, [(505, 423), (668, 423), (649, 568), (482, 568)], fill="#dff9f4")
    line(draw, [(521, 464), (612, 464)], "#2e7d78", 11)
    line(draw, [(514, 503), (630, 503)], amber, 11)
    line(draw, [(506, 542), (582, 542)], "#2e7d78", 11)
    polygon(draw, [(450, 590), (671, 590), (706, 624), (425, 624)], fill="#65727a")

    # Body and limbs, outlined once for strong small-size legibility.
    limbs = [
        [(318, 409), (340, 605), (431, 684), (464, 830)],
        [(340, 605), (305, 716), (347, 830)],
        [(330, 455), (421, 536), (511, 615)],
        [(332, 482), (389, 590), (560, 615)],
        [(445, 830), (503, 830)],
        [(326, 830), (384, 830)],
    ]
    for limb in limbs:
        line(draw, limb, ink, 39)
        line(draw, limb, paper, 25)
    ellipse(draw, (488, 598, 522, 632), fill="#fffdf8", outline=ink, width=scaled(8))
    ellipse(draw, (540, 598, 574, 632), fill="#fffdf8", outline=ink, width=scaled(8))

    # Head, face, scarf, mug and steam.
    ellipse(draw, (213, 233, 395, 415), fill="#fffdf8", outline=paper, width=scaled(18))
    line(draw, [(275, 311), (290, 311)], ink, 11)
    line(draw, [(335, 311), (350, 311)], ink, 11)
    line(draw, [(319, 349), (347, 349)], ink, 11)
    line(draw, [(291, 407), (365, 407)], amber, 19)
    line(draw, [(361, 410), (435, 455)], amber, 18)
    line(draw, [(219, 293), (244, 254), (290, 232), (335, 234)], "#52616a", 13)
    polygon(draw, [(397, 533), (463, 533), (463, 603), (397, 603)], fill="#fff4d8")
    line(draw, [(463, 551), (484, 551), (484, 584), (463, 584)], paper, 9)
    line(draw, [(414, 517), (407, 495), (420, 468)], "#d7dee3", 8)
    line(draw, [(441, 517), (448, 495), (437, 468)], "#d7dee3", 8)

    ellipse(draw, (854, 188, 888, 222), fill=amber)
    line(draw, [(838, 205), (807, 205)], amber, 9)
    line(draw, [(904, 205), (935, 205)], amber, 9)
    line(draw, [(871, 172), (871, 141)], amber, 9)
    line(draw, [(871, 238), (871, 269)], amber, 9)

    return image.resize((SIZE, SIZE), Image.Resampling.LANCZOS)


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    image = render()
    image.save(ASSETS / "CodexDesktopPet.png")
    image.save(
        ASSETS / "CodexDesktopPet.ico",
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )


if __name__ == "__main__":
    main()
