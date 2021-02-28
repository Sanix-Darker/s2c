from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2, HKDF
from Crypto.Hash import HMAC, SHA256, SHA512
from Crypto.Random import get_random_bytes
from Crypto.Util.Padding import pad, unpad

from base64 import b64encode, b64decode
from binascii import Error as Base64Error
from os.path import getsize as file_size
from re import sub as re_sub

#
#import time
#
#start = time.time()
#

class KriptaAES(object):
    '''
    Encrypts data and files using AES CBC/CFB - 128/192/256 bits.
    The encryption and authentication keys
    are derived from the supplied key/password using HKDF/PBKDF2.
    The key can be set either with `set_master_key` or with `random_key_gen`.
    Encrypted data format: salt[16] + iv[16] + ciphertext[n] + mac[32].
    Ciphertext authenticity is verified with HMAC SHA256.
    Requires pycryptodome https://pycryptodome.readthedocs.io
    :ivar key_iterations: int The number of PBKDF2 iterations.
    :ivar base64: bool Accepts ans returns base64 encoded data.
    :param mode: str Optional, the AES mode (cbc or cfb).
    :param size: int Optional, the key size (128, 192 or 256).
    :raises ValueError: if the mode or size is invalid.
    @author Sanix-darker
    '''
    def __init__(self, mode = 'CBC', size = 128):
        self._modes = {'CBC': AES.MODE_CBC, 'CFB': AES.MODE_CFB}
        self._sizes = (128, 192, 256)
        self._salt_len = 16
        self._iv_len = 16
        self._mac_len = 32
        self._mac_key_len = 32

        if mode.upper() not in self._modes:
            raise ValueError(mode + ' is not supported!')
        if size not in self._sizes:
            raise ValueError('Invalid key size!')
        self._mode = mode.upper()
        self._key_len = int(size / 8)
        self._master_key = None

        self.key_iterations = 20000
        self.base64 = True

    def encrypt(self, data, password = None):
        '''
        Encrypts data using the supplied password or a master key.
        The password is not required if a master key has been set -
        either with `random_key_gen` or with `set_master_key`.
        If a password is supplied, it will be used to create a key with PBKDF2.
        :param data: str or bytes or bytearray The plaintext.
        :param password: str or bytes or bytearray Optional, the password.
        :return: bytes Encrypted data (salt + iv + ciphertext + mac).
        '''
        try:
            data = self._to_bytes(data)
            if self._mode == 'CBC':
                data = pad(data, AES.block_size)

            salt = self._random_bytes(self._salt_len)
            iv = self._random_bytes(self._iv_len)

            aes_key, mac_key = self._keys(salt, password)
            cipher = self._cipher(aes_key, iv)
            ciphertext = cipher.encrypt(data)
            mac = self._sign(iv + ciphertext, mac_key)

            encrypted = salt + iv + ciphertext + mac
            if self.base64:
                encrypted = b64encode(encrypted)
            return encrypted
        except (TypeError, ValueError) as e:
            self._error_handler(e)

    def decrypt(self, data, password = None):
        '''
        Decrypts data using the supplied password or a master key.
        The password is not required if a master key has been set -
        either with `random_key_gen` or with `set_master_key`.
        If a password is supplied, it will be used to create a key with PBKDF2.
        :param data: str or bytes or bytearray The ciphertext.
        :param password: str or bytes or bytearray Optional, the password.
        :return: bytes Plaintext.
        '''
        try:
            data = self._to_bytes(data)
            data = b64decode(data) if self.base64 else data

            salt = data[:self._salt_len]
            iv = data[self._salt_len: self._salt_len + self._iv_len]
            ciphertext = data[self._salt_len + self._iv_len: -self._mac_len]
            mac = data[-self._mac_len:]

            aes_key, mac_key = self._keys(salt, password)
            self._verify(iv + ciphertext, mac, mac_key)

            cipher = self._cipher(aes_key, iv)
            plaintext = cipher.decrypt(ciphertext)
            if self._mode == 'CBC':
                plaintext = unpad(plaintext, AES.block_size)
            return plaintext
        except (TypeError, ValueError, Base64Error) as e:
            self._error_handler(e)

    def encrypt_file(self, path, password = None):
        '''
        Encrypts files using the supplied password or a master key.
        The password is not required if a master key has been set -
        either with `random_key_gen` or with `set_master_key`.
        If a password is supplied, it will be used to create a key with PBKDF2.
        The original file is not modified; a new encrypted file is created.
        :param path: str The file path.
        :param password: str or bytes Optional, the password.
        :return: str The new file path.
        '''
        try:
            salt = self._random_bytes(self._salt_len)
            iv = self._random_bytes(self._iv_len)

            aes_key, mac_key = self._keys(salt, password)
            cipher = self._cipher(aes_key, iv)
            hmac = HMAC.new(mac_key, digestmod = SHA256)
            new_path = path + '.enc'

            with open(new_path, 'wb') as f:
                f.write(salt + iv)
                hmac.update(iv)

                for chunk, is_last in self._file_chunks(path):
                    if self._mode == 'CBC' and is_last:
                        chunk = pad(chunk, AES.block_size)
                    data = cipher.encrypt(chunk)
                    f.write(data)
                    hmac.update(data)

                f.write(hmac.digest())
            return new_path
        except (TypeError, ValueError, IOError) as e:
            self._error_handler(e)

    def decrypt_file(self, path, password = None):
        '''
        Decrypts files using the supplied password or a master key.
        The password is not required if a master key has been set -
        either with `random_key_gen` or with `set_master_key`.
        If a password is supplied, it will be used to create a key with PBKDF2.
        The original file is not modified; a new decrypted file is created.
        :param path: str The file path.
        :param password: str or bytes Optional, the password.
        :return: str The new file path.
        '''
        try:
            with open(path, 'rb') as f:
                salt = f.read(self._salt_len)
                iv = f.read(self._iv_len)
                f.seek(file_size(path) - self._mac_len)
                mac = f.read(self._mac_len)

            aes_key, mac_key = self._keys(salt, password)
            self._verify_file(path, mac, mac_key)
            cipher = self._cipher(aes_key, iv)
            new_path = re_sub(r'\.enc$', '.dec', path)

            with open(new_path, 'wb') as f:
                chunks = self._file_chunks(
                    path,
                    self._salt_len + self._iv_len,
                    self._mac_len
                )
                for chunk, is_last in chunks:
                    data = cipher.decrypt(chunk)

                    if self._mode == 'CBC' and is_last:
                        data = unpad(data, AES.block_size)
                    f.write(data)
            return new_path
        except (TypeError, ValueError, IOError) as e:
            self._error_handler(e)

    def set_master_key(self, key, raw = False):
        '''
        Sets a new master key.
        This key will be used to create the encryption and authentication keys.
        :param key: str or bytes or bytearray The new master key.
        :param encoded: bool Optional, expexts raw bytes; not base64-encoded.
        '''
        try:
            if not raw:
                key = b64decode(key)
            self._master_key = self._to_bytes(key)
        except (TypeError, Base64Error) as e:
            self._error_handler(e)

    def get_master_key(self, raw = False):
        '''
        Returns the master key (or `None` if the key is not set).
        :param raw: bool Optional, returns raw bytes; not base64-encoded.
        :return: bytes The master key.
        '''
        if self._master_key is None:
            self._error_handler(ValueError('The key is not set!'))
        elif not raw:
            return b64encode(self._master_key)
        else:
            return self._master_key

    def random_key_gen(self, key_len = 32, raw = False):
        '''
        Generates a new random key.
        This key will be used to create the encryption and authentication keys.
        :param raw: bool Optional, returns raw bytes; not base64-encoded.
        :return: bytes The new master key.
        '''
        self._master_key = self._random_bytes(key_len)
        if not raw:
            return b64encode(self._master_key)
        return self._master_key

    def _keys(self, salt, password):
        '''
        Derives encryption and authentication keys from a key or password.
        If the password is not null, it will be used to create the keys.
        :raises ValueError: if neither the key or password is set.
        '''
        if password is not None:
            dkey = PBKDF2(
                password,
                salt,
                self._key_len + self._mac_key_len,
                self.key_iterations,
                hmac_hash_module = SHA512
            )
        elif self._master_key is not None:
            dkey = HKDF(
                self._master_key,
                self._key_len + self._mac_key_len,
                salt, SHA256
            )
        else:
            raise ValueError('No password or key specified!')
        return (dkey[:self._key_len], dkey[self._key_len:])

    def _random_bytes(self, size):
        '''
        Creates random bytes; used for IV, salt and key generation.
        '''
        return get_random_bytes(size)

    def _cipher(self, key, iv):
        '''
        Creates an AES object; used for encryption / decryption.
        '''
        return AES.new(key, self._modes[self._mode], IV = iv)

    def _sign(self, ciphertext, key):
        '''
        Computes the MAC of ciphertext; used for authentication.
        '''
        hmac = HMAC.new(key, ciphertext, digestmod = SHA256)
        return hmac.digest()

    def _sign_file(self, path, key):
        '''
        Computes the MAC of ciphertext; used for authentication.
        '''
        hmac = HMAC.new(key, digestmod = SHA256)
        for data, _ in self._file_chunks(path, self._salt_len):
            hmac.update(data)
        return hmac.digest()

    def _verify(self, data, mac, key):
        '''
        Verifies the authenticity of ciphertext.
        :raises ValueError: if the MAC is invalid.
        '''
        hmac = HMAC.new(key, data, digestmod = SHA256)
        hmac.verify(mac)

    def _verify_file(self, path, mac, key):
        '''
        Verifies the authenticity of ciphertext.
        :raises ValueError: if the MAC is invalid.
        '''
        hmac = HMAC.new(key, digestmod = SHA256)
        beg, end = self._salt_len, self._mac_len

        for chunk, _ in self._file_chunks(path, beg, end):
            hmac.update(chunk)
        hmac.verify(mac)

    def _error_handler(self, exception):
        '''
        Handles exceptions (prints the exception by default).
        '''
        print(exception)

    def _file_chunks(self, path, beg = 0, end = 0):
        '''
        A generator that reads a file and yields chunks of data.
        The chunk size should be a multiple of 16 in CBC mode.
        '''
        size = 1024
        end = file_size(path) - end

        with open(path, 'rb') as f:
            pos = (len(f.read(beg)))
            while pos < end:
                size = size if end - pos > size else end - pos
                data = f.read(size)
                pos += len(data)

                yield (data, pos == end)

    def _to_bytes(self, data, encoding = 'utf-8'):
        '''
        Converts unicode strings and byte arrays to byte strings.
        '''
        if hasattr(data, 'encode'):
            data = bytes(data, encoding)
        if type(data) is bytearray:
            data = bytes(data)
        return data

#
#k = KriptaAES()
#
#print("\nWELCOME TO KRIPTA-AES-PYTHON")
#message = """
#
#----------------------------------------------------------------------
#[+] s2c v0.0.1 | Client : 336d5ebc5436534e61d16e63ddfca327
#----------------------------------------------------------------------
#?clLxwpE&&&&HHHHH&&H&&&EdEpddddAApAppZGGUUUXXXXaaaaaaahShhhhhh444V3VVV
#?cL7thpE&&&H0HH&HHH&&EEdAEddApdAAAppZpZUUUUUXXXaaaaaaaSShhhhhhhh4V4V4h
#cl7YCU&HH0$0000H0H&&&&EAEEAdddddEdddAAApppGGUUUXXXaaaaaaaaaShShhhhhhhh
#L7YtwA&$0$0$$D$00H0&&&&E&&EE&E&EEE&EdddAAppppGUUUUUUXXXaaaaaaSaSShhhhh
#LYtChHDD$DDD$DD$$$$$HHHH&&&&&H&&HH0H&EEEEddppppppUUUUXaaXaaaaaaaaaaaaa
#jttoG$8D88888888DDDDD0$0HHH&H&&HH0HH&&&&&EEddAAppGGUGUUUUUUXXXXXaaaaXa
#t%{308888888888888DDDDD$$$$000$0$0$$H0HHH&&&&EdEdppppGUUGUUUUUUUUUUXUU
#tf{a8#####Q#888888888888DD$DDDDDDDDDD$$$HS*:+.+?AdApppppZZGZUUGUGUUGUG
#tCypQgggggQQ#g#QQ88QQ888888888888888DD$L.`      .)?pApZpppppZZZZZZZUZp
#tfIHggggRggRg#ggggg####88QQ8888888888D:::_;:.      ^UAAppppAdAAApppppp
#tfh8gggRRRRRRgggRggggg#QQ#8Q#Q8Q8##8h+++___;:,.    .G&EEEdAddddddpdppA
#%{ZggRRRRRRRRRggRggggg######QQ##Q#V8=__=;+_:::...   ?&&EE&EEEEEEAddddd
#tw$RRRRRRRRRRRRRRRggggg#ggg##gg#8+=***^:,.._^.....  .p&&&&E&&&&&&&&EEd
#%hQRRRRRRRRRRRRRRRRRRggggg#gg#g#&_*)?*:...!^::..... ^&H&HH0HH&&&H&&&&E
#fGgRRRRRRRRRRRRRRRgRggggggggQgggQ)*)<___:.. `.`...._$$$000H&&E&&E&&E&E
#y&RRRRRRRRRRRRRRRgggRgRgggg###g#p**)=^)_+:``...`~:lDD$$$0&EEdppdddddAd
#38RRRRRRRRRRRRgRRRRggggggggg#Qg8<**_;:^;_.`. .`._$8DDD0&EpGUXXUUUUUGGZ
#agRRRRRRRRRRRRRRRRgggggggg##g88x*=**:;:. . ....+F88DD$EpUaShh44hhSaSaa
#pgRRRRRRRRRRRRRRRRRgggg######Q$)**++=:.` ```..:h888D$EpXhVIyyoyoyywI3h
#$d0$&$EARRZRRyRRRgRg{Qg#gggQg#?\==\:~:   ``.~_D888DD&ZXhIy{f%nCCCCffoo
#gRNBBNU0NNBNgyNQ8888n##Q#ggQQc)<=::,.    .*$88888DDHpUhIy{%%%%tCfCCfff
#8gRRRghRRgggU0Wg888$&QQ888$%?)**+^.`    `a$8Q888DH&pa4Iy{%%t%%nn%nnnnf
#ggRRRRRRRRRRRWRRRRRgg88X?))?))*=_,.``   ..^G8D$&dZXa3wy{ntttttn%%%nnCC
#gRRRRRRRRRRRRRRRRRg83)*)))))?+))+....` `...~:+XUah3wy{fnttxt%tttt%tt%%
#RRRRRRRRRRRRRRR$c<*****))))*_=*)+:^:~....,~:~::;){fntxxxxxttt%x  7 FPS
#----------------------------------------------------------------------
#23f498becb757ea1645685cef580e94282587f80c5718209cbbe8aa7332050d3 |1774
#----------------------------------------------------------------------
#
#
#"""
#secret_key = "secret-code-password"
#print("-----------------------------------------------------")
#print("Message : ", message)
#print("-----------------------------------------------------")
#print("secret_key : ", secret_key)
#print("-----------------------------------------------------")
#encrypted_msg = k.encrypt(message, secret_key)
#print("Encrypted-Message : ", encrypted_msg.decode('utf-8'))
#print("-----------------------------------------------------")
#print("Decrypted-Message : ", k.decrypt(encrypted_msg, secret_key).decode('utf-8'))
#print("-----------------------------------------------------")
#
#
#print("len message : ", len(message))
#print("len secret-key : ", len(secret_key))
#print("len encrypted_msg : ", len(encrypted_msg.decode('utf-8')))
#print("len bytes encrypted_msg : ", len(encrypted_msg))
#print("elapsed time : ", time.time() - start)
#
