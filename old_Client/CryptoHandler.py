import hashlib
import sys
import time
from base64 import b64encode, b64decode
from typing import Union

from Crypto.Cipher import PKCS1_OAEP, AES
from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
from Crypto.PublicKey.RSA import RsaKey
from Crypto.Random import get_random_bytes
from Crypto.Signature.pkcs1_15 import PKCS115_SigScheme

import ClientConfig
from Utils import Singleton


# CryptoHandler est un singleton : son instanciation n'est possible qu'une fois.


@Singleton
class CryptoHandler:
    str_public_key: str
    __private_key: RsaKey
    public_key: RsaKey

    def __init__(self):
        self.testvar = None
        self.__private_key, self.public_key = ClientConfig.load_keys()
        if not self.__private_key or not self.public_key:
            print("RSA generation...")
            self.generate_keys()
            self.__private_key, self.public_key = ClientConfig.load_keys()
        self.str_public_key = b64encode(self.public_key.export_key(format="DER")).decode("utf-8")
        self.identity = hashlib.sha1(b64encode(self.public_key.export_key(format="DER"))).hexdigest()

    def generate_keys(self) -> (RsaKey, RsaKey):
        key_length = 2048
        private_key: RsaKey = RSA.generate(key_length)
        public_key: RsaKey = private_key.publickey()
        print("New keys generated !")
        ClientConfig.store_keys(private_key, public_key)

    def to_rsa(self, key: str) -> RsaKey:
        return RSA.import_key(b64decode(key))

    def check_authenticator(self, key: RsaKey, authenticator: str) -> bool:
        msg = str(round(time.time()))[:-1]
        hash = SHA256.new(msg.encode())
        verifier = PKCS115_SigScheme(key)
        try:
            # noinspection PyTypeChecker
            verifier.verify(hash, b64decode(authenticator))
            return True
        except ValueError:
            return False

    def sign_rsa(self, message: str) -> str:
        msg_hash = SHA256.new(message.encode())
        signer = PKCS115_SigScheme(self.__private_key)
        # noinspection PyTypeChecker
        return b64encode(signer.sign(msg_hash)).decode("utf-8")

    def get_authenticator(self) -> str:
        return self.sign_rsa(str(round(time.time()))[:-1])

    def generate_session_key(self) -> bytes:
        return get_random_bytes(16)

    def encrypt_rsa(self, data: Union[str, bytes], public_key: RsaKey) -> bytes:
        if type(data) == str:
            data = data.encode()
        if sys.getsizeof(data) > 200:
            raise Exception("Trying to encrypt too large data with RSA. Limit is 200 bytes.")
        cipher_rsa = PKCS1_OAEP.new(public_key)
        encrypted_data = cipher_rsa.encrypt(data)
        return encrypted_data

    def decrypt_rsa(self, data: Union[str, bytes]) -> bytes:
        if type(data) == str:
            data = data.decode()
        cipher_rsa = PKCS1_OAEP.new(self.__private_key)
        return cipher_rsa.decrypt(data)

    def encrypt_aes(self, data: Union[str, bytes], session_key: bytes) -> bytes:
        if type(data) == str:
            data = data.encode()
        cipher = AES.new(session_key, AES.MODE_GCM)
        cipher_data, tag = cipher.encrypt_and_digest(data)
        nonce = cipher.nonce
        full_data = nonce + tag + cipher_data
        return full_data

    def decrypt_aes(self, data: bytes, session_key: bytes) -> bytes:
        nonce = data[:16]
        tag = data[16:32]
        cipher_data = data[32:]
        cipher = AES.new(session_key, AES.MODE_GCM, nonce=nonce)
        clear_data = cipher.decrypt_and_verify(cipher_data, tag)
        return clear_data

    # Chiffre data avec AES en générant une clé de session puis chiffre la clé de session avec la pubkey RSA spécifiée
    def encrypt_pgp(self, data: bytes, public_key: RsaKey) -> bytes:
        session_key = self.generate_session_key()
        encrypted_data = self.encrypt_aes(data, session_key)
        encrypted_session_key = self.encrypt_rsa(session_key, public_key)
        # noinspection PyTypeChecker
        signature = PKCS115_SigScheme(self.__private_key).sign(SHA256.new(data))

        return encrypted_session_key + signature + encrypted_data

    # Déchiffre la clé de session, puis les données, puis check la signature du hash des données
    def decrypt_pgp(self, full_data: bytes, public_key: RsaKey) -> bytes:
        encrypted_session_key = full_data[:256]
        signature = full_data[256:512]
        encrypted_data = full_data[512:]

        session_key = self.decrypt_rsa(encrypted_session_key)
        decrypted_data = self.decrypt_aes(encrypted_data, session_key)

        try:
            # noinspection PyTypeChecker
            PKCS115_SigScheme(public_key).verify(SHA256.new(decrypted_data), signature)
        except ValueError:
            print("WARNING Received data may be altered as fellow user signature does not match. Proceed with care.")

        return decrypted_data


if __name__ == '__main__':
    # noinspection PyCallByClass
    ch: CryptoHandler = Singleton.Instance(CryptoHandler)
