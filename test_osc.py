"""Bench test: feed the readouts and print every /poof the controller sends

Run from a machine on the rig network with python-osc installed.  The
controller must list this machine's address in CLIENTS to be heard.
"""
import argparse
import asyncio
import random

from pythonosc import udp_client
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import AsyncIOOSCUDPServer


def print_poof(address, *args):
    print(f"{address} {args}")


async def feed(client):
    heater = 0.0
    while True:
        client.send_message("/pressure", float(random.randint(0, 99)))
        client.send_message("/temperature", float(random.randint(60, 105)))
        heater = 1.0 - heater
        client.send_message("/water_heater", heater)
        await asyncio.sleep(5)


async def main(args):
    dispatcher = Dispatcher()
    dispatcher.map("/poof", print_poof)
    server = AsyncIOOSCUDPServer(("0.0.0.0", args.port), dispatcher, asyncio.get_event_loop())
    transport, _ = await server.create_serve_endpoint()
    try:
        await feed(udp_client.SimpleUDPClient(args.ip, args.port))
    finally:
        transport.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ip", default="192.168.1.15", help="The ip of the poof controller")
    parser.add_argument("--port", type=int, default=8888, help="The OSC port")
    asyncio.run(main(parser.parse_args()))
