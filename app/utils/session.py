from hashlib import md5
from uuid import uuid4
from random import randint


def generate_key(prs: object):
    """
    This metho will just generate a secret key for
    AES encryption/decryption

    We check if the provided key is None before generate
    a new one

    """
    if prs.key is None:
        key = str(randint(0, 99999) + str(uuid4()))
        return "s2c_" + md5(key.encode()).hexdigest()[:4]
    else:
        return prs.key


def parse(prs: object):
    """
    This method will generate a new session

    """
    session = {
        "key":  generate_key(prs),
        "id": "",
        "status": ""
    }
    if prs.create is None and prs.join is None:
        session["status"] = "create"
        session["id"] = str(uuid4())
    elif prs.create is not None and prs.join is None:
        session["status"] = "create"
        session["id"] = prs.create
    elif prs.create is None and prs.join is not None:
        session["status"] = "join"
        session["id"] = prs.join

    return session


