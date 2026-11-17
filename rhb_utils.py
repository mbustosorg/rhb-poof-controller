"""
 Copyright (C) 2026 Mauricio Bustos (m@bustos.org)
 This program is free software: you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation, either version 3 of the License, or
 (at your option) any later version.

The Ethernet and display helpers are rhb-water-heater's, which runs on the
same board.  Keep the two in step.
"""

import time

import board
import busio
import digitalio
import microcontroller

import adafruit_wiznet5k.adafruit_wiznet5k as wiznet_module
from adafruit_wiznet5k.adafruit_wiznet5k_socketpool import SocketPool

display = None

MINUS_GLYPH = 0x40
BLANK_GLYPH = 0x00
# "[[]]" on a 7 segment display
CONNECTING_GLYPHS = (0x39, 0x39, 0x0F, 0x0F)
# One four digit HT16K33 carries both readouts, two digits each, as
# (tens, ones): pressure on the left, temperature on the right.
PRESSURE_DIGITS = (0, 1)
TEMPERATURE_DIGITS = (2, 3)
ALL_DIGITS = (0, 1, 2, 3)

_eth_spi = None
_eth_cs = None
_eth_rst = None
_eth = None


def reboot():
    time.sleep(5)
    microcontroller.reset()


def set_glyphs(digits, glyph):
    """Fill the given digits with the same raw glyph"""
    if display is None:
        return
    for digit in digits:
        display.set_digit_raw(digit, glyph)


def toggle_connecting_display(count):
    """Flash "[[]]" while an ethernet connection is being attempted."""
    if display is None:
        return
    for i in ALL_DIGITS:
        display.set_digit_raw(i, BLANK_GLYPH if count % 2 else CONNECTING_GLYPHS[i])


def set_two_digits(value, tens_digit, ones_digit):
    """Show `value' rounded across two digits.

    Senders broadcast floats, some of them unrounded, so round here rather
    than truncate.  Only 0-99 fits in two digits: peg anything higher at 99
    and show "--" below zero.
    """
    if display is None:
        return
    value = round(value)
    if value < 0:
        set_glyphs((tens_digit, ones_digit), MINUS_GLYPH)
        return
    if value > 99:
        value = 99
    display[tens_digit] = str(value // 10)
    display[ones_digit] = str(value % 10)


def _eth_hardware():
    """SPI and control pins can only be claimed once, so hold on to them."""
    global _eth_spi, _eth_cs, _eth_rst
    if _eth_spi is None:
        _eth_spi = busio.SPI(board.ETH_CLK, MOSI=board.ETH_MOSI, MISO=board.ETH_MISO)
        _eth_cs = digitalio.DigitalInOut(board.ETH_CS)
        _eth_rst = digitalio.DigitalInOut(board.ETH_RST)
    return _eth_spi, _eth_cs, _eth_rst


def _raw_ip(address):
    """"192.168.1.15" -> the four bytes the WIZnet registers want"""
    octets = [int(o) for o in address.split(".")]
    if len(octets) != 4 or any(o < 0 or o > 255 for o in octets):
        raise ValueError(f"Not an IPv4 address: {address}")
    return bytes(octets)


def ethernet_connection(address, subnet=None, gateway=None, dns=None):
    """One immediate attempt.  Returns a SocketPool, or None if not ready.

    Deliberately synchronous and non-blocking: the caller owns the retry loop
    and does the waiting.  An `await' in here would be awaited across a module
    boundary, which CircuitPython's asyncio does not support -- it raises
    "'generator' object has no attribute '__await__'".

    The rig is statically addressed, so the interface is configured from
    `address' rather than by DHCP.  There is no DHCP server on the wired side,
    and set_dhcp() blocks until it gets a lease that never comes.
    """
    global _eth
    try:
        if _eth is None:
            spi, cs, rst = _eth_hardware()
            _eth = wiznet_module.WIZNET5K(spi, cs, rst, is_dhcp=False)
        if not _eth.link_status:
            return None
        octets = address.split(".")
        _eth.ifconfig = (
            _raw_ip(address),
            _raw_ip(subnet or "255.255.255.0"),
            _raw_ip(gateway or ".".join(octets[:3] + ["1"])),
            _raw_ip(dns or gateway or ".".join(octets[:3] + ["1"])),
        )
        pool = SocketPool(_eth)
        print("Ethernet connected, ip =", _eth.pretty_ip(_eth.ip_address))
        return pool
    except Exception as e:
        print("Ethernet connection failed:", e)
        _eth = None
        return None
