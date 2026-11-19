Poof Controller Board
=====================

Two layer, 74 x 62 mm carrier for the circuit in [HARDWARE.md](../HARDWARE.md).

![Board, top](board.png)

| Ref | Part | Footprint |
| --- | --- | --- |
| U2 | Waveshare ESP32-S3-POE-ETH, on 2 x 20 headers | `rhb:Waveshare_ESP32-S3-ETH` |
| U1 | PC817 | `Package_DIP:DIP-4_W7.62mm` |
| R1 | 2.2k, 1/4 W | `Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal` |
| D1 | 1N4148 | `Diode_THT:D_DO-35_SOD27_P7.62mm_Horizontal` |
| J1 | 2 way screw terminal, 5.08 mm | `TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-2-5.08_1x02_P5.08mm_Horizontal` |
| J2 | JST-XH 4 pin, to the display | `Connector_JST:JST_XH_B4B-XH-A_1x04_P2.50mm_Vertical` |
| H1-H4 | M3 holes | `MountingHole:MountingHole_3.2mm_M3` |

- **U2** mounts top face up; its RJ45 / USB-C end overhangs the left edge by
  2 mm.
- **J1** takes the button wire, after the inline fuse at the supply, and the
  supply's negative.
- The bottom ground pour stops at the middle of the PC817, keeping the 12V
  side isolated.

The U2 footprint comes from Waveshare's dimension drawing.  **Check it against
a real board before ordering**: lay the module on a 1:1 print and see that
pin 1 lands on the square pad.

Regenerating
------------

Edit the scripts, not the KiCad files, then run from this directory:

    KICAD=/Applications/KiCad/KiCad.app/Contents
    python3 generate_footprint.py
    python3 generate_schematic.py
    $KICAD/MacOS/kicad-cli sch export netlist -o rhb_poof_controller.net rhb_poof_controller.kicad_sch
    $KICAD/Frameworks/Python.framework/Versions/Current/bin/python3 generate_pcb.py
    $KICAD/Frameworks/Python.framework/Versions/Current/bin/python3 route.py
    $KICAD/MacOS/kicad-cli pcb drc --schematic-parity -o drc.rpt rhb_poof_controller.kicad_pcb

`route.py` needs Java 17+ and `~/tools/freerouting-1.9.jar`.

DRC has two expected warnings: the mounting holes aren't in the schematic,
and U2's outline runs past the board edge.
