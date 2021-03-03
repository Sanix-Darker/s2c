# main.py
# The main script for s2c
# parse input parameters and
import argparse
from app.client import Client
from app.utils.session import parse
from app.settings import HOST, PORT



if __name__ == "__main__":
    # Initialize the arguments
    prs = argparse.ArgumentParser()
    prs.add_argument('-s', '--session_id',
            help='The sesion_id, if noting is provide,it will generate for you',
            type=str, default=None)
    prs.add_argument('-c', '--client_id',
            help='Your id or name in the session, if noting is provide,it will generate for you',
            type=str, default=None)
    prs.add_argument('-k', '--key',
            help='To provide the custom key for the AES encryption',
            type=str, default=None)
    prs.add_argument('-i', '--ip',
            help='The host of the server where websockets will transits',
            type=str, default=HOST)
    prs.add_argument('-p', '--port',
            help='The port of the host',
            type=int, default=PORT)

    # We start our client here
    client = Client(parse(prs.parse_args()))

