#!/usr/bin/env python3
"""
Place the poof controller board.  Run with KiCad's bundled python after
exporting the netlist from the schematic:

  /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 generate_pcb.py

Reads:  rhb_poof_controller.net
Writes: rhb_poof_controller.kicad_pcb (unrouted; see README.md for routing)

Layout, 2 layers, about 74 x 62 mm:
  - The Waveshare ESP32-S3-POE-ETH runs across the top, socketed top face
    up, its RJ45 / USB-C end 2 mm past the left edge so the cable and USB-C
    plug clear the carrier.
  - U1, the PC817, is below it by IO40 (pin 11), LED pins facing down, and
    J2, the display connector, beside it by IO39 and IO38 (pins 12, 14).
  - R1, D1 and J1, the 12V side, run along the bottom edge.  J1's wire entry
    faces off the board.
  - The ground pour on B.Cu covers only the board side, stopping at the
    PC817's middle, so the 12V side shares no copper with it.
  - M3 holes in the four corners.
"""
import json
import os
import re
import sys

NET    = "rhb_poof_controller.net"
PCB    = "rhb_poof_controller.kicad_pcb"
PRO    = "rhb_poof_controller.kicad_pro"
FPROOT = "/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints"
# This board's own footprints, the "rhb" library in fp-lib-table
LOCAL_LIBS = {"rhb": os.path.join(os.path.dirname(os.path.abspath(__file__)), "rhb.pretty")}

try:
    import pcbnew
except ImportError:
    sys.exit("ERROR: run with KiCad's bundled python3 (pcbnew not found).")

try:
    import wx; _APP = wx.App()
except Exception as _e:
    print("warning: wx init:", _e)

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
BY1 = 159.0
CORNER_R = 2.0
MH_INSET = 3.5

add("U2", PX, PY, rot=90)

# PC817 below IO40 (pin 11, x = PX + 10 * PITCH): LED pins 1-2 along the
# bottom, transistor pins 4-3 along the top
U1_Y = 141.0
add("U1", 152.0, U1_Y, rot=90)

# Display connector beside it, by IO39 and IO38 (pins 12 and 14), cable
# entry down
add("J2", 166.0, 132.5)

# 12V side along the bottom.  Rotated 180, J1's pin 2 is to the left of pin 1.
add("R1", 131.0, 142.5)
add("D1", 143.0, 147.0)
j1 = add("J1", 130.0, 153.5, rot=180)
# Its reference would sit off the bottom edge
j1.Reference().SetPosition(V(BX0 + 3.5, 146.6))

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
silk("+  -  D  C", 169.75, 138.0, 1.0)
silk("BTN", 130.0, 146.6, 1.0)
silk("12V-", 124.9, 146.6, 1.0)
silk("12V SIDE", 146.0, 155.5, 1.0)

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
# Stops at the PC817's middle, between its transistor and LED pins, so no
# ground copper runs under the 12V side.
ISOLATION_Y = U1_Y - 3.81
z = pcbnew.ZONE(board)
z.SetLayer(pcbnew.B_Cu)
z.SetNetCode(net_items["/GND"].GetNetCode())
z.SetLocalClearance(MM(0.3))
z.SetMinThickness(MM(0.25))
set_rect(z, BX0, BY0, BX1, ISOLATION_Y)
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
