Red Hot Beverly Poof Controller
===============================

`rhb-poof-controller` is the poof button panel for the Red Hot Beverly.  It runs
MicroPython on a Pico W at `192.168.1.15` and does three things:

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
  (`DEBOUNCE_MS`).
- Each pair shows `--` until its first value arrives, and again after 15 s
  without one, so it never shows a stale number.  A quiet water heater also
  stops the temperature blinking.
- Values are rounded; above 99 shows `99`, below 0 shows a leading minus.

Hardware
--------

[HARDWARE.md](HARDWARE.md) has the full circuit: board choice, power,
wiring and parts.

| Part | Pico W pin |
| --- | --- |
| Four digit display, HT16K33 backpack at I2C `0x70` | SDA GP16, SCL GP17 (I2C0) |
| Button optocoupler output | GP15, internal pull-up, low = pressed |
| Onboard LED | lit while the button is pressed |

The 12V button reaches GP15 only through a PC817 optocoupler, since the
Pico's GPIO is 3.3V only.

Pressure is on digits 0 and 1 and temperature on 2 and 3
(`PRESSURE_DIGITS`, `TEMPERATURE_DIGITS` in `rhb_pico_utils.py`); the colon
stays off.  The HT16K33's own blink would flash all four digits, so the
temperature pair is blinked in software at 1 Hz (`blink_loop` in `main.py`).

Configuration
-------------

`config_rhb.json` is gitignored; copy `config_rhb.json.example`.

| Key | Default | Meaning |
| --- | --- | --- |
| `WIFI_SSID`, `WIFI_PASSWORD` | | The rig WiFi |
| `IP` | | Static address.  The rig has no DHCP |
| `CLIENTS` | every rig listener | Who hears `/poof`.  `host` for port 8888, `host:port` otherwise |
| `POOF_PIN` | `15` | Button input GPIO |
| `DEBOUNCE_MS` | `20` | How long an edge must hold |
| `DISPLAY` | `112` (0x70) | I2C address of the display, in decimal since JSON has no hex |

Deploying
---------

Flash MicroPython for the Pico W, then copy these to the board with Thonny or
`mpremote cp`:

- `main.py`, `rhb_pico_utils.py`, `config_rhb.json`
- `uosc/` from [micropython-osc](https://github.com/SpotlightKid/micropython-osc)
- `ht16k33.mpy`, `ht16k33segment.mpy` from
  [HT16K33-Python](https://github.com/smittytone/HT16K33-Python)

Power save is turned off on the WiFi radio; without it the water heater's
W5500 cannot reach this board.

Testing
-------

`test_osc.py` sends random `/pressure`, `/temperature` and an alternating
`/water_heater` every 5 s and prints each `/poof` it hears.  Run it from a
machine whose address is in `CLIENTS`:

    python3 test_osc.py --ip 192.168.1.15
