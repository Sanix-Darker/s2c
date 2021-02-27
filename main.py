from app.utils.cam import start_cam
import gnupg
import argparse


if __name__ == "__main__":
    # The gnupg for encryption
    gpg = gnupg.GPG()


    # Initialize the arguments
    prs = argparse.ArgumentParser()
    prs.add_argument('-s', '--server',
            help='If you\'re the server, you can set the session name',
            type=str, default="-")

    prs = prs.parse_args()

    start_cam(gpg, prs.server)


