Poof Controller Board
=====================

A two layer, 74 x 62 mm carrier for the circuit in
[HARDWARE.md](../HARDWARE.md): a Waveshare ESP32-S3-POE-ETH on headers, the
button's optocoupler, and connectors for the button and the display.

![Board, top](board.png)

The module shows as an outline; there is no 3D model for it.

| Ref | Part | Footprint |
| --- | --- | --- |
| U2 | Waveshare ESP32-S3-POE-ETH, on 2 x 20 headers | `rhb:Waveshare_ESP32-S3-ETH` |
| U1 | PC817 | `Package_DIP:DIP-4_W7.62mm` |
| R1 | 2.2k, 1/4 W | `Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal` |
| D1 | 1N4148 | `Diode_THT:D_DO-35_SOD27_P7.62mm_Horizontal` |
| J1 | 2 way screw terminal, 5.08 mm | `TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-2-5.08_1x02_P5.08mm_Horizontal` |
| J2 | JST-XH 4 pin, to the display | `Connector_JST:JST_XH_B4B-XH-A_1x04_P2.50mm_Vertical` |
| H1-H4 | M3 holes | `MountingHole:MountingHole_3.2mm_M3` |

- **U2** mounts top face up (the RJ45 and PoE module's side), on male headers
  pointing down into female headers on the carrier.  Its RJ45 / USB-C end
  hangs 2 mm past the left edge, so the cable and a USB-C plug for loading
  code both clear the carrier.  Power comes in over PoE; nothing else powers
  the board.
- **J1** `BTN` takes the button wire after the inline 250 mA fuse and the
  button, so it is 12V only while the button is held.  `12V-` is the 12V
  supply's negative.
- **J2** is `+ - D C`, left to right, matching the backpack's pins.
- **Isolation**: the ground pour, on the bottom layer, covers only the board
  side and stops at the middle of the PC817.  The 12V traces along the
  bottom share no copper with it.

The module's footprint, `rhb.pretty/Waveshare_ESP32-S3-ETH.kicad_mod`, is
built from Waveshare's dimension drawing (see `generate_footprint.py`).  The
headers are Pico compatible, so the pads are a Pico's.  **Check it against a
real board before ordering**: hold the module over a 1:1 print of the board
and see that its pins land on the pads with pin 1 where the square pad is.

Regenerating
------------

The footprint, schematic and board are generated; edit the scripts, not the
KiCad files, then run from this directory:

    KICAD=/Applications/KiCad/KiCad.app/Contents
    python3 generate_footprint.py
    python3 generate_schematic.py
    $KICAD/MacOS/kicad-cli sch export netlist -o rhb_poof_controller.net rhb_poof_controller.kicad_sch
    $KICAD/Frameworks/Python.framework/Versions/Current/bin/python3 generate_pcb.py
    $KICAD/Frameworks/Python.framework/Versions/Current/bin/python3 route.py
    $KICAD/MacOS/kicad-cli pcb drc --schematic-parity -o drc.rpt rhb_poof_controller.kicad_pcb

`route.py` needs Java 17+ and `~/tools/freerouting-1.9.jar`.  It autoroutes
with freerouting and fills the ground pour.

DRC reports no clearance or connection errors.  It does list two expected
warnings: the mounting holes are not in the schematic, and the module's
silkscreen outline runs past the left edge because the module overhangs it.
