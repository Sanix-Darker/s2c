# main.py
# The main script for s2c
# parse input parameters and
import argparse
from app.core import run
from app.modules.security.KriptaAES import KriptaAES
from app.utils.session import parse
from app.settings import HOST, PORT



if __name__ == "__main__":
    # We instantiate the class only once
    kripta_aes = KriptaAES()

    # Initialize the arguments
    prs = argparse.ArgumentParser()
    prs.add_argument('-c', '--create',
            help='This command is to create a new session',
            type=str, default=None)
    prs.add_argument('-j', '--join',
            help='To Join a new v2c session chat',
            type=str, default=None)
    prs.add_argument('-k', '--key',
            help='To provide a custom key for the AES encryption',
            type=str, default=None)
    prs.add_argument('-ho', '--host',
            help='The host of the server where websockets will transits',
            type=str, default=HOST)
    prs.add_argument('-p', '--port',
            help='The port of the host',
            type=str, default=PORT)


    run(kripta_aes, parse(prs.parse_args()))

