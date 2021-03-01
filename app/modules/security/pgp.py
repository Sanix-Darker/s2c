# note - gpg needs to be installed first:
# brew install gpg
# apt install gpg

# you may need to also:
# export GPG_TTY=$(tty)
from os import path as os_path, makedirs



def generate_pub_priv_keys(gpg: object, \
                            file_name: str, \
                            passphrase: str, \
                            share_file_name: str="./data/share"):
    """
    This method will use PGP through GnuPG to generate
    a public and private keys that will be use for encrypt
    and decrypt.

    Args:
        - gpg: The GnuPG instance to conserve the same context
        - file_name: the file name where keys will be stored
        - passphrase: The passphrase for encrypt/decrypt
    """
    # if data directory doesn't exist, let's create it
    if not os_path.exists("./data"):
        makedirs("data")

    # Generate key
    key = gpg.gen_key(gpg.gen_key_input(
        passphrase=passphrase,
        key_type="RSA",
        key_length=1024
    ))

    # Create ascii-readable versions of pub / private keys
    # Export it in a single file
    with open(file_name, 'w') as f:
        f.write(gpg.export_keys(key.fingerprint))
        f.write(gpg.export_keys(
            keyids=key.fingerprint,
            secret=True,
            passphrase=passphrase,
        ))

    # We save also the file that should be share for encryption from the peer
    with open(share_file_name, "w") as f:
        f.write(gpg.export_keys(key.fingerprint))


def import_keys(gpg: object, file_name: str) -> list:
    """
    To import presaved keys before encryption/decryption

    Args:
        - gpg: The GnuPG instance to conserve the same context
        - file_name: The path for the presaved keys
    """

    # import keys
    with open(file_name) as f:
        key_data = f.read()

    return [k["fingerprint"] for k in gpg.import_keys(key_data).results]



def encrypt(gpg: object, input_str: str, recipients: list) -> str:
    """
    This method will encrypt input ascii str

    Args:
        - gpg: The GnuPG instance to conserve the same context
        - input_str: The input ASCII text
        - recipients: The list of recipients
    """

    if len(input_str) > 2:
        # encrypt file
        enc = gpg.encrypt(input_str, recipients, always_trust=True)

        # We print an error if there is a problem
        if not enc.ok:
            print(enc.status)
            return ""

        return str(enc)

    return ""


def decrypt(gpg: object, input_str: str, passphrase: str) -> str:
    """
    This method will decrypt input encrypted ascii str

    Args:
        - gpg: The GnuPG instance to conserve the same context
        - input_str: The encrypted input ASCII text
        - passphrase: THe passphrase to decrypt
    """
    if len(input_str) > 2:
        # decrypt file
        dec = gpg.decrypt(input_str, passphrase=passphrase)

        # We print an error if there is a problem
        if not dec.ok:
            print(dec.status)
            return ""

        return str(dec)

    return ""


# How to test that locallyl
#if __name__ == "__main__":
#    import gnupg
#    import time
#    from os import path
#
#    # Create the gpg instance
#    gpg = gnupg.GPG()
#    key_path = "./data/k"
#    passphrase = "darker"
#
#    # We check if the key is present
#    # if not we generate a key pair
#    if not path.exists(key_path):
#        generate_pub_priv_keys(gpg, key_path, passphrase)
#
#    # We import keys pair from the file saved locally
#    ks = import_keys(gpg, key_path)
#
#    input_str = "Example of text !"
#    print("input_str : ", input_str)
#
#    enc = encrypt(gpg, input_str, recipients=ks)
#    print("enc : ", enc)
#
#    dec = decrypt(gpg, enc, passphrase)
#    print("dec : ", dec)
#
#
