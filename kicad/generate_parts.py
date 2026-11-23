#!/usr/bin/env python3
"""
Write rhb_poof_controller.pretty/Waveshare_ESP32-S3-ETH.kicad_mod, the footprint for the
Waveshare ESP32-S3-ETH (and -POE-ETH) mounted top face up on 2 x 20 headers.

From Waveshare's dimension drawing (ESP32-S3-ETH-details-size.png):
  - board 72.80 x 21.00 mm
  - 2 x 20 headers, 2.54 mm pitch, rows 17.78 mm apart: Pico compatible
  - 19.87 mm from the pin 1 / pin 40 row to the RJ45 / USB-C end, so
    72.80 - 19.87 - 19 * 2.54 = 4.67 mm past pins 20 / 21 at the other end

Seen from the top face (the RJ45's) with the RJ45 end up, pin 1 is top left
and pin 40 top right, as on a Pico.  So the pads are a Pico's: pin 1 at the
origin, pins 1-20 down x = 0, pins 40-21 down x = 17.78, and the RJ45 end
toward -y.

Check against a real board before ordering PCBs.
"""
import os
import uuid

NAME   = "Waveshare_ESP32-S3-ETH"
PITCH  = 2.54
ROW    = 17.78
LENGTH = 72.80
WIDTH  = 21.00
END_TO_PIN1 = 19.87

X0 = ROW / 2 - WIDTH / 2                 # -1.61
X1 = ROW / 2 + WIDTH / 2                 # 19.39
Y0 = -END_TO_PIN1                        # the RJ45 / USB-C end
Y1 = Y0 + LENGTH

def U(): return str(uuid.uuid4())

def rect(layer, x0, y0, x1, y1, width):
    return (f'\t(fp_rect (start {x0:.3f} {y0:.3f}) (end {x1:.3f} {y1:.3f})\n'
            f'\t\t(stroke (width {width}) (type solid)) (fill no) (layer "{layer}") (uuid "{U()}"))')

def text(kind, s, x, y, layer, hide=False, size=1.0):
    return (f'\t(property "{kind}" "{s}" (at {x:.3f} {y:.3f} 0) (layer "{layer}")'
            + (' (hide yes)' if hide else '') +
            f' (uuid "{U()}")\n\t\t(effects (font (size {size} {size}) (thickness {size*0.15:.2f}))))')

def fp_text(s, x, y, layer, size=1.0):
    return (f'\t(fp_text user "{s}" (at {x:.3f} {y:.3f} 0) (layer "{layer}") (uuid "{U()}")\n'
            f'\t\t(effects (font (size {size} {size}) (thickness {size*0.15:.2f}))))')

def pad(num, x, y):
    shape = "roundrect" if num == 1 else "circle"
    extra = "\n\t\t(roundrect_rratio 0.125)" if num == 1 else ""
    return (f'\t(pad "{num}" thru_hole {shape} (at {x:.3f} {y:.3f}) (size 1.6 1.6) (drill 1)\n'
            f'\t\t(layers "*.Cu" "*.Mask") (remove_unused_layers no){extra} (uuid "{U()}"))')

items = [
    text("Reference", "REF**", ROW / 2, Y1 + 1.5, "F.SilkS"),
    text("Value", NAME, ROW / 2, Y1 + 3.0, "F.Fab"),
    text("Footprint", "", 0, 0, "F.Fab", hide=True),
    text("Datasheet", "https://docs.waveshare.com/ESP32-S3-ETH", 0, 0, "F.Fab", hide=True),
    rect("F.Fab", X0, Y0, X1, Y1, 0.1),
    rect("F.SilkS", X0 - 0.12, Y0 - 0.12, X1 + 0.12, Y1 + 0.12, 0.12),
    # The courtyard leaves a window between the header rows: the module sits
    # about 8.5 mm up on its sockets, so parts under 4.5 mm tall fit there.
    rect("F.CrtYd", X0 - 0.25, Y0 - 0.25, X1 + 0.25, Y1 + 0.25, 0.05),
    rect("F.CrtYd", 1.3, 0.0, ROW - 1.3, 19 * PITCH, 0.05),
    # The RJ45 and USB-C end, which must sit at the carrier's edge
    fp_text("RJ45 / USB-C", ROW / 2, Y0 + 3.0, "F.SilkS"),
    fp_text("${REFERENCE}", ROW / 2, ROW, "F.Fab"),
]
for n in range(1, 21):
    items.append(pad(n, 0.0, (n - 1) * PITCH))
for n in range(21, 41):
    items.append(pad(n, ROW, (40 - n) * PITCH))

body = (f'(footprint "{NAME}"\n'
        f'\t(version 20260206)\n'
        f'\t(generator "rhb_poof_controller_gen")\n'
        f'\t(layer "F.Cu")\n'
        f'\t(attr through_hole)\n'
        + "\n".join(items) + "\n)\n")

out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rhb_poof_controller.pretty")
os.makedirs(out_dir, exist_ok=True)
path = os.path.join(out_dir, NAME + ".kicad_mod")
with open(path, "w") as f:
    f.write(body)
print("Wrote", path)
