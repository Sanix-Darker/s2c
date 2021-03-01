# Just the encrypt/decrypt methods
# for kripta_aes

def encrypt_aes(kripta_aes: object, key: str, msg: str) -> bytes:
    """
    This method will just encrypt a message from kripta_aes
    module

    """

    return kripta_aes.encrypt(msg, key)

def decrypt_aes(kripta_aes: object, key: str, enc_msg: str) -> bytes:
    """
    This method will just decrypt an encrypted message from
    kripta_aes module

    """

    return kripta_aes.decrypt(enc_msg, key)

