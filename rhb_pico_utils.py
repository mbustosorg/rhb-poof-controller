from time import sleep

import machine
import network

try:
    import socket
except ImportError:
    import usocket as socket

try:
    import select
except ImportError:
    import uselect as select

try:
    import asyncio
except ImportError:
    import uasyncio as asyncio

display = None

MAX_DGRAM_SIZE = 6000
MINUS_GLYPH = 0x40
BLANK_GLYPH = 0x00
# One 4-digit HT16K33 backpack carries both readouts, two digits each, as
# (tens, ones) digit positions: pressure on the left, temperature on the right.
PRESSURE_DIGITS = (0, 1)
TEMPERATURE_DIGITS = (2, 3)
ALL_DIGITS = (0, 1, 2, 3)


def reboot():
    """Reset the machine"""
    sleep(5)
    machine.reset()


def set_glyphs(digits, glyph):
    """Fill the given digits with the same raw glyph.  The caller draws."""
    for digit in digits:
        display.set_glyph(glyph, digit)


def toggle_startup_display(count):
    """Indicate progress by chasing one segment around every digit"""
    if display:
        set_glyphs(ALL_DIGITS, 1 << (count % 6))
        display.draw()


def set_two_digits(digits, value):
    """Show `value' rounded to a whole number on one readout's two digits

    Senders broadcast floats, some of them unrounded, so round here rather
    than truncate. Only 0-99 fits in two digits: peg anything higher at 99
    and show a leading minus below 0.  The caller draws.
    """
    tens, ones = digits
    value = round(value)
    if value < -9:
        set_glyphs(digits, MINUS_GLYPH)
        return
    if value < 0:
        display.set_glyph(MINUS_GLYPH, tens)
        display.set_number(-value, ones)
        return
    if value > 99:
        value = 99
    display.set_number(value // 10, tens)
    display.set_number(value % 10, ones)


def wifi_connection(config):
    """Connect to the wifi.

    The rig is statically addressed, so the address comes from the config
    rather than DHCP.  It has to match, because every listener on the rig
    sends to config["IP"].
    """
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    # Power save lets the radio doze between beacons, which delays the ARP
    # reply the water heater's W5500 is waiting on and drops inbound UDP that
    # arrives while it is asleep.  This board is mains powered; keep it awake.
    try:
        wlan.config(pm=getattr(network.WLAN, "PM_NONE", 0xA11140))
    except Exception as e:
        print("Could not disable wifi power save:", e)
    if config.get("IP"):
        octets = config["IP"].split(".")
        gateway = config.get("GATEWAY") or ".".join(octets[:3] + ["1"])
        wlan.ifconfig(
            (
                config["IP"],
                config.get("NETMASK", "255.255.255.0"),
                gateway,
                config.get("DNS", gateway),
            )
        )
    while True:
        wait = 0
        wlan.connect(config["WIFI_SSID"], config["WIFI_PASSWORD"])
        while wait < 12:
            status = wlan.status()
            if status >= 3:
                break
            toggle_startup_display(wait)
            wait += 1
            sleep(1)
        if wlan.status() != 3:
            print(f'network connection failed, retrying {wlan.status()}')
        else:
            print('connected')
            status = wlan.ifconfig()
            print('ip = ' + status[0])
            break
    return wlan


def format_source(src):
    """Human readable `host:port' from a recvfrom() address

    lwip hands back an (ip, port) tuple, but fall back to the raw value so a
    packed sockaddr still logs something useful.
    """
    if isinstance(src, tuple):
        return f"{src[0]}:{src[1]}"
    return str(src)


async def run_server(saddr, port, handler):
    """Run the OSC Server asynchronously"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # Bind every interface.  Binding the configured address instead means
        # that if this device ever comes up on a different one, the socket is
        # listening where no packet can reach it and the failure is silent.
        ai = socket.getaddrinfo("0.0.0.0", port)[0]
        sock.setblocking(False)
        sock.bind(ai[-1])
        p = select.poll()
        p.register(sock, select.POLLIN)
        poll = getattr(p, "ipoll", p.poll)

        print(f"Listening for OSC messages on 0.0.0.0:{port} (configured {saddr})")
        while True:
            try:
                for res in poll(1):
                    if res[1] & (select.POLLERR | select.POLLHUP):
                        print("UDPServer.serve: unexpected socket error.")
                        break
                    elif res[1] & select.POLLIN:
                        buf, addr = sock.recvfrom(MAX_DGRAM_SIZE)
                        asyncio.create_task(handler(buf, addr))
                await asyncio.sleep(0.0)
            except Exception as e:
                print(f"Exception in run_server: {e}")
                break
        sock.close()
    except Exception as e:
        print(f"Exception in run_server top: {e}")
