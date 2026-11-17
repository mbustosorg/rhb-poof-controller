Poof Controller Hardware
========================

The poof button panel is a Pico W, one optocoupler for the 12V button, and a
four digit HT16K33 display, on two separate supplies.

![Poof controller circuit](circuit.svg)

Board
-----

Use a **Raspberry Pi Pico W**.  A Pico 2 W also works with the code unchanged,
flashed with the RP2350 build of MicroPython.  A Pi Zero 2 W (as in
rhb-gauge-panel) is the wrong board here:

- The code is MicroPython (`machine.Pin`, `network.WLAN`, `Pin("LED")`).  A
  Zero runs Linux and CPython and would need it rewritten.
- The Pico is sending `/poof` about a second after power up; a Zero takes
  20-30 s to boot.
- The generator gets switched off without warning.  A Pico has no SD card to
  corrupt when that happens.
- The button loop polls every 2 ms with nothing else on the core, so the
  timing does not depend on what Linux is scheduling.

System
------

    120V generator
     |
     +-- 12V supply ---- fuse ---- poof button ---- opto LED (12V side)
     |                                                 .
     |                                     (isolated)  .
     |                                                 .
     +-- 5V USB supply ---- Pico W ---- opto transistor (3.3V side)
                             |  |
                             |  +-- I2C ---- HT16K33 four digit display
                             |
                             +-- WiFi "rhb", 192.168.1.15
                                   out: /poof        -> CLIENTS on :8888,
                                                        body display on :10002
                                   in:  /pressure    <- rhb-sensor-monitor
                                        /temperature <- rhb-water-heater
                                        /water_heater <- rhb-water-heater

The two supplies share no ground.  That is the point of the optocoupler: the
button's wiring runs out to the operator, and anything it picks up stays on
the 12V side.  Feeding the Pico from the 12V supply through a buck converter
would join the grounds and undo that.

Wiring
------

Pico W pin numbers are the physical pins, counting from the USB end.

### Power

| From | To |
| --- | --- |
| 5V USB supply (120V adapter) | Pico W micro USB |
| 12V supply + | Fuse, 250 mA, then the button |
| 12V supply - | PC817 pin 2 (cathode) |

### Button and optocoupler

    12V + --- fuse --- button --- 2.2k ---+--- PC817 1 (anode)
                       (N.O.)             |
                                       1N4148
                                     (cathode at pin 1)
                                          |
    12V - --------------------------------+--- PC817 2 (cathode)

    Pico GP15 (pin 20) ------------------------ PC817 4 (collector)
    Pico GND  (pin 18) ------------------------ PC817 3 (emitter)

| Part | Value | Why |
| --- | --- | --- |
| Button | momentary, normally open, rated for 12V | Closed while held |
| R1 | 2.2k, 1/4 W | (12V - 1.2V) / 2.2k = 4.9 mA through the LED, 5.4 mA at 13V.  The PC817 allows 50 mA |
| D1 | 1N4148 | Reverse across the LED.  The PC817 LED tolerates only 6V reversed, and a generator surge can ring the 12V line |
| U1 | PC817 | At 5 mA in and its worst case 50% CTR it sinks 2.5 mA; the pull-up needs well under 0.1 mA |
| Pull-up | Pico internal on GP15 | Enabled in `button_loop`.  Add an external 10k to 3V3 (pin 36) only if the opto sits far from the Pico |

Pressed, the transistor pulls GP15 low; released, the pull-up holds it high.
`button_loop` debounces 20 ms either way, so a spike shorter than that cannot
poof.

### Display

An Adafruit 0.56" four digit seven segment backpack (HT16K33), address `0x70`
with no address jumpers bridged.

| Backpack | Pico W |
| --- | --- |
| `+` (VCC) | 3V3 OUT, pin 36 |
| `-` (GND) | GND, pin 38 |
| `D` (SDA) | GP16, pin 21 |
| `C` (SCL) | GP17, pin 22 |
| `IO`, if present | 3V3 OUT, pin 36 |

Run it from 3V3, not 5V.  The backpack's pull-ups on `D` and `C` go to its
supply, and 5V on those lines would reach the Pico's 3.3V-only pins.  At
brightness 8 the display draws well within what the Pico's 3V3 regulator
supplies.

### Onboard

The Pico W's onboard LED lights while the button is pressed.

Parts
-----

| Qty | Part |
| --- | --- |
| 1 | Raspberry Pi Pico W (or Pico 2 W) |
| 1 | Adafruit 0.56" four digit seven segment display with I2C backpack |
| 1 | PC817 optocoupler |
| 1 | 2.2k resistor, 1/4 W |
| 1 | 1N4148 diode |
| 1 | Inline fuse holder and 250 mA fuse |
| 1 | Momentary N.O. pushbutton, 12V |
| 1 | 12V supply on the 120V system |
| 1 | 5V USB supply on the 120V system, and a micro USB cable |
