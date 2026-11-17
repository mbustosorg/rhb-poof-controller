#!/usr/bin/env python3
"""
Generate the KiCad schematic (.kicad_sch) and project (.kicad_pro) for the
poof controller board.  HARDWARE.md and circuit.svg describe the circuit.

  J1  2-way screw terminal: the button line, already through the inline fuse
      and the button, and the 12V supply's -
  R1  2.2k from the button line to the PC817 LED
  D1  1N4148 reversed across the LED
  U1  PC817; its transistor pulls GP15 low while the button is held
  U2  Waveshare ESP32-S3-POE-ETH, socketed, powered over PoE
  J2  JST-XH 4 pin to the HT16K33 backpack: +, -, D, C

The 12V side (BTN_12V, OPTO_A, GND_12V) shares nothing with the board side.

Connectivity is label-based; re-run to regenerate, then export the netlist:
  kicad-cli sch export netlist -o rhb_poof_controller.net rhb_poof_controller.kicad_sch
"""
import json
import os
import uuid

PROJECT   = "rhb_poof_controller"
ROOT_UUID = "00000000-0000-0000-0000-0000000000f0"  # stable root sheet uuid

def U(): return str(uuid.uuid4())

# --------------------------------------------------------------------------
# low-level emitters
# --------------------------------------------------------------------------
out = []
def emit(s): out.append(s)

def label(net, x, y, justify):
    emit(f'  (label "{net}" (at {x:.3f} {y:.3f} 0)\n'
         f'    (effects (font (size 1.27 1.27)) (justify {justify}))\n'
         f'    (uuid "{U()}"))')

def wire(x1, y1, x2, y2):
    emit(f'  (wire (pts (xy {x1:.3f} {y1:.3f}) (xy {x2:.3f} {y2:.3f}))\n'
         f'    (stroke (width 0) (type default)) (uuid "{U()}"))')

def text(s, x, y, size=1.8):
    esc = s.replace('"', '\\"')
    emit(f'  (text "{esc}" (at {x:.3f} {y:.3f} 0)\n'
         f'    (effects (font (size {size} {size})) (justify left)) (uuid "{U()}"))')

def no_connect(x, y):
    emit(f'  (no_connect (at {x:.3f} {y:.3f}) (uuid "{U()}"))')

# --------------------------------------------------------------------------
# symbol model (rectangular block with left / right pin lists)
# --------------------------------------------------------------------------
PIN_LEN = 5.08
PITCH   = 2.54

lib_symbols = []
symbol_pins = {}   # libname -> { pin_number_str: (tip_x_sym, tip_y_sym, side) }

def make_block(libname, left, right, hw=7.62, value="", ref="U"):
    base = libname.split(":")[-1]
    n    = max(len(left), len(right))
    top  = (n - 1) / 2 * PITCH
    half_h = top + PITCH
    offs   = {}

    body = (f'    (symbol "{base}_0_1"\n'
            f'      (rectangle (start {-hw:.3f} {half_h:.3f}) (end {hw:.3f} {-half_h:.3f})\n'
            f'        (stroke (width 0.254) (type default)) (fill (type background))))')
    pin_sx = []
    for side, pins, tip, angle in (("L", left, -(hw + PIN_LEN), 0),
                                   ("R", right, hw + PIN_LEN, 180)):
        for i, p in enumerate(pins):
            if p is None: continue
            num, name, etype = p
            sy = top - i * PITCH
            pin_sx.append(
                f'      (pin {etype} line (at {tip:.3f} {sy:.3f} {angle}) (length {PIN_LEN})\n'
                f'        (name "{name}" (effects (font (size 1.27 1.27))))\n'
                f'        (number "{num}" (effects (font (size 1.27 1.27)))))')
            offs[num] = (tip, sy, side)
    sym = (f'  (symbol "{libname}"\n'
           f'    (exclude_from_sim no) (in_bom yes) (on_board yes)\n'
           f'    (property "Reference" "{ref}" (at {-hw:.3f} {half_h+2.54:.3f} 0)\n'
           f'      (effects (font (size 1.27 1.27)) (justify left)))\n'
           f'    (property "Value" "{value}" (at {-hw:.3f} {-(half_h+2.54):.3f} 0)\n'
           f'      (effects (font (size 1.27 1.27)) (justify left)))\n'
           f'    (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))\n'
           f'    (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))\n'
           f'{body}\n'
           f'    (symbol "{base}_1_1"\n' + "\n".join(pin_sx) + "\n    )\n  )")
    lib_symbols.append(sym)
    symbol_pins[libname] = offs

def make_passive(libname, graphic, ref):
    """2-pin vertical passive.  Pin 1 tip at the top, pin 2 at the bottom.

    For the diode pin 1 is the cathode, matching KiCad's DO-35 footprint.
    """
    base = libname.split(":")[-1]
    TIP  = PIN_LEN + PITCH   # = 7.62
    if graphic == "R":
        gfx = ('      (rectangle (start -1.016 2.54) (end 1.016 -2.54)\n'
               '        (stroke (width 0.254) (type default)) (fill (type none)))')
    else:  # D, cathode bar at the top, pointing up from the anode
        gfx = ('      (polyline (pts (xy -1.27 -1.27) (xy 1.27 -1.27) (xy 0 1.27) (xy -1.27 -1.27))\n'
               '        (stroke (width 0.254) (type default)) (fill (type none)))\n'
               '      (polyline (pts (xy -1.27 1.27) (xy 1.27 1.27))\n'
               '        (stroke (width 0.254) (type default)) (fill (type none)))\n'
               '      (polyline (pts (xy 0 2.54) (xy 0 -2.54))\n'
               '        (stroke (width 0) (type default)) (fill (type none)))')
    names = ("K", "A") if graphic == "D" else ("~", "~")
    sym = (f'  (symbol "{libname}"\n'
           f'    (exclude_from_sim no) (in_bom yes) (on_board yes)\n'
           f'    (property "Reference" "{ref}" (at 2.54 0 90)\n'
           f'      (effects (font (size 1.27 1.27))))\n'
           f'    (property "Value" "" (at -2.54 0 90) (effects (font (size 1.27 1.27))))\n'
           f'    (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))\n'
           f'    (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))\n'
           f'    (symbol "{base}_0_1"\n{gfx}\n'
           f'      (pin passive line (at 0 {TIP:.3f} 270) (length {PIN_LEN})\n'
           f'        (name "{names[0]}" (effects (font (size 1.27 1.27))))\n'
           f'        (number "1" (effects (font (size 1.27 1.27)))))\n'
           f'      (pin passive line (at 0 {-TIP:.3f} 90) (length {PIN_LEN})\n'
           f'        (name "{names[1]}" (effects (font (size 1.27 1.27))))\n'
           f'        (number "2" (effects (font (size 1.27 1.27)))))\n'
           f'    )\n  )')
    lib_symbols.append(sym)
    symbol_pins[libname] = {"1": (0.0, TIP, "T"), "2": (0.0, -TIP, "B")}

# --------------------------------------------------------------------------
# placement
# --------------------------------------------------------------------------
def place(libname, ref, value, footprint, px, py, net_map, datasheet="~"):
    """Place a symbol; pins in net_map get a stub and a label, the rest a no-connect"""
    offs = symbol_pins[libname]
    # Snap to the 2.54 grid so every pin tip lands on the connection grid
    px, py = round(px / PITCH) * PITCH, round(py / PITCH) * PITCH
    emit(f'  (symbol (lib_id "{libname}") (at {px:.3f} {py:.3f} 0) (unit 1)\n'
         f'    (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no)\n'
         f'    (uuid "{U()}")\n'
         f'    (property "Reference" "{ref}" (at {px+4:.3f} {py-12:.3f} 0)\n'
         f'      (effects (font (size 1.27 1.27)) (justify left)))\n'
         f'    (property "Value" "{value}" (at {px+4:.3f} {py-9:.3f} 0)\n'
         f'      (effects (font (size 1.27 1.27)) (justify left)))\n'
         f'    (property "Footprint" "{footprint}" (at {px:.3f} {py:.3f} 0)\n'
         f'      (effects (font (size 1.27 1.27)) (hide yes)))\n'
         f'    (property "Datasheet" "{datasheet}" (at {px:.3f} {py:.3f} 0)\n'
         f'      (effects (font (size 1.27 1.27)) (hide yes)))\n'
         f'    (instances (project "{PROJECT}"\n'
         f'      (path "/{ROOT_UUID}" (reference "{ref}") (unit 1))))\n'
         f'  )')
    for num, (sx, sy, side) in offs.items():
        ax, ay = px + sx, py - sy   # schematic coords (Y flipped)
        net = net_map.get(num)
        if net is None:
            no_connect(ax, ay)
            continue
        if   side == "L": lx, ly, just = ax - PITCH, ay, "right"
        elif side == "R": lx, ly, just = ax + PITCH, ay, "left"
        elif side == "T": lx, ly, just = ax, ay - PITCH, "left"
        else:             lx, ly, just = ax, ay + PITCH, "left"
        wire(ax, ay, lx, ly)
        label(net, lx, ly, just)

# --------------------------------------------------------------------------
# library symbols
# --------------------------------------------------------------------------
def pin(n, name, t="passive"): return (str(n), name, t)

# Waveshare ESP32-S3-ETH, pins numbered as on its silkscreen: 1 and 40 at the
# RJ45 end, like a Pico's
make_block("rhb:ESP32-S3-ETH",
    left=[
        pin(1,  "IO20", "bidirectional"), pin(2,  "IO19", "bidirectional"),
        pin(3,  "GND",  "passive"),       pin(4,  "IO48", "bidirectional"),
        pin(5,  "IO47", "bidirectional"), pin(6,  "IO46", "bidirectional"),
        pin(7,  "IO45", "bidirectional"), pin(8,  "GND",  "passive"),
        pin(9,  "IO42", "bidirectional"), pin(10, "IO41", "bidirectional"),
        pin(11, "IO40", "bidirectional"), pin(12, "IO39", "bidirectional"),
        pin(13, "GND",  "passive"),       pin(14, "IO38", "bidirectional"),
        pin(15, "IO37", "bidirectional"), pin(16, "IO36", "bidirectional"),
        pin(17, "IO35", "bidirectional"), pin(18, "GND",  "passive"),
        pin(19, "IO34", "bidirectional"), pin(20, "IO33", "bidirectional"),
    ],
    right=[
        pin(40, "VBUS",    "power_out"),     pin(39, "VSYS",    "power_out"),
        pin(38, "GND",     "passive"),       pin(37, "3V3_EN",  "input"),
        pin(36, "3V3",     "power_out"),     pin(35, "IO21",    "bidirectional"),
        pin(34, "IO17",    "bidirectional"), pin(33, "GND",     "passive"),
        pin(32, "IO16",    "bidirectional"), pin(31, "IO18",    "bidirectional"),
        pin(30, "CHIP_UP", "input"),         pin(29, "IO15",    "bidirectional"),
        pin(28, "GND",     "passive"),       pin(27, "IO3",     "bidirectional"),
        pin(26, "IO2",     "bidirectional"), pin(25, "IO1",     "bidirectional"),
        pin(24, "IO0",     "bidirectional"), pin(23, "GND",     "passive"),
        pin(22, "IO44",    "bidirectional"), pin(21, "IO43",    "bidirectional"),
    ],
    hw=10.16, value="Waveshare ESP32-S3-POE-ETH")

make_block("rhb:PC817",
    left=[pin(1, "A"), pin(2, "K")],
    right=[pin(4, "C"), pin(3, "E")],
    hw=5.08, value="PC817")

make_block("rhb:Term2",
    left=[], right=[pin(1, "BTN"), pin(2, "12V-")],
    hw=5.08, value="Button, 12V-", ref="J")

make_block("rhb:Display4",
    left=[pin(1, "+"), pin(2, "-"), pin(3, "D"), pin(4, "C")],
    right=[], hw=5.08, value="HT16K33 display", ref="J")

make_passive("rhb:R", "R", "R")
make_passive("rhb:D", "D", "D")

# --------------------------------------------------------------------------
# schematic layout  (mm, Y down)
# --------------------------------------------------------------------------
text("RHB poof controller", 20, 15, size=3)
text("12V side: BTN_12V, OPTO_A, GND_12V share nothing with the board side", 20, 21, size=1.5)
text("Fuse (250 mA) and the poof button are off board, inline in the button wire", 20, 25, size=1.5)

text("=== 12V BUTTON INPUT ===", 20, 45)
place("rhb:Term2", "J1", "Button, 12V-",
      "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-2-5.08_1x02_P5.08mm_Horizontal",
      30, 65,
      {"1": "BTN_12V", "2": "GND_12V"})

place("rhb:R", "R1", "2.2k",
      "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal",
      60, 65,
      {"1": "BTN_12V", "2": "OPTO_A"})

place("rhb:D", "D1", "1N4148",
      "Diode_THT:D_DO-35_SOD27_P7.62mm_Horizontal",
      75, 65,
      {"1": "OPTO_A", "2": "GND_12V"})

text("=== OPTOCOUPLER ===", 95, 45)
place("rhb:PC817", "U1", "PC817",
      "Package_DIP:DIP-4_W7.62mm",
      110, 65,
      {"1": "OPTO_A", "2": "GND_12V", "4": "POOF", "3": "GND"})

text("=== ESP32-S3-POE-ETH ===", 150, 45)
text("Wired, powered over PoE; IO40 uses the internal pull-up", 150, 49, size=1.3)
place("rhb:ESP32-S3-ETH", "U2", "Waveshare ESP32-S3-POE-ETH",
      "rhb:Waveshare_ESP32-S3-ETH",
      185, 100,
      {
          "11": "POOF",
          "12": "SDA",
          "14": "SCL",
          "36": "+3V3",
          "3": "GND", "8": "GND", "13": "GND", "18": "GND",
          "23": "GND", "28": "GND", "33": "GND", "38": "GND",
      },
      datasheet="https://docs.waveshare.com/ESP32-S3-ETH")

text("=== DISPLAY ===", 240, 45)
text("HT16K33 backpack at 0x70, run from 3V3", 240, 49, size=1.3)
place("rhb:Display4", "J2", "HT16K33 display",
      "Connector_JST:JST_XH_B4B-XH-A_1x04_P2.50mm_Vertical",
      260, 65,
      {"1": "+3V3", "2": "GND", "3": "SDA", "4": "SCL"})

# --------------------------------------------------------------------------
# write
# --------------------------------------------------------------------------
def write_schematic(path):
    header = f'''\
(kicad_sch
  (version 20231120)
  (generator "rhb_poof_controller_gen")
  (uuid "{ROOT_UUID}")
  (paper "A4")
  (lib_symbols
{chr(10).join(lib_symbols)}
  )
'''
    with open(path, "w") as f:
        f.write(header + "\n".join(out) + "\n)\n")
    print(f"Wrote {path}")

def write_project(path):
    proj = {
        "board": {"design_settings": {}, "layer_presets": [], "viewports": []},
        "boards": [],
        "cvpcb": {"equivalence_files": []},
        "erc": {"erc_exclusions": [], "meta": {"version": 0}, "pin_map": [], "rule_severities": []},
        "libraries": {"pinned_footprint_libs": [], "pinned_symbol_libs": []},
        "meta": {"filename": f"{PROJECT}.kicad_pro", "version": 1},
        "net_settings": {"classes": [], "meta": {"version": 3}, "net_colors": None,
                         "netclass_assignments": None, "netclass_patterns": []},
        "pcbnew": {"last_paths": {}, "page_layout_descr_file": ""},
        "schematic": {"legacy_lib_dir": "", "legacy_lib_list": []},
        "sheets": [], "text_variables": {}
    }
    with open(path, "w") as f:
        json.dump(proj, f, indent=2)
    print(f"Wrote {path}")

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
write_schematic(os.path.join(OUT_DIR, f"{PROJECT}.kicad_sch"))
write_project(  os.path.join(OUT_DIR, f"{PROJECT}.kicad_pro"))
