"""
 Copyright (C) 2026 Mauricio Bustos (m@bustos.org)
 This program is free software: you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation, either version 3 of the License, or
 (at your option) any later version.
"""

# Writes flat_bar.dxf (drawing) and flat_bar.step (model for milling quotes):
# 1/4" x 1" flat bar, two bolt holes, and a pocket + through cutout for the
# JHYOSSTHI JH-WPogo-10Pin magnetic pogo connector.
# Run: uv run --python 3.12 --with ezdxf --with cadquery python mechanical/flat_bar.py

from pathlib import Path

import cadquery as cq
import ezdxf
from ezdxf import units

MM = 1 / 25.4

# All dimensions in inches. X runs along the bar, Y across it; bottom end at X = 0.
LENGTH = 16.0
WIDTH = 1.0
THICKNESS = 0.25
HOLE_SPACING = 13.0
HOLE_DIA = 17 / 64  # free-fit clearance for a 1/4" bolt
HOLE_X = [(LENGTH - HOLE_SPACING) / 2, (LENGTH + HOLE_SPACING) / 2]

# Connector, ESTIMATED from the listing photos (no drawing published): flange
# 26 x 11 mm, body behind it 21 x 7.5 mm.  Measure one and update these.
# The flange sits flush in a pocket on the mating face; the body and wires pass
# through.  Corner radius suits a 1/8" end mill.
POCKET = (26.5 * MM, 11.5 * MM)   # flange + 0.25 mm a side
POCKET_DEPTH = 1.6 * MM           # flange thickness, estimated
THRU = (21.5 * MM, 8.0 * MM)      # body + 0.25 mm a side
CORNER_R = 1 / 16
# Centred between the bottom end and the bottom hole.
CONN_X = (HOLE_X[0] - HOLE_DIA / 2) / 2
CONN_Y = WIDTH / 2


def rounded_rect(msp, cx, cy, w, h, r, layer, s=1.0, ox=0.0, oy=0.0):
    """Closed polyline, rounded corners; scaled by s and offset to (ox, oy)."""
    x0, x1, y0, y1 = cx - w / 2, cx + w / 2, cy - h / 2, cy + h / 2
    b = 0.41421356  # tan(22.5 deg): a 90 degree arc
    pts = [
        (x0 + r, y0, 0), (x1 - r, y0, b), (x1, y0 + r, 0), (x1, y1 - r, b),
        (x1 - r, y1, 0), (x0 + r, y1, b), (x0, y1 - r, 0), (x0, y0 + r, b),
    ]
    msp.add_lwpolyline([(ox + x * s, oy + y * s, 0, 0, bulge) for x, y, bulge in pts],
                       format="xyseb", close=True, dxfattribs={"layer": layer})


def drawing(out):
    doc = ezdxf.new("R2010", setup=True)
    doc.units = units.IN
    doc.header["$MEASUREMENT"] = 0
    for name, color, lt in (("OUTLINE", 7, "CONTINUOUS"), ("HOLES", 1, "CONTINUOUS"),
                            ("CONNECTOR_THRU", 3, "CONTINUOUS"), ("CONNECTOR_POCKET", 5, "DASHED"),
                            ("DIMS", 4, "CONTINUOUS")):
        doc.layers.add(name, color=color, linetype=lt)
    msp = doc.modelspace()
    fmt = {"dimtxt": 0.12, "dimasz": 0.1, "dimexo": 0.05, "dimexe": 0.08, "dimgap": 0.04,
           "dimdec": 3, "dimdsep": ord("."), "dimtad": 1, "dimzin": 8}

    def dim(base, p1, p2, angle=0, scale=1.0):
        o = dict(fmt, dimlfac=1 / scale)
        msp.add_linear_dim(base=base, p1=p1, p2=p2, angle=angle, dimstyle="Standard",
                           override=o, dxfattribs={"layer": "DIMS"}).render()

    def note(s, x, y, h=0.15):
        msp.add_text(s, height=h, dxfattribs={"layer": "DIMS"}).set_placement((x, y))

    # --- full part, 1:1 ---------------------------------------------------------
    msp.add_lwpolyline([(0, 0), (LENGTH, 0), (LENGTH, WIDTH), (0, WIDTH)], close=True,
                       dxfattribs={"layer": "OUTLINE"})
    for x in HOLE_X:
        msp.add_circle((x, CONN_Y), HOLE_DIA / 2, dxfattribs={"layer": "HOLES"})
    rounded_rect(msp, CONN_X, CONN_Y, *POCKET, CORNER_R, "CONNECTOR_POCKET")
    rounded_rect(msp, CONN_X, CONN_Y, *THRU, CORNER_R, "CONNECTOR_THRU")
    dim((0, -0.8), (0, 0), (LENGTH, 0))
    dim((0, -0.4), (HOLE_X[0], CONN_Y), (HOLE_X[1], CONN_Y))
    dim((0, -0.4), (0, 0), (HOLE_X[0], CONN_Y))
    dim((-0.4, 0), (0, 0), (0, WIDTH), angle=90)
    note(f'1/4" x 1" 6061-T6 ALUMINUM FLAT BAR, {THICKNESS:.3f} THK.  QTY 2 (IDENTICAL).', 0, WIDTH + 0.65)
    note(f'2X %%C{HOLE_DIA:.3f} THRU.  BREAK ALL EDGES.  TOL +/-0.010 UNLESS NOTED.', 0, WIDTH + 0.35)

    # --- detail of the connector end, 4:1 ------------------------------------------
    s, ox, oy, xmax = 4.0, 0.0, -6.5, 1.9
    msp.add_lwpolyline([(ox + xmax * s, oy), (ox, oy), (ox, oy + WIDTH * s), (ox + xmax * s, oy + WIDTH * s)],
                       dxfattribs={"layer": "OUTLINE"})
    zig = [(xmax, 0), (xmax, 0.4), (xmax - 0.05, 0.47), (xmax + 0.05, 0.53), (xmax, 0.6), (xmax, WIDTH)]
    msp.add_lwpolyline([(ox + x * s, oy + y * s) for x, y in zig], dxfattribs={"layer": "OUTLINE"})
    msp.add_circle((ox + HOLE_X[0] * s, oy + CONN_Y * s), HOLE_DIA / 2 * s, dxfattribs={"layer": "HOLES"})
    rounded_rect(msp, CONN_X, CONN_Y, *POCKET, CORNER_R, "CONNECTOR_POCKET", s, ox, oy)
    rounded_rect(msp, CONN_X, CONN_Y, *THRU, CORNER_R, "CONNECTOR_THRU", s, ox, oy)

    def P(x, y):
        return (ox + x * s, oy + y * s)

    px0, px1 = CONN_X - POCKET[0] / 2, CONN_X + POCKET[0] / 2
    py0, py1 = CONN_Y - POCKET[1] / 2, CONN_Y + POCKET[1] / 2
    tx0, tx1 = CONN_X - THRU[0] / 2, CONN_X + THRU[0] / 2
    ty0, ty1 = CONN_Y - THRU[1] / 2, CONN_Y + THRU[1] / 2
    dim((0, oy - 0.5), P(0, 0), P(CONN_X, CONN_Y), scale=s)
    dim((0, oy - 1.0), P(px0, py0), P(px1, py0), scale=s)
    dim((0, oy - 1.5), P(tx0, ty0), P(tx1, ty0), scale=s)
    dim((0, oy - 2.0), P(0, 0), P(HOLE_X[0], CONN_Y), scale=s)
    dim((ox - 0.5, 0), P(px0, py0), P(px0, py1), angle=90, scale=s)
    dim((ox - 1.0, 0), P(tx0, ty0), P(tx0, ty1), angle=90, scale=s)
    nx = ox + xmax * s + 0.6
    note("DETAIL: CONNECTOR END (4:1)", ox, oy + WIDTH * s + 0.5, 0.2)
    note(f"POCKET (DASHED): {POCKET_DEPTH:.3f} DEEP FROM MATING FACE, R{CORNER_R:.4f} CORNERS", nx, oy + 3.0)
    note(f"CUTOUT (SOLID): THRU, R{CORNER_R:.4f} CORNERS", nx, oy + 2.6)
    note("CONNECTOR SIZES ARE ESTIMATES: VERIFY AGAINST A PART BEFORE CUTTING", nx, oy + 2.0)
    note("JHYOSSTHI JH-WPogo-10Pin MAGNETIC POGO CONNECTOR", nx, oy + 1.6)

    doc.saveas(out)


def model(out):
    """Solid in mm: mating face is +Z."""
    L, W, T = LENGTH / MM, WIDTH / MM, THICKNESS / MM
    cx, cy = CONN_X / MM - L / 2, CONN_Y / MM - W / 2
    r = CORNER_R / MM
    bar = cq.Workplane("XY").box(L, W, T)
    bar = (bar.faces(">Z").workplane()
           .pushPoints([(x / MM - L / 2, 0) for x in HOLE_X]).hole(HOLE_DIA / MM))
    def cutter(w, h, depth):
        # rounded rectangle prism, from just above the mating face down `depth`
        return (cq.Workplane("XY").workplane(offset=T / 2 + 1).center(cx, cy)
                .rect(w / MM, h / MM).extrude(-(depth + 1)).edges("|Z").fillet(r))

    bar = bar.cut(cutter(*POCKET, POCKET_DEPTH / MM)).cut(cutter(*THRU, T + 1))
    cq.exporters.export(bar, str(out))


def main():
    here = Path(__file__).parent
    drawing(here / "flat_bar.dxf")
    model(here / "flat_bar.step")
    print(f"connector centre {CONN_X:.3f} in from the bottom end; "
          f"walls: end {CONN_X - POCKET[0] / 2:.3f} in, hole {HOLE_X[0] - HOLE_DIA / 2 - CONN_X - POCKET[0] / 2:.3f} in")


if __name__ == "__main__":
    main()
