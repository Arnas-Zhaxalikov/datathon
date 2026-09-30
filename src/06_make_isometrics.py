"""Изометрическая графика для слайдов. Генерирует SVG в outputs/isometric/."""
import math
import os

OUT = "outputs/isometric"
os.makedirs(OUT, exist_ok=True)

COS30 = math.cos(math.radians(30))

SLAB = {
    "navy":  ("#2A3E68", "#1D2C4C", "#16223A"),
    "blue":  ("#4A8CD4", "#36699F", "#27507B"),
    "ochre": ("#C07F33", "#8E5D26", "#6B461C"),
    "steel": ("#35496F", "#253554", "#1A2740"),
}
EDGE = "#4C618C"


def project(x, y, z, s, ox, oy):
    return (x - y) * COS30 * s + ox, (x + y) * 0.5 * s - z * s + oy


def cuboid(x, y, dx, dy, h, s, ox, oy, kind="navy", z=0.0, opacity=1.0, edge=EDGE):
    """Параллелепипед: верхняя грань, правая (восток) и левая (юг)."""
    top_c, right_c, left_c = SLAB[kind]
    p = lambda X, Y, Z: "%.1f,%.1f" % project(X, Y, Z, s, ox, oy)
    top = " ".join([p(x, y, z + h), p(x + dx, y, z + h), p(x + dx, y + dy, z + h), p(x, y + dy, z + h)])
    right = " ".join([p(x + dx, y, z + h), p(x + dx, y + dy, z + h), p(x + dx, y + dy, z), p(x + dx, y, z)])
    left = " ".join([p(x, y + dy, z + h), p(x + dx, y + dy, z + h), p(x + dx, y + dy, z), p(x, y + dy, z)])
    a = f' opacity="{opacity}"' if opacity < 1 else ""
    return (f'<polygon points="{left}" fill="{left_c}" stroke="{edge}" stroke-width="1.5"{a}/>'
            f'<polygon points="{right}" fill="{right_c}" stroke="{edge}" stroke-width="1.5"{a}/>'
            f'<polygon points="{top}" fill="{top_c}" stroke="{edge}" stroke-width="1.5"{a}/>')


def arrow(x1, y1, x2, y2, color, width=3.0, head=13.0):
    ang = math.atan2(y2 - y1, x2 - x1)
    bx, by = x2 - head * math.cos(ang), y2 - head * math.sin(ang)
    l = (bx - head * 0.52 * math.sin(ang), by + head * 0.52 * math.cos(ang))
    r = (bx + head * 0.52 * math.sin(ang), by - head * 0.52 * math.cos(ang))
    return (f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{bx:.1f}" y2="{by:.1f}" '
            f'stroke="{color}" stroke-width="{width}" stroke-linecap="round"/>'
            f'<polygon points="{x2:.1f},{y2:.1f} {l[0]:.1f},{l[1]:.1f} {r[0]:.1f},{r[1]:.1f}" fill="{color}"/>')


def write(name, w, h, body, label):
    svg = (f'<svg viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" '
           f'aria-label="{label}" xmlns="http://www.w3.org/2000/svg">{body}</svg>')
    with open(f"{OUT}/{name}.svg", "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"{OUT}/{name}.svg  {len(svg) // 1024} КБ")
    return svg


# Фоновая изометрическая сетка
def grid(w=1920, h=1080, step=64, color="#2B3C60", op=0.5):
    parts = []
    span = int(h * 0.577 / step) + 1
    for i in range(-span, int(w / step) + span + 1):
        x0 = i * step
        parts.append(f'<line x1="{x0}" y1="0" x2="{x0 + h * 0.577:.0f}" y2="{h}" '
                     f'stroke="{color}" stroke-width="1"/>')
        parts.append(f'<line x1="{x0}" y1="0" x2="{x0 - h * 0.577:.0f}" y2="{h}" '
                     f'stroke="{color}" stroke-width="1"/>')
    return f'<g opacity="{op}">' + "".join(parts) + "</g>"


write("grid", 1920, 1080, grid(step=112, op=0.42), "Изометрическая сетка фона")

# Обложка: стопка слоёв данных, верхний слой — объединённая таблица
body, S, OX, OY = [], 66, 410, 300
for kind, z in [("navy", 0.0), ("navy", 0.9), ("steel", 1.8), ("blue", 2.7)]:
    body.append(cuboid(0, 0, 5.2, 5.2, 0.42, S, OX, OY, kind=kind, z=z))
body.append(cuboid(0.9, 0.9, 3.4, 3.4, 0.5, S, OX, OY, kind="ochre", z=4.0))
for dx, dy, z in [(6.6, 0.4, 3.1), (0.2, 6.7, 2.6), (5.9, 1.1, 5.4)]:
    body.append(cuboid(dx, dy, 0.5, 0.5, 0.5, S, OX, OY, kind="blue", z=z, opacity=0.9))
write("cover_stack", 830, 700, "".join(body),
      "Изометрическая стопка слоёв данных: формы архива сводятся в одну таблицу")

# Конвейер из пяти шагов
cubes, arrows, S, OX, OY = [], [], 52, 130, 96
for i in range(5):
    kind = "ochre" if i == 4 else ("blue" if i == 0 else "steel")
    cubes.append(cuboid(i * 2.55, -i * 2.55, 1.5, 1.5, 0.95, S, OX, OY, kind=kind))
    if i < 4:
        x1, y1 = project(i * 2.55 + 1.62, -i * 2.55 + 0.75, 0.55, S, OX, OY)
        x2, y2 = project((i + 1) * 2.55 - 0.32, -(i + 1) * 2.55 + 0.75, 0.55, S, OX, OY)
        arrows.append(arrow(x1, y1, x2, y2, "#93A7C8", 2.6, 12))
write("pipeline", 1420, 250, "".join(cubes) + "".join(arrows),
      "Конвейер из пяти шагов обработки данных")

# Слияние четырёх форм в одну таблицу
body, S, OX, OY = [], 54, 540, 70
for i in range(4):
    col, row = i % 2, i // 2
    body.append(cuboid(col * 2.8, row * 2.8, 2.2, 2.2, 0.44, S, OX, OY, kind="steel"))
body.append(cuboid(-0.7, -0.7, 6.3, 6.3, 0.66, S, OX, OY, kind="ochre", z=-7.0))
ax, ay = project(2.5, 2.5, -0.9, S, OX, OY)
bx, by = project(2.5, 2.5, -5.1, S, OX, OY)
body.append(arrow(ax, ay, bx, by, "#C07F33", 3.6, 16))
write("merge", 1080, 800, "".join(body),
      "Четыре формы обследования сводятся в одну таблицу домохозяйств")
