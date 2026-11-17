"""
 Copyright (C) 2024 Mauricio Bustos (m@bustos.org)
 This program is free software: you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation, either version 3 of the License, or
 (at your option) any later version.
"""

import json
import time
import asyncio
import traceback

import board
import busio
import keypad

from adafruit_ht16k33 import segments

import microosc
import rhb_utils

OSC_PORT = 8888
# Every listener on the rig, as rhb-sensor-monitor broadcasts to, plus the
# monitor itself (the data logger).  A listener on another port is written
# "host:port" -- the body display, on rhbbody, listens on 10002.
DEFAULT_CLIENTS = [
    "192.168.1.3", "192.168.1.4", "192.168.1.5",
    "192.168.1.9", "192.168.1.10", "192.168.1.11", "192.168.1.13",
    "192.168.1.3:10002",
]

POOF_PIN = "IO40"
DEBOUNCE_MS = 20
# keypad scans this often; an edge counts once it holds for DEBOUNCE_MS of
# scans
SCAN_INTERVAL_MS = 5
# A lost release over UDP would leave a listener thinking the poofer is still
# held, so the release is sent again this many times, RELEASE_REPEAT apart.
# 0.0 is idempotent, so the copies are harmless.
RELEASE_REPEATS = 2
RELEASE_REPEAT = 0.05
# With nothing heard for this long, a readout shows -- rather than a stale value
STALE = 15
# While the heater is on the temperature digits blink at 1Hz: this long lit,
# this long dark
BLINK_HALF_PERIOD = 0.5
# Bounds a send to a listener that is not there.  The W5500 has to ARP for
# it first, and with the event loop stopped meanwhile.
SEND_TIMEOUT = 0.5
# A listener whose send failed is skipped for 2, 4, 8 ... seconds, up to
# this, so one that is switched off does not hold up every press for the rest
MAX_SKIP = 60
RX_TIMEOUT = 0.05
RX_BUFFER = 512

pool = None
osc_server = None
osc_client = None
endpoints = []
_fail_counts = {}
_skip_until = {}
last_heard = {"/pressure": None, "/temperature": None}
# The temperature digits 2 and 3 show, None for --.  It is held here so the
# blink can blank them and bring the same value back.
temperature = None
heater_on = False
blink_off = False


def show_temperature():
    """Draw the temperature on digits 2 and 3, blanked on the off beat

    They blink while the heater is on.  The HT16K33's own blink_rate cannot
    do that: it blinks the whole display, the pressure digits included.  So
    blink_loop flips blink_off and redraws, and this blanks just these two.
    """
    digits = rhb_utils.TEMPERATURE_DIGITS
    if heater_on and blink_off:
        rhb_utils.set_glyphs(digits, rhb_utils.BLANK_GLYPH)
    elif temperature is None:
        rhb_utils.set_glyphs(digits, rhb_utils.MINUS_GLYPH)
    else:
        rhb_utils.set_two_digits(temperature, *digits)


def set_heater(on):
    """Start or stop the temperature blink

    Only redraw on a change; /water_heater arrives every cycle.
    """
    global heater_on
    if on != heater_on:
        heater_on = on
        show_temperature()


# microosc dispatches on msg.addr.startswith(key), so each handler is also
# handed /pressure_fine and the like.  Match exactly -- /pressure_fine and
# /water_pressure are not what these digits show.

def pressure_handler(msg):
    """Accumulator pressure, owned by rhb-sensor-monitor"""
    if msg.addr != "/pressure":
        return
    rhb_utils.set_two_digits(msg.args[0], *rhb_utils.PRESSURE_DIGITS)
    last_heard["/pressure"] = time.monotonic()


def temperature_handler(msg):
    """Water bath temperature, owned by rhb-water-heater"""
    global temperature
    if msg.addr != "/temperature":
        return
    temperature = msg.args[0]
    show_temperature()
    last_heard["/temperature"] = time.monotonic()


def heater_handler(msg):
    if msg.addr != "/water_heater":
        return
    set_heater(bool(round(msg.args[0])))


dispatch_map = {
    "/pressure": pressure_handler,
    "/temperature": temperature_handler,
    "/water_heater": heater_handler,
}


def client_endpoints(entries):
    """Parse CLIENTS, "host" or "host:port", into (host, port) pairs"""
    result = []
    for entry in entries:
        host, _, port = entry.strip().partition(":")
        result.append((host.strip(), int(port) if port else OSC_PORT))
    return result


def send_poof(value):
    """Send /poof to every listener, skipping ones that have been failing

    Each send is isolated, so one unreachable listener cannot stop the rest
    from hearing the button.  A send to an absent host costs SEND_TIMEOUT
    with the event loop stopped, so a host that fails is skipped for a
    growing time rather than delaying every press after it.
    """
    if not osc_client:
        return
    msg = microosc.OscMsg("/poof", [float(value)], ["f"])
    now = time.monotonic()
    for endpoint in endpoints:
        if _skip_until.get(endpoint, 0) > now:
            continue
        osc_client.host, osc_client.port = endpoint
        try:
            osc_client.send(msg)
            _fail_counts[endpoint] = 0
        except Exception as e:
            n = _fail_counts.get(endpoint, 0) + 1
            _fail_counts[endpoint] = n
            skip = min(2 ** n, MAX_SKIP)
            _skip_until[endpoint] = now + skip
            print(f"Could not send /poof to {endpoint[0]}:{endpoint[1]} ({e}); skipping {skip}s")


def make_keys(pin):
    """The button, scanned and debounced in the background

    keypad keeps scanning while the event loop is stopped in a send, and
    queues the edges, so a press is never lost to a slow listener.  The
    button drives an optocoupler that pulls the pin to ground, so it reads
    low while pressed.
    """
    try:
        return keypad.Keys(
            (pin,), value_when_pressed=False, pull=True,
            interval=SCAN_INTERVAL_MS / 1000,
            debounce_threshold=max(1, DEBOUNCE_MS // SCAN_INTERVAL_MS),
        )
    except TypeError:
        # Older CircuitPython has no debounce_threshold.  Scanning every
        # DEBOUNCE_MS is the next best thing: an edge has to be there on a
        # scan to count.
        return keypad.Keys(
            (pin,), value_when_pressed=False, pull=True,
            interval=DEBOUNCE_MS / 1000,
        )


def set_led(on):
    if pixel is not None:
        pixel[0] = (255, 0, 0) if on else (0, 0, 0)


async def button_loop():
    """Send /poof 1.0 on press, 0.0 on release, the release three times"""
    event = keypad.Event()
    repeats_left = 0
    next_repeat = 0
    while True:
        if keys.events.get_into(event):
            pressed = event.pressed
            send_poof(1.0 if pressed else 0.0)
            set_led(pressed)
            print(f"{time.monotonic():.2f} /poof {'press' if pressed else 'release'}")
            repeats_left = 0 if pressed else RELEASE_REPEATS
            next_repeat = time.monotonic() + RELEASE_REPEAT
        elif repeats_left and time.monotonic() >= next_repeat:
            send_poof(0.0)
            repeats_left -= 1
            next_repeat = time.monotonic() + RELEASE_REPEAT
        await asyncio.sleep(0.002)


def start_osc():
    """Bring up OSC on a new connection.  See rhb-water-heater's connect_network."""
    global osc_server, osc_client, endpoints
    osc_server = microosc.OSCServer(pool, config["IP"], OSC_PORT, dispatch_map)
    # microosc hardcodes a 1ms timeout on the receive socket.  Every
    # _available() and read_udp() is an SPI transaction to the W5500, so a
    # real read cannot finish inside 1ms: it consumes the bytes and then
    # raises ETIMEDOUT, which poll() swallows as "no data".
    osc_server._sock.settimeout(RX_TIMEOUT)
    # microosc sizes its receive buffer at 128 bytes.  A datagram longer than
    # that can only be read in part, and the leftover desynchronises every
    # read after it.
    osc_server._buf = bytearray(RX_BUFFER)
    endpoints = client_endpoints(config.get("CLIENTS", DEFAULT_CLIENTS))
    # One socket for every listener.  The W5500 only has eight, and
    # sendto() takes the destination per call, so the host and port are
    # swapped before each send.  The timeout is set on the pool default so
    # the client socket picks it up, after the server socket above has
    # already been made with the blocking default.
    pool.setdefaulttimeout(SEND_TIMEOUT)
    osc_client = (
        microosc.OSCClient(pool, endpoints[0][0], endpoints[0][1])
        if endpoints
        else None
    )
    pool.setdefaulttimeout(None)
    # Start every listener from a known released state
    send_poof(0.0)
    # -- -- until data arrives
    rhb_utils.set_glyphs(rhb_utils.ALL_DIGITS, rhb_utils.MINUS_GLYPH)


async def network_loop():
    """Wait for the Ethernet link, then bring up OSC

    The button is read all along; a press before the link is up is simply
    not heard by anyone.
    """
    global pool
    count = 0
    while pool is None:
        pool = rhb_utils.ethernet_connection(config["IP"])
        if pool is None:
            rhb_utils.toggle_connecting_display(count)
            count += 1
            await asyncio.sleep(0.5)
    start_osc()


def poll_osc():
    """Read exactly one datagram and dispatch it.  Never raises.

    This is rhb-water-heater's poll_osc; its docstring has the reasons.  In
    short, osc_server.poll() and recvfrom_into can stop part way through a
    datagram and desynchronise every read after it, and read_udp asked for
    the whole buffer returns one datagram and stops on the boundary.
    """
    sock = osc_server._sock
    try:
        if sock._available() <= 0:
            return
        length, data = sock._interface.read_udp(sock._socknum, len(osc_server._buf))
    except Exception as exception:
        print("OSC read failed:", exception)
        return
    if not length:
        return
    osc_server._buf[:length] = data
    try:
        message = microosc.parse_osc_packet(osc_server._buf, length)
    except Exception as exception:
        # Drifted off a datagram boundary: throw away what is queued so the
        # next read starts clean.
        print(f"Discarding {length} byte OSC packet: {exception}")
        for _ in range(8):
            try:
                if sock._available() <= 0:
                    break
                sock._interface.read_udp(sock._socknum, len(osc_server._buf))
            except Exception:
                break
        return
    try:
        osc_server._dispatch(message)
    except Exception as exception:
        print(f"Handler for {message.addr} failed: {exception}")


async def osc_loop():
    while True:
        if osc_server:
            poll_osc()
        await asyncio.sleep(0)


async def stale_loop():
    """Blank a readout to -- once its sender has gone quiet"""
    global temperature, heater_on
    while True:
        now = time.monotonic()
        for address in ("/pressure", "/temperature"):
            heard = last_heard[address]
            if heard is not None and now - heard > STALE:
                last_heard[address] = None
                if address == "/pressure":
                    rhb_utils.set_glyphs(rhb_utils.PRESSURE_DIGITS, rhb_utils.MINUS_GLYPH)
                else:
                    # rhb-water-heater sends /water_heater too, so it has
                    # gone quiet as well: stop blinking a heater nobody reports
                    temperature = None
                    heater_on = False
                    show_temperature()
                print(f"{time.monotonic():.2f} {address} has gone quiet")
        await asyncio.sleep(1)


async def blink_loop():
    """Blink the temperature digits at 1Hz while the heater is on

    Nothing to undo when it goes off: set_heater redraws on the change, and
    show_temperature only blanks while it is on.
    """
    global blink_off
    while True:
        await asyncio.sleep(BLINK_HALF_PERIOD)
        blink_off = not blink_off
        if heater_on:
            show_temperature()


async def main_loop():
    try:
        print("Starting main loop...")
        await asyncio.gather(
            asyncio.create_task(button_loop()),
            asyncio.create_task(network_loop()),
            asyncio.create_task(osc_loop()),
            asyncio.create_task(stale_loop()),
            asyncio.create_task(blink_loop()),
        )
    except Exception as e:
        traceback.print_exception(type(e), e, e.__traceback__)
    rhb_utils.reboot()


# --- Hardware init ---

with open("config_rhb.json") as f:
    config = json.load(f)

DEBOUNCE_MS = config.get("DEBOUNCE_MS", DEBOUNCE_MS)
keys = make_keys(getattr(board, config.get("POOF_PIN", POOF_PIN)))
# Act only on edges seen from here on: a button already held at power up
# must be released and pressed again before it poofs.  Its press is in the
# queue after the first scans; dropping it leaves keypad knowing the button
# is down, so the next event is the release.
time.sleep(0.1)
keys.events.clear()

# The onboard WS2812 lights while the button is pressed, if the neopixel
# library is on the board
try:
    import neopixel
    pixel = neopixel.NeoPixel(getattr(board, "NEOPIXEL", board.IO21), 1, brightness=0.2)
    set_led(False)
except Exception as e:
    print("No status LED:", e)
    pixel = None

i2c = busio.I2C(board.IO38, board.IO39)  # SCL=IO38, SDA=IO39, as rhb-water-heater
rhb_utils.display = segments.Seg7x4(i2c, address=config.get("DISPLAY", 0x70))
rhb_utils.display.brightness = 0.5

try:
    asyncio.run(main_loop())
except Exception as e:
    traceback.print_exception(type(e), e, e.__traceback__)
rhb_utils.reboot()
