Poof Controller Board
=====================

Two layer, 74 x 62 mm carrier for the circuit in [HARDWARE.md](../HARDWARE.md).
Parts: [bom.csv](bom.csv).

![Board, top](board.png)

![Copper: red top, blue bottom](board.svg)

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

Edit the scripts, not the KiCad files, then run `./build.sh`.  Routing needs
Java 17+ and `~/tools/freerouting-1.9.jar`.

Expected warnings:

| Warning | Why |
| --- | --- |
| `lib_symbol_issues` | Symbols live only in the schematic |
| `extra_footprint` | Mounting holes aren't in the schematic |
| `silk_edge_clearance` | U2's outline runs past the board edge |
