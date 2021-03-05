# Just the encrypt/decrypt methods
# for kripta_aes
from s2c.modules.security.KriptaAES import KriptaAES


# We instantiate the class only once
kripta_aes = KriptaAES()


def encrypt_aes(key: str, msg: str) -> str:
    """
    This method will just encrypt a message from kripta_aes
    module

    """

    return kripta_aes.encrypt(msg, key).decode("utf-8")

def decrypt_aes(key: str, enc_msg: str) -> str:
    """
    This method will just decrypt an encrypted message from
    kripta_aes module

    """

    return kripta_aes.decrypt(enc_msg, key).decode("utf-8")

