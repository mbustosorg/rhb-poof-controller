#!/usr/bin/env python3
"""
Place the poof controller board.  Run with KiCad's Python; build.sh does.

Reads:  rhb_poof_controller.net
Writes: rhb_poof_controller.kicad_pcb, unrouted; route.py routes it

Layout, 2 layers, about 74 x 43 mm:
  - The Waveshare ESP32-S3-POE-ETH runs across the top, socketed top face
    up, its RJ45 / USB-C end 2 mm past the left edge so the cable and USB-C
    plug clear the carrier.
  - R1, D1 and U1, the PC817, sit under the module between its header rows,
    U1 by IO40 (pin 11), LED pins facing down.
  - J1, the 12V side's terminal, and J2, the display connector by IO39 and
    IO38 (pins 12, 14), run along the bottom edge, entries facing off it.
  - The ground pour on B.Cu covers only the board side, so the 12V side
    shares no copper with it.
  - M3 holes in the four corners.
"""
import json
import os
import re
import sys

HERE   = os.path.dirname(os.path.abspath(__file__))
NET    = os.path.join(HERE, "rhb_poof_controller.net")
PCB    = os.path.join(HERE, "rhb_poof_controller.kicad_pcb")
PRO    = os.path.join(HERE, "rhb_poof_controller.kicad_pro")
FPROOT = "/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints"
# This board's own footprints, the project library in fp-lib-table
LOCAL_LIBS = {"rhb_poof_controller": os.path.join(HERE, "rhb_poof_controller.pretty")}

try:
    import pcbnew
except ImportError:
    sys.exit("ERROR: run with KiCad's bundled python3 (pcbnew not found).")

try:
    import wx; _APP = wx.App()
except Exception as _e:
    print("warning: wx init:", _e)

YEAR = 2026  # silkscreen copyright
MM = pcbnew.FromMM
def V(x, y): return pcbnew.VECTOR2I(MM(x), MM(y))

# ── parse netlist ────────────────────────────────────────────────────────────
src = open(NET).read()

comp_fp, comp_val = {}, {}
for ref, body in re.findall(
        r'\(comp\s+\(ref "([^"]+)"\)(.*?)(?=\(comp\s|\(libparts\b|\Z)', src, re.S):
    fp  = re.search(r'\(footprint "([^"]+)"\)', body)
    val = re.search(r'\(value "([^"]*)"\)', body)
    if fp:  comp_fp[ref]  = fp.group(1)
    if val: comp_val[ref] = val.group(1)

pad_net, netnames = {}, set()
for name, body in re.findall(
        r'\(net\s+\(code "\d+"\)\s+\(name "([^"]+)"\)(.*?)(?=\(net\s|\Z)', src, re.S):
    for ref, pin in re.findall(r'\(node\s+\(ref "([^"]+)"\)\s+\(pin "([^"]+)"\)', body):
        pad_net[(ref, pin)] = name
        netnames.add(name)

print(f"parsed {len(comp_fp)} components, {len(netnames)} nets, {len(pad_net)} pad-nets")

# ── board setup ──────────────────────────────────────────────────────────────
board = pcbnew.CreateEmptyBoard()
board.SetCopperLayerCount(2)

net_items = {}
for n in sorted(netnames):
    ni = pcbnew.NETINFO_ITEM(board, n)
    board.Add(ni); net_items[n] = ni

def load_fp(fpid):
    lib, name = fpid.split(":", 1)
    path = LOCAL_LIBS.get(lib, os.path.join(FPROOT, lib + ".pretty"))
    return pcbnew.FootprintLoad(path, name)

def add(ref, x, y, rot=0):
    """Place a footprint with its origin, pad 1 for every part here, at (x, y).

    rot is CCW degrees (KiCad convention).
    """
    fp = load_fp(comp_fp[ref])
    fp.SetFPID(pcbnew.LIB_ID(*comp_fp[ref].split(":", 1)))
    fp.SetReference(ref)
    fp.SetValue(comp_val.get(ref, ""))
    fp.SetPosition(V(x, y))
    if rot:
        fp.SetOrientationDegrees(rot)
    board.Add(fp)
    for pad in fp.Pads():
        key = (ref, pad.GetNumber())
        if key in pad_net:
            pad.SetNet(net_items[pad_net[key]])
    return fp

def add_mh(ref, cx, cy):
    fp = load_fp("MountingHole:MountingHole_3.2mm_M3")
    fp.SetReference(ref)
    fp.SetValue("M3")
    fp.SetPosition(V(cx, cy))
    board.Add(fp)

def set_rect(zone, x0, y0, x1, y1):
    sps = zone.Outline(); sps.NewOutline()
    for px, py in [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]:
        sps.Append(MM(px), MM(py))

# ── floorplan ────────────────────────────────────────────────────────────────
#
# Module pin 1 at (PX, PY), rotated 90 CCW: pins 1-20 run left to right along
# y = PY, pins 40-21 along y = PY - 17.78, the RJ45 end at the left.  The
# module is 72.8 x 21 mm, from PX - 19.87 to PX + 52.93 (generate_footprint.py).
PX, PY = 132.0, 125.0
PITCH  = 2.54
OVERHANG = 2.0

BX0 = PX - 19.87 + OVERHANG   # the RJ45 end hangs past this edge
BX1 = PX + 52.93 + 3.0
BY0 = 97.5
BY1 = 140.5
CORNER_R = 2.0
MH_INSET = 3.5

add("U2", PX, PY, rot=90)

# The 12V side's low parts sit under the module, between its header rows
# (y 108-124), so the board only needs one row of connectors below it.
# They're under 4.5 mm tall; the module sits about 8.5 mm up on its sockets.
#
# PC817 by IO40 (pin 11): LED pins 1-2 along the bottom, transistor pins
# 4-3 along the top.
U1_Y = 121.5
add("U1", 152.0, U1_Y, rot=90)
r1 = add("R1", 136.5, 111.0)
r1.Reference().SetPosition(V(141.58, 113.3))
add("D1", 147.5, 119.0, rot=180)

# One row along the bottom edge: J1, wire entry down, and J2, cable entry
# down, by IO39 and IO38 (pins 12 and 14).  Rotated 180, J1's pin 2 is to the
# left of pin 1.
j1 = add("J1", 130.0, 134.5, rot=180)
j1.Reference().SetPosition(V(119.0, 128.3))   # its default is off the edge
add("J2", 160.0, 131.0)

# ── silkscreen ───────────────────────────────────────────────────────────────
def silk(s, x, y, size=1.0, rot=0):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(s)
    t.SetLayer(pcbnew.F_SilkS)
    t.SetPosition(V(x, y))
    t.SetTextSize(V(size, size))
    t.SetTextThickness(MM(size * 0.15))
    if rot:
        t.SetTextAngleDegrees(rot)
    board.Add(t)

silk("RHB POOF", 150.0, 101.0, 1.5)
silk(f"m@bustos.org (c) {YEAR}", 173.5, 101.0, 0.8)
silk("+  -  D  C", 163.75, 137.6, 1.0)
silk("12V-  BTN", 127.46, 128.3, 1.0)
silk("12V SIDE", 145.0, 132.5, 1.0)
# The button's fuse is inline at the 12V supply, not on this board
silk("FUSE AT SUPPLY", 145.0, 134.3, 1.0)

# ── board outline ────────────────────────────────────────────────────────────
rr = pcbnew.PCB_SHAPE(board)
rr.SetShape(pcbnew.SHAPE_T_RECTANGLE)
rr.SetLayer(pcbnew.Edge_Cuts)
rr.SetWidth(MM(0.15))
rr.SetStart(V(BX0, BY0)); rr.SetEnd(V(BX1, BY1))
try:
    rr.SetCornerRadius(MM(CORNER_R))
except AttributeError:
    pass
board.Add(rr)
print(f"board outline: {BX1-BX0:.1f} x {BY1-BY0:.1f} mm")

d = MH_INSET
add_mh("H1", BX0 + d, BY0 + d)
add_mh("H2", BX1 - d, BY0 + d)
add_mh("H3", BX1 - d, BY1 - d)
add_mh("H4", BX0 + d, BY1 - d)

# ── GND pour, board side only ─────────────────────────────────────────────────
# Leaves out the 12V side: J1, R1 and D1 at the left, and the PC817's LED
# pins, so no ground copper runs under it.  A strip along the module's pin
# 1-20 row still reaches its GND pins 3 and 8, between the 12V parts.
X12 = 150.5                     # right edge of the 12V side, left of U1
z = pcbnew.ZONE(board)
z.SetLayer(pcbnew.B_Cu)
z.SetNetCode(net_items["/GND"].GetNetCode())
z.SetLocalClearance(MM(0.3))
z.SetMinThickness(MM(0.25))
sps = z.Outline(); sps.NewOutline()
for px, py in [(BX0, BY0), (BX1, BY0), (BX1, BY1), (X12, BY1),
               (X12, PY + 1.6), (134.5, PY + 1.6), (134.5, PY - 1.6), (X12, PY - 1.6),
               (X12, U1_Y + 2.5), (157.0, U1_Y + 2.5), (157.0, U1_Y - 3.81),
               (X12, U1_Y - 3.81), (X12, 108.5), (BX0, 108.5)]:
    sps.Append(MM(px), MM(py))
board.Add(z)

pcbnew.SaveBoard(PCB, board)
print(f"wrote {PCB}")

# ── net classes → .kicad_pro ─────────────────────────────────────────────────
try:
    pro = json.load(open(PRO))
except Exception:
    pro = {}
pro.setdefault("net_settings", {})
pro["net_settings"]["classes"] = [
    {"name": "Default", "clearance": 0.25, "track_width": 0.3,
     "via_diameter": 0.8, "via_drill": 0.4,
     "diff_pair_gap": 0.25, "diff_pair_width": 0.2,
     "microvia_diameter": 0.3, "microvia_drill": 0.1,
     "wire_width": 6, "bus_width": 12, "line_style": 0,
     "pcb_color": "rgba(0,0,0,0.000)", "schematic_color": "rgba(0,0,0,0.000)",
     "priority": 2147483647},
    {"name": "Power", "clearance": 0.3, "track_width": 0.6,
     "via_diameter": 1.0, "via_drill": 0.5,
     "diff_pair_gap": 0.25, "diff_pair_width": 0.2,
     "microvia_diameter": 0.3, "microvia_drill": 0.1,
     "wire_width": 6, "bus_width": 12, "line_style": 0,
     "pcb_color": "rgba(0,0,0,0.000)", "schematic_color": "rgba(0,0,0,0.000)",
     "priority": 0},
]
pro["net_settings"]["netclass_patterns"] = [
    {"netclass": "Power", "pattern": "/GND"},
    {"netclass": "Power", "pattern": "/+3V3"},
]
json.dump(pro, open(PRO, "w"), indent=2)
print("patched net classes into", PRO)
