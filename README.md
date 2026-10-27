Red Hot Beverly Poof Controller
===============================

`rhb-poof-controller` is the poof button panel for the Red Hot Beverly.  It runs
MicroPython on a Pico W at `192.168.1.15` and does three things:

1. **Reads the 12V poof button** and sends `/poof 1.0` on press and
   `/poof 0.0` on release to every listener on the rig.
2. **Shows accumulator pressure** from `/pressure` (rhb-sensor-monitor) on a
   two digit readout.
3. **Shows water bath temperature** from `/temperature` (rhb-water-heater) on a
   second two digit readout, which blinks while `/water_heater` is 1.

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
- A readout shows `--` until its first value arrives, and again after 15 s
  without one, so it never shows a stale number.
- Values are rounded; above 99 shows `99`, below 0 shows a leading minus.

Hardware
--------

| Part | Pico W pin |
| --- | --- |
| Pressure readout, HT16K33 at I2C `0x70` | SDA GP16, SCL GP17 (I2C0) |
| Temperature readout, HT16K33 at I2C `0x71` (bridge A0) | same bus |
| Button optocoupler output | GP15, internal pull-up, low = pressed |
| Onboard LED | lit while the button is pressed |

The Pico's GPIO is 3.3V only, so the 12V button must not touch it.  Isolate
it with an optocoupler such as a PC817:

    12V --- button --- 2.2k --- PC817 anode (1)
                                PC817 cathode (2) --- 12V supply ground (-)
    GP15 ----------------------- PC817 collector (4)
    Pico GND ------------------- PC817 emitter (3)

The 12V comes from a mains supply on the generator's 120V system.  That is
about 5 mA through the LED at 12V, still fine if the supply is trimmed up to
13V.  A 1N4148 across the opto LED (reversed) protects it from a reverse spike
on the 12V line, such as when the generator surges.  Each HT16K33 runs from
the Pico's 3V3.

The readouts use digits 0 and 1 of each HT16K33 (`TENS_DIGIT`, `ONES_DIGIT`
in `rhb_pico_utils.py`); on a 4-digit backpack that is the left pair.

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
| `PRESSURE_DISPLAY`, `TEMPERATURE_DISPLAY` | `112` (0x70), `113` (0x71) | I2C addresses, in decimal since JSON has no hex |

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
