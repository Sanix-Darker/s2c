import gnupg
import argparse

from app.core import (
    run
)



if __name__ == "__main__":
    # The gnupg for encryption
    gpg = gnupg.GPG()

    # Initialize the arguments
    prs = argparse.ArgumentParser()
    prs.add_argument('-s', '--server',
            help='If you\'re the server, you can set the session name',
            type=str, default="-")

    prs = prs.parse_args()

    run(gpg, prs.server)

