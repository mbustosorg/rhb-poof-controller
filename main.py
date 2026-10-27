import json
from time import time, ticks_ms, ticks_diff

from machine import Pin, I2C

try:
    import socket
except ImportError:
    import usocket as socket

try:
    import asyncio
except ImportError:
    import uasyncio as asyncio

from uosc.client import create_message
from uosc.server import split_oscstr, parse_message, parse_bundle

from ht16k33segment import HT16K33Segment

from rhb_pico_utils import run_server, wifi_connection
import rhb_pico_utils

OSC_PORT = 8888
# Every listener on the rig, as rhb-sensor-monitor broadcasts to, plus the
# monitor itself (the data logger).  A listener on another port is written
# "host:port" -- the body display, on rhbbody, listens on 10002.
DEFAULT_CLIENTS = [
    "192.168.1.3", "192.168.1.4", "192.168.1.5",
    "192.168.1.9", "192.168.1.10", "192.168.1.11", "192.168.1.13",
    "192.168.1.3:10002",
]

POOF_PIN = 15
DEBOUNCE_MS = 20
# A lost release over UDP would leave a listener thinking the poofer is still
# held, so the release is sent again this many times, RELEASE_REPEAT_MS apart.
# 0.0 is idempotent, so the copies are harmless.
RELEASE_REPEATS = 2
RELEASE_REPEAT_MS = 50
# With nothing heard for this long, a readout shows -- rather than a stale value
STALE_MS = 15000

pressure_display = None
temperature_display = None
last_heard = {"/pressure": None, "/temperature": None}
heater_on = False


def set_heater_blink(on):
    """Blink the temperature readout while the heater is on

    Only touch the chip on a change; /water_heater arrives every cycle.
    """
    global heater_on
    if on != heater_on:
        heater_on = on
        temperature_display.set_blink_rate(2 if on else 0)


async def handle_osc(data, src, dispatch=None, strict=False):
    try:
        head, _ = split_oscstr(data, 0)
        if head.startswith('/'):
            messages = [(-1, parse_message(data, strict))]
        elif head == '#bundle':
            messages = parse_bundle(data, strict)
        else:
            return
    except Exception as exc:
        if __debug__:
            print(f"Could not parse from {rhb_pico_utils.format_source(src)}: {exc} Data: {data}")
        return
    try:
        for timetag, (oscaddr, tags, args) in messages:

            # Match the exact addresses -- a substring test also catches
            # /water_pressure and /pressure_fine, which are not what these
            # digits show.
            if oscaddr == "/pressure":
                # Accumulator pressure, owned by rhb-sensor-monitor
                rhb_pico_utils.set_two_digits(pressure_display, args[0])
                pressure_display.draw()
                last_heard[oscaddr] = ticks_ms()
            elif oscaddr == "/temperature":
                # Water bath temperature, owned by rhb-water-heater
                rhb_pico_utils.set_two_digits(temperature_display, args[0])
                temperature_display.draw()
                last_heard[oscaddr] = ticks_ms()
            elif oscaddr == "/water_heater":
                set_heater_blink(bool(round(args[0])))
            else:
                continue
            if __debug__:
                print(f"{time()} OSC message from {rhb_pico_utils.format_source(src)} : {oscaddr} {tags} {args}")
            if dispatch:
                dispatch(timetag, (oscaddr, tags, args, src))
    except Exception as exc:
        print(f"Exception in OSC handler for {rhb_pico_utils.format_source(src)}: {exc}")


def client_address(entry):
    """Resolve a CLIENTS entry, "host" or "host:port", to a socket address"""
    host, _, port = entry.partition(":")
    return socket.getaddrinfo(host.strip(), int(port) if port else OSC_PORT)[0][-1]


def send_poof(sock, clients, value):
    """Send /poof to every listener

    Each send is isolated, so one unreachable listener cannot stop the rest
    from hearing the button.
    """
    msg = create_message("/poof", float(value))
    for client in clients:
        try:
            sock.sendto(msg, client)
        except Exception as e:
            print(f"Could not send /poof to {client}: {e}")


async def button_loop(clients):
    """Watch the 12V button and send /poof 1.0 on press, 0.0 on release

    The button drives an optocoupler that pulls the pin to ground, so the
    pin reads 0 while pressed.  An edge only counts once the pin has held
    its new level for DEBOUNCE_MS, so a spike on the 12V line cannot poof.
    """
    try:
        pin = Pin(config.get("POOF_PIN", POOF_PIN), Pin.IN, Pin.PULL_UP)
        debounce_ms = config.get("DEBOUNCE_MS", DEBOUNCE_MS)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # Start every listener from a known released state
        send_poof(sock, clients, 0.0)
        # Act only on edges seen after boot: a button already held at power
        # up must be released and pressed again before it poofs.
        stable = candidate = pin.value()
        since = ticks_ms()
        repeats_left = 0
        last_sent = ticks_ms()
        while True:
            now = ticks_ms()
            raw = pin.value()
            if raw != candidate:
                candidate = raw
                since = now
            elif candidate != stable and ticks_diff(now, since) >= debounce_ms:
                stable = candidate
                pressed = stable == 0
                send_poof(sock, clients, 1.0 if pressed else 0.0)
                rhb_pico_utils.led.value(pressed)
                print(f"{time()} /poof {'press' if pressed else 'release'}")
                repeats_left = 0 if pressed else RELEASE_REPEATS
                last_sent = now
            if repeats_left and ticks_diff(now, last_sent) >= RELEASE_REPEAT_MS:
                send_poof(sock, clients, 0.0)
                repeats_left -= 1
                last_sent = now
            await asyncio.sleep_ms(2)
    except Exception as e:
        print(f"Exception in button_loop: {e}")
        rhb_pico_utils.reboot()


async def stale_loop():
    """Blank a readout to -- once its sender has gone quiet"""
    while True:
        now = ticks_ms()
        for address, display in (("/pressure", pressure_display), ("/temperature", temperature_display)):
            heard = last_heard[address]
            if heard is not None and ticks_diff(now, heard) > STALE_MS:
                last_heard[address] = None
                rhb_pico_utils.show_glyphs(display, rhb_pico_utils.MINUS_GLYPH)
                if display is temperature_display:
                    set_heater_blink(False)
                print(f"{time()} {address} has gone quiet")
        await asyncio.sleep(1)


async def main_loop():
    """Main async loop"""
    try:
        print("Starting main loop...")
        clients = [
            client_address(entry)
            for entry in config.get("CLIENTS", DEFAULT_CLIENTS)
        ]
        asyncio.create_task(button_loop(clients))
        asyncio.create_task(stale_loop())
        await run_server(config["IP"], OSC_PORT, handle_osc)
    except Exception as e:
        print(f"Exception in main_loop: {e}")
    rhb_pico_utils.reboot()


if __name__ == "__main__":
    rhb_pico_utils.led = Pin("LED", Pin.OUT)
    rhb_pico_utils.led.off()
    with open("config_rhb.json") as f:
        config = json.load(f)

    i2c = I2C(0, scl=Pin(17), sda=Pin(16))
    devices = i2c.scan()
    if devices:
        for d in devices:
            print(f"I2C device found: {hex(d)}")
    pressure_display = HT16K33Segment(i2c, config.get("PRESSURE_DISPLAY", 0x70))
    temperature_display = HT16K33Segment(i2c, config.get("TEMPERATURE_DISPLAY", 0x71))
    rhb_pico_utils.displays = [pressure_display, temperature_display]
    for display in rhb_pico_utils.displays:
        display.set_brightness(8)
        display.set_blink_rate(0)

    try:
        rhb_pico_utils.toggle_startup_display(1)
        wlan = wifi_connection(config)
        for display in rhb_pico_utils.displays:
            rhb_pico_utils.show_glyphs(display, rhb_pico_utils.MINUS_GLYPH)  # -- until data arrives
        asyncio.run(main_loop())
    except Exception as e:
        print(f"{e}")
        rhb_pico_utils.reboot()
    rhb_pico_utils.reboot()
