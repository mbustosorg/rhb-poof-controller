Red Hot Beverly Poof Controller
===============================

The Red Hot Beverly's poof button panel: CircuitPython on a Waveshare
ESP32-S3-POE-ETH at `192.168.1.15`, wired and powered over PoE.

1. Sends `/poof 1.0` on press and `/poof 0.0` on release to every listener.
2. Shows accumulator pressure (`/pressure`) on the left two digits.
3. Shows water bath temperature (`/temperature`) on the right two digits,
   blinking while `/water_heater` is 1.

OSC
---

| Direction | Address | Value | Producer / consumers |
| --- | --- | --- | --- |
| out | `/poof` | `1.0` pressed, `0.0` released | Every address in `CLIENTS`, including the body display |
| in | `/pressure` | psi, float | rhb-sensor-monitor |
| in | `/temperature` | degrees F, float | rhb-water-heater |
| in | `/water_heater` | `1.0` heating, `0.0` off | rhb-water-heater |

All on UDP 8888, except the body display at `192.168.1.3:10002`.

- `/poof` is a level, not a count: the release is sent three times, 50 ms
  apart, in case one is lost.
- At boot it sends `/poof 0.0`; a button held at power up must be released
  first.
- Edges are debounced 20 ms (`DEBOUNCE_MS`) and scanned in the background, so
  one that arrives during a send is late, not lost.
- An unreachable listener is skipped for 2, 4, 8 ... up to 60 s, since each
  failed send blocks for up to 0.5 s.
- A readout shows `--` before its first value and after 15 s without one.
  Values are rounded; above 99 shows `99`, below 0 shows `--`.

Hardware
--------

See [HARDWARE.md](HARDWARE.md).

| Part | ESP32-S3-ETH pin |
| --- | --- |
| HT16K33 display, I2C `0x70` | SDA IO39, SCL IO38 |
| Button, through a PC817 | IO40, internal pull-up, low = pressed |
| Onboard RGB LED | IO21, red while pressed |
| W5500 Ethernet | IO9-IO14, on the board |

The temperature pair blinks in software (`blink_loop`), since the HT16K33's
blink would flash all four digits.

`rhb_utils.py` and the OSC receive path (`poll_osc`, `start_osc`) are
rhb-water-heater's, with its W5500 fixes.  Keep the two in step.

Configuration
-------------

`config_rhb.json` is gitignored; copy `config_rhb.json.example`.

| Key | Default | Meaning |
| --- | --- | --- |
| `IP` | | Static address; no DHCP on the rig |
| `CLIENTS` | every rig listener | Who hears `/poof`.  `host` for port 8888, `host:port` otherwise |
| `POOF_PIN` | `"IO40"` | Button input, a `board` pin name |
| `DEBOUNCE_MS` | `20` | How long an edge must hold |
| `DISPLAY` | `112` (0x70) | Display I2C address, decimal since JSON has no hex |

Deploying
---------

Flash CircuitPython for the Waveshare ESP32-S3-ETH, then copy to `CIRCUITPY`
over USB-C:

- `code.py`, `rhb_utils.py`, `config_rhb.json`
- Into `lib/`, from the Adafruit bundle: `adafruit_ht16k33`,
  `adafruit_bus_device`, `adafruit_wiznet5k`, `adafruit_ticks`, `asyncio`,
  and optionally `neopixel`
- `microosc`, from the Community bundle

Console: `/dev/cu.usbmodem<UID>` (`cu.*`, not `tty.*`).  The display flashes
`[[]]` until the link is up, then `-- --` until data arrives.

Testing
-------

`test_osc.py` sends random readings every 5 s and prints each `/poof`.  Run
it from an address in `CLIENTS`:

    python3 test_osc.py --ip 192.168.1.15
