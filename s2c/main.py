# main.py
# The main script for s2c
# parse input parameters and
import argparse
from s2c.client import Client
from hashlib import md5
from uuid import uuid4, uuid1
from random import randint

HOST = "127.0.0.1"
PORT = 2938

def generate_key(prs: object):
    """
    This metho will just generate a secret key for
    AES encryption/decryption

    We check if the provided key is None before generate
    a new one

    """
    if prs.key is not None:
        return prs.key

    key = str(randint(0, 99999)) + str(uuid4())
    return "s2c_" + md5(key.encode()).hexdigest()[:4]


def parse(prs: object):
    """
    This method will generate a new session

    """
    return {
        "session_id": str(uuid1()) if prs.session_id is None else prs.session_id,
        "session_key": generate_key(prs),
        "client_id": str(uuid4()) if prs.client_id is None else prs.client_id,
        "ip": prs.ip,
        "port": int(prs.port),
    }

if __name__ == "__main__":
    # Initialize the arguments
    prs = argparse.ArgumentParser()
    prs.add_argument(
        "-s",
        "--session_id",
        help="The sesion_id, if noting is provide,it will generate for you",
        type=str,
        default=None,
    )
    prs.add_argument(
        "-c",
        "--client_id",
        help="Your id or name in the session, if noting is provide,it will generate for you",
        type=str,
        default=None,
    )
    prs.add_argument(
        "-k",
        "--key",
        help="To provide the custom key for the AES encryption",
        type=str,
        default=None,
    )
    prs.add_argument(
        "-i",
        "--ip",
        help="The host of the server where websockets will transits",
        type=str,
        default=HOST,
    )
    prs.add_argument(
        "-p", "--port", help="The port of the host", type=int, default=PORT
    )

    # We start our client here
    client = Client(parse(prs.parse_args()))
