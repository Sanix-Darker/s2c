from hashlib import md5
from uuid import uuid4, uuid1
from random import randint



def generate_key(prs: object):
    """
    This metho will just generate a secret key for
    AES encryption/decryption

    We check if the provided key is None before generate
    a new one

    """
    if prs.key is None:
        key = str(randint(0, 99999)) + str(uuid4())
        return "s2c_" + md5(key.encode()).hexdigest()[:4]
    else:
        return prs.key


def parse(prs: object):
    """
    This method will generate a new session

    """
    return {
        "session_id": str(uuid1()) if prs.session_id is None else prs.session_id,
        "session_key":  generate_key(prs),
        "client_id": str(uuid4()) if prs.client_id is None else prs.client_id,
        "ip": prs.ip,
        "port": int(prs.port)
    }

