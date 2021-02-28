# The utils __init__ part
# where we are going to import everything

from cv2 import (
        resize,
        flip,
        cvtColor,
        COLOR_BGR2GRAY,
        VideoCapture
)


#from app.settings import (
#        version,
#        characters,
#        global_brightnesses,
#        client,
#        start,
#        frames,
#        indices,
#        key_path,
#        passphrase
#)


from app.utils.pgp import (
        import_keys,
        generate_pub_priv_keys,
        encrypt,
        decrypt
)

from os import (
        system,
        name as os_name,
        path as os_path
)

from bisect import bisect
from hashlib import md5,  sha256
import gnupg, time, socket, numpy as np

