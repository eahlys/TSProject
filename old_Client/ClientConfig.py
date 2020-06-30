import os
from typing import *

from Crypto.PublicKey import RSA
from Crypto.PublicKey.RSA import RsaKey

"""
ClientConfig rassemble les fonctions de gestion de la configuration du Client

"""

if not os.path.exists(".config"):
    os.mkdir(".config")


def load_keys() -> (RsaKey, RsaKey):
    try:
        priv_file: BinaryIO = open(".config/rsa_private.key", "rb")
        pub_file: BinaryIO = open(".config/rsa_public.key", "rb")
        privkey: RsaKey = RSA.import_key(priv_file.read())
        pubkey: RsaKey = RSA.import_key(pub_file.read())
        priv_file.close()
        pub_file.close()
        return privkey, pubkey
    except Exception:
        return None, None


def store_keys(privkey: RsaKey, pubkey: RsaKey):
    try:
        priv_file: BinaryIO = open(".config/rsa_private.key", "wb")
        pub_file: BinaryIO = open(".config/rsa_public.key", "wb")
        priv_file.write(privkey.export_key())
        pub_file.write(pubkey.export_key())
        priv_file.close()
        pub_file.close()
    except Exception as e:
        print(e)
        print("Cannot store keys in .config dir. Exiting...")
        raise SystemExit
