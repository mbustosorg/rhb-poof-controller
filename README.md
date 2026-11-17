Red Hot Beverly Poof Controller
===============================

`rhb-poof-controller` is the poof button panel for the Red Hot Beverly.  It runs
CircuitPython on a Waveshare ESP32-S3-POE-ETH at `192.168.1.15`, wired and
powered over PoE, and does three things:

1. **Reads the 12V poof button** and sends `/poof 1.0` on press and
   `/poof 0.0` on release to every listener on the rig.
2. **Shows accumulator pressure** from `/pressure` (rhb-sensor-monitor) on the
   left two digits of a four digit display.
3. **Shows water bath temperature** from `/temperature` (rhb-water-heater) on the
   right two digits, which blink while `/water_heater` is 1.

OSC
---

| Direction | Address | Value | Producer / consumers |
| --- | --- | --- | --- |
| out | `/poof` | `1.0` pressed, `0.0` released | This controller, to every address in `CLIENTS`, including the body display |
| in | `/pressure` | psi, float | rhb-sensor-monitor |
| in | `/temperature` | degrees F, float | rhb-water-heater |
| in | `/water_heater` | `1.0` heating, `0.0` off | rhb-water-heater |

Everything is on UDP port 8888, except the body display (rhb-body-display on
rhbbody), which listens on `192.168.1.3:10002` and shows a POOF while the
button is held.  Addresses are matched exactly, so `/pressure_fine` and
`/water_pressure` are ignored.

- The release is sent three times, 50 ms apart, so one lost datagram cannot
  leave a listener thinking the button is still held.  Treat `/poof` as a
  level, not a count.
- At boot it sends `/poof 0.0`.  A button already held at power up must be
  released and pressed again before it sends `1.0`.
- A press or release only counts once the input has held for 20 ms
  (`DEBOUNCE_MS`).  The button is scanned in the background (`keypad`), so
  an edge is still caught, and sent late rather than lost, while the event
  loop is stopped in a send.
- A listener that a send fails to reach is skipped for 2, 4, 8 ... s, up to
  60 s, so one that is switched off does not hold up the rest.  Each failed
  send costs up to 0.5 s while the W5500 tries to find it.
- Each pair shows `--` until its first value arrives, and again after 15 s
  without one, so it never shows a stale number.  A quiet water heater also
  stops the temperature blinking.
- Values are rounded; above 99 shows `99`, below 0 shows `--`.

Hardware
--------

[HARDWARE.md](HARDWARE.md) has the full circuit: board choice, power,
wiring and parts.

| Part | ESP32-S3-ETH pin |
| --- | --- |
| Four digit display, HT16K33 backpack at I2C `0x70` | SDA IO39, SCL IO38, as rhb-water-heater |
| Button optocoupler output | IO40, internal pull-up, low = pressed |
| Onboard RGB LED | red while the button is pressed |
| W5500 Ethernet | IO9-IO14, on the board |

The 12V button reaches IO40 only through a PC817 optocoupler, since the
ESP32's GPIO is 3.3V only.

Pressure is on digits 0 and 1 and temperature on 2 and 3
(`PRESSURE_DIGITS`, `TEMPERATURE_DIGITS` in `rhb_utils.py`); the colon
stays off.  The HT16K33's own blink would flash all four digits, so the
temperature pair is blinked in software at 1 Hz (`blink_loop` in `code.py`).

This is the water heater's board, and the Ethernet and display code is its
code: `rhb_utils.py` and the OSC receive path (`poll_osc`, `start_osc`)
carry its fixes for the W5500's socket timeout and receive buffer.  Keep the
two in step.

Configuration
-------------

`config_rhb.json` is gitignored; copy `config_rhb.json.example`.

| Key | Default | Meaning |
| --- | --- | --- |
| `IP` | | Static address.  The rig has no DHCP on the wired side |
| `CLIENTS` | every rig listener | Who hears `/poof`.  `host` for port 8888, `host:port` otherwise |
| `POOF_PIN` | `"IO40"` | Button input, a `board` pin name |
| `DEBOUNCE_MS` | `20` | How long an edge must hold |
| `DISPLAY` | `112` (0x70) | I2C address of the display, in decimal since JSON has no hex |

Deploying
---------

Flash CircuitPython for the Waveshare ESP32-S3-ETH, as for rhb-water-heater,
then copy these to the `CIRCUITPY` volume over the board's USB-C:

- `code.py`, `rhb_utils.py`, `config_rhb.json`
- From the Adafruit CircuitPython bundle, into `lib/`: `adafruit_ht16k33`,
  `adafruit_bus_device`, `adafruit_wiznet5k`, `adafruit_ticks`, `asyncio`,
  and `neopixel` for the status LED (optional)
- `microosc` from the Community bundle

The board soft reboots on write.  The console is on
`/dev/cu.usbmodem<UID>`; use `cu.*`, not `tty.*`.  It shows `[[]]` flashing
until the Ethernet link is up, then `-- --` until data arrives.

Testing
-------

`test_osc.py` sends random `/pressure`, `/temperature` and an alternating
`/water_heater` every 5 s and prints each `/poof` it hears.  Run it from a
machine whose address is in `CLIENTS`:

    python3 test_osc.py --ip 192.168.1.15
