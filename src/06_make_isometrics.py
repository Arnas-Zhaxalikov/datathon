"""Изометрическая графика для слайдов. Генерирует SVG в outputs/isometric/.

Тема задаётся переменной ISO_THEME: light (по умолчанию) или dark.
Объём даётся тремя способами: три тона на гранях по направлению света,
градиент вдоль каждой грани и мягкая тень на опорной плоскости.
"""
import json
import math
import os

OUT = "outputs/isometric"
os.makedirs(OUT, exist_ok=True)

THEME = os.environ.get("ISO_THEME", "light")
COS30 = math.cos(math.radians(30))

PALETTE = {
    "light": dict(navy="#3C6FB5", steel="#6E86AD", blue="#2C6CB0", ochre="#C0762A",
                  slate="#98A9C4", mute="#C2CCDB", shadow="#7B8AA3", grid="#DCE2EC"),
    "dark":  dict(navy="#3A5286", steel="#445C8A", blue="#4A8CD4", ochre="#C07F33",
                  slate="#2E4168", mute="#26344F", shadow="#070C18", grid="#2B3C60"),
}[THEME]
SHADOW_OP = 0.20 if THEME == "light" else 0.34
FACE = {"top": 1.0, "right": 0.78, "left": 0.60} if THEME == "light" else \
       {"top": 1.0, "right": 0.70, "left": 0.48}


def shade(hex_color, k, lift=0.0):
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    f = lambda c: max(0, min(255, int(c * k + 255 * lift)))
    return "#%02X%02X%02X" % (f(r), f(g), f(b))


def project(x, y, z, s, ox, oy):
    return (x - y) * COS30 * s + ox, (x + y) * 0.5 * s - z * s + oy


class Scene:
    def __init__(self, prefix, s, ox, oy):
        self.prefix, self.s, self.ox, self.oy = prefix, s, ox, oy
        self.defs, self.body, self.n = [], [], 0
        self.labels = []

    def _grad(self, base, face):
        self.n += 1
        gid = f"{self.prefix}{self.n}"
        c = shade(base, FACE[face])
        c1, c2 = shade(c, 1.0, 0.06), shade(c, 0.86)
        x2, y2 = ("0%", "100%") if face == "top" else ("100%", "100%")
        self.defs.append(
            f'<linearGradient id="{gid}" x1="0%" y1="0%" x2="{x2}" y2="{y2}">'
            f'<stop offset="0%" stop-color="{c1}"/><stop offset="100%" stop-color="{c2}"/>'
            f'</linearGradient>')
        return f"url(#{gid})"

    def shadow(self, x, y, dx, dy, spread=0.35, op=None, z=0.0):
        p = lambda X, Y: "%.1f,%.1f" % project(X, Y, z, self.s, self.ox, self.oy)
        pts = " ".join([p(x - spread, y - spread), p(x + dx + spread, y - spread),
                        p(x + dx + spread, y + dy + spread), p(x - spread, y + dy + spread)])
        self.body.append(f'<polygon points="{pts}" fill="{PALETTE["shadow"]}" '
                         f'opacity="{SHADOW_OP if op is None else op}"/>')

    def plate(self, x, y, dx, dy, color=None, op=1.0):
        p = lambda X, Y: "%.1f,%.1f" % project(X, Y, 0, self.s, self.ox, self.oy)
        pts = " ".join([p(x, y), p(x + dx, y), p(x + dx, y + dy), p(x, y + dy)])
        self.body.append(f'<polygon points="{pts}" fill="{color or PALETTE["grid"]}" opacity="{op}"/>')

    def line(self, x1, y1, x2, y2, color=None, width=1.2, op=0.9):
        a = project(x1, y1, 0, self.s, self.ox, self.oy)
        b = project(x2, y2, 0, self.s, self.ox, self.oy)
        self.body.append(f'<line x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{b[0]:.1f}" y2="{b[1]:.1f}" '
                         f'stroke="{color or PALETTE["grid"]}" stroke-width="{width}" opacity="{op}"/>')

    def cuboid(self, x, y, dx, dy, h, kind="navy", z=0.0, op=1.0):
        base = PALETTE[kind]
        p = lambda X, Y, Z: "%.1f,%.1f" % project(X, Y, Z, self.s, self.ox, self.oy)
        faces = [
            ("left", [p(x, y + dy, z + h), p(x + dx, y + dy, z + h), p(x + dx, y + dy, z), p(x, y + dy, z)]),
            ("right", [p(x + dx, y, z + h), p(x + dx, y + dy, z + h), p(x + dx, y + dy, z), p(x + dx, y, z)]),
            ("top", [p(x, y, z + h), p(x + dx, y, z + h), p(x + dx, y + dy, z + h), p(x, y + dy, z + h)]),
        ]
        a = f' opacity="{op}"' if op < 1 else ""
        for face, pts in faces:
            self.body.append(f'<polygon points="{" ".join(pts)}" fill="{self._grad(base, face)}"'
                             f' stroke="{shade(base, 0.62 if THEME == "light" else 0.34)}"'
                             f' stroke-width="1"{a}/>')
        edge = shade(base, 1.0, 0.16)
        self.body.append(f'<polyline points="{p(x, y, z + h)} {p(x + dx, y, z + h)}" fill="none" '
                         f'stroke="{edge}" stroke-width="1.6" opacity="{0.7 * op:.2f}"/>')

    def prism(self, corners, h, kind="navy", op=1.0):
        """Призма по четырём углам основания: время идёт по горизонтали экрана."""
        base = PALETTE[kind]
        p = lambda c, Z: "%.1f,%.1f" % project(c[0], c[1], Z, self.s, self.ox, self.oy)
        a, b, c, d = corners
        faces = [("left", [p(d, h), p(c, h), p(c, 0), p(d, 0)]),
                 ("right", [p(b, h), p(c, h), p(c, 0), p(b, 0)]),
                 ("top", [p(a, h), p(b, h), p(c, h), p(d, h)])]
        o = f' opacity="{op}"' if op < 1 else ""
        for face, pts in faces:
            self.body.append(f'<polygon points="{" ".join(pts)}" fill="{self._grad(base, face)}"'
                             f' stroke="{shade(base, 0.62 if THEME == "light" else 0.34)}"'
                             f' stroke-width="1"{o}/>')
        edge = shade(base, 1.0, 0.16)
        self.body.append(f'<polyline points="{p(a, h)} {p(b, h)}" fill="none" stroke="{edge}" '
                         f'stroke-width="1.6" opacity="{0.7 * op:.2f}"/>')

    def arrow(self, p1, p2, color, width=3.0, head=14.0):
        (x1, y1), (x2, y2) = p1, p2
        ang = math.atan2(y2 - y1, x2 - x1)
        bx, by = x2 - head * math.cos(ang), y2 - head * math.sin(ang)
        l = (bx - head * 0.5 * math.sin(ang), by + head * 0.5 * math.cos(ang))
        r = (bx + head * 0.5 * math.sin(ang), by - head * 0.5 * math.cos(ang))
        self.body.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{bx:.1f}" y2="{by:.1f}" stroke="{color}" '
            f'stroke-width="{width}" stroke-linecap="round"/>'
            f'<polygon points="{x2:.1f},{y2:.1f} {l[0]:.1f},{l[1]:.1f} {r[0]:.1f},{r[1]:.1f}" fill="{color}"/>')

    def label(self, x, y, z, text, align="right", size=22, tone="ink"):
        px, py = project(x, y, z, self.s, self.ox, self.oy)
        self.labels.append(dict(x=round(px, 1), y=round(py, 1), text=text, align=align,
                                size=size, tone=tone))

    def at(self, x, y, z):
        return project(x, y, z, self.s, self.ox, self.oy)

    def svg(self, name, w, h, label):
        out = (f'<svg viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" aria-label="{label}" '
               f'xmlns="http://www.w3.org/2000/svg"><defs>{"".join(self.defs)}</defs>'
               f'{"".join(self.body)}</svg>')
        with open(f"{OUT}/{name}.svg", "w", encoding="utf-8") as f:
            f.write(out)
        if self.labels:
            with open(f"{OUT}/{name}.labels.json", "w", encoding="utf-8") as f:
                json.dump(dict(w=w, h=h, labels=self.labels), f, ensure_ascii=False)
        print(f"{OUT}/{name}.svg  {len(out) // 1024} КБ  подписей: {len(self.labels)}")


def grid_svg(w=1920, h=1080, step=112, op=0.55):
    span = int(h * 0.577 / step) + 1
    c = PALETTE["grid"]
    parts = []
    for i in range(-span, int(w / step) + span + 1):
        x0 = i * step
        parts.append(f'<line x1="{x0}" y1="0" x2="{x0 + h * 0.577:.0f}" y2="{h}" stroke="{c}" stroke-width="1"/>')
        parts.append(f'<line x1="{x0}" y1="0" x2="{x0 - h * 0.577:.0f}" y2="{h}" stroke="{c}" stroke-width="1"/>')
    out = (f'<svg viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" '
           f'aria-label="Изометрическая сетка фона" xmlns="http://www.w3.org/2000/svg">'
           f'<g opacity="{op}">{"".join(parts)}</g></svg>')
    with open(f"{OUT}/grid.svg", "w", encoding="utf-8") as f:
        f.write(out)
    print(f"{OUT}/grid.svg  {len(out) // 1024} КБ")


grid_svg()

# Обложка: стопка слоёв архива, верхний слой — объединённая таблица
sc = Scene("a", 66, 410, 320)
sc.shadow(0, 0, 5.2, 5.2, spread=0.5)
for kind, z in [("mute", 0.0), ("slate", 0.9), ("steel", 1.8), ("blue", 2.7)]:
    sc.cuboid(0, 0, 5.2, 5.2, 0.42, kind=kind, z=z)
sc.cuboid(0.9, 0.9, 3.4, 3.4, 0.54, kind="ochre", z=4.0)
for dx, dy, z in [(6.7, 0.4, 3.0), (0.2, 6.8, 2.4), (6.0, 1.2, 5.2)]:
    sc.cuboid(dx, dy, 0.52, 0.52, 0.52, kind="blue", z=z, op=0.95)
sc.svg("cover_stack", 840, 720, "Стопка слоёв архива: формы сводятся в одну таблицу")

# Конвейер из пяти шагов
sc = Scene("b", 52, 132, 104)
for i in range(5):
    sc.shadow(i * 2.55, -i * 2.55, 1.5, 1.5, spread=0.2)
for i in range(5):
    kind = "ochre" if i == 4 else ("blue" if i == 0 else "steel")
    sc.cuboid(i * 2.55, -i * 2.55, 1.5, 1.5, 0.95, kind=kind)
for i in range(4):
    sc.arrow(sc.at(i * 2.55 + 1.62, -i * 2.55 + 0.75, 0.55),
             sc.at((i + 1) * 2.55 - 0.3, -(i + 1) * 2.55 + 0.75, 0.55),
             shade(PALETTE["steel"], 0.8), 2.6, 12)
sc.svg("pipeline", 1430, 260, "Конвейер из пяти шагов обработки данных")

# Слияние четырёх форм в одну таблицу
sc = Scene("c", 54, 540, 74)
for i in range(4):
    col, row = i % 2, i // 2
    sc.cuboid(col * 2.8, row * 2.8, 2.2, 2.2, 0.44, kind="steel")
sc.shadow(-0.7, -0.7, 6.3, 6.3, spread=0.5, z=-7.0)
sc.cuboid(-0.7, -0.7, 6.3, 6.3, 0.7, kind="ochre", z=-7.0)
sc.arrow(sc.at(2.5, 2.5, -0.9), sc.at(2.5, 2.5, -5.2), PALETTE["ochre"], 3.4, 16)
sc.svg("merge", 1080, 800, "Четыре формы обследования сводятся в одну таблицу домохозяйств")

# Гант-диаграмма конкурса: ось X — день от 21.09, ось Y — этап
STAGES = [
    ("Дескриптивная аналитика", 0, 9, "done"),
    ("Гипотезы и методология", 10, 16, "next"),
    ("Завершение проекта", 17, 21, "plan"),
    ("Допуск к финалу", 22, 25, "plan"),
    ("Финал и защита", 29, 30, "final"),
]
TICKS = [(0, "21.09"), (9, "30.09"), (16, "7.10"), (21, "12.10"), (29, "20.10")]
KIND = {"done": "blue", "next": "ochre", "plan": "steel", "final": "navy"}

ROW, BARH = 1.6, 1.05

sc = Scene("d", 22, 360, 92)
sc.plate(-1.0, -1.0, 32.0, len(STAGES) * ROW + 0.6, PALETTE["grid"], op=0.45)
for d, _ in TICKS:
    sc.line(d, -1.0, d, len(STAGES) * ROW - 0.4, shade(PALETTE["shadow"], 1.0, 0.26), 1.4, 0.85)
for r, (name, s0, s1, kind) in enumerate(STAGES):
    v = r * ROW
    h = 1.75 if kind == "done" else 1.15
    sc.shadow(s0, v, s1 - s0, BARH, spread=0.16)
    sc.cuboid(s0, v, s1 - s0, BARH, h, kind=KIND[kind])
    sc.label(s0, v - 0.45, h + 0.3, name, align="left", size=23)
for d, txt in TICKS:
    sc.label(d, -1.9, 0.15, txt, align="center", size=20, tone="muted")
sc.svg("gantt", 1180, 580, "Гант-диаграмма этапов конкурса от 21 сентября до 20 октября")
