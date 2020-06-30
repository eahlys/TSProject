import hashlib
import logging
import sys
from base64 import b64encode, b64decode
from datetime import datetime
from typing import Union

from Crypto.Cipher import PKCS1_OAEP, AES
from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
from Crypto.PublicKey.RSA import RsaKey
from Crypto.Random import get_random_bytes
from Crypto.Signature.pkcs1_15 import PKCS115_SigScheme

import node_config

"""
crypto_manager contient les fonctions de gestion du chiffrement et de la cryptographie : chiffrement de messages,
gestion des clés, authentification des tiers
"""

logger = logging.getLogger(__name__)

__private_key: RsaKey
public_key: RsaKey

__private_key, public_key = node_config.load_keys()
# Si les clés n'existent pas, on les génère
if not __private_key or not public_key:
    logger.info("RSA keys generation...")
    __private_key = RSA.generate(2048)
    public_key = __private_key.publickey()
    logger.info("New keys generated successfully !")
    node_config.store_keys(__private_key, public_key)

# Génération d'une version base64 de la clé publique
str_public_key = b64encode(public_key.export_key(format="DER")).decode("utf-8")

# Génération du SHA256 de la clé publique, correspondant à l'identité du node
identity = hashlib.sha256(str_public_key.encode()).hexdigest()
logger.info("Node identity is : " + identity)


# Permet de récupérer un objet RsaKey exploitable à partir d'une clé base64
def to_rsa_key(key: str) -> RsaKey:
    return RSA.import_key(b64decode(key))


# Vérifie la signature des données d'authentification d'un tiers
def check_sign_rsa(key: RsaKey, signed_data: bytes, data: bytes) -> bool:
    verifier = PKCS115_SigScheme(key)
    try:
        # noinspection PyTypeChecker
        verifier.verify(SHA256.new(data), b64decode(signed_data))
        return True
    except ValueError:
        return False


def check_authenticator(key: RsaKey, authenticator: str) -> bool:
    return check_sign_rsa(key, authenticator.encode(), str(round(datetime.timestamp(datetime.now())))[:-1].encode())


# Retourne la signature encodée en base64 de données fournies
def sign_rsa(data: bytes) -> str:
    hash_timestamp = SHA256.new(data)
    signer = PKCS115_SigScheme(__private_key)
    # noinspection PyTypeChecker
    return b64encode(signer.sign(hash_timestamp)).decode("utf-8")


# Génération des données d'authentification
def get_authenticator() -> str:
    return sign_rsa(str(round(datetime.timestamp(datetime.now())))[:-1].encode())


# Renvoie une clé de session aléatoire
def generate_session_key() -> bytes:
    return get_random_bytes(16)


# Chiffre des données en clair avec une clé publique distante
def encrypt_rsa(data: Union[str, bytes], public_key: RsaKey) -> bytes:
    if type(data) == str:
        data = data.encode()
    if sys.getsizeof(data) > 200:
        raise Exception("Trying to encrypt too large data with RSA. Limit is 200 bytes.")
    cipher_rsa = PKCS1_OAEP.new(public_key)
    encrypted_data = cipher_rsa.encrypt(data)
    return encrypted_data


# Déchiffre des données chiffrées en RSA avec la clé privée locale
def decrypt_rsa(data: Union[str, bytes]) -> bytes:
    if type(data) == str:
        data = data.decode()
    cipher_rsa = PKCS1_OAEP.new(__private_key)
    return cipher_rsa.decrypt(data)


# Chiffre des données en AES GCM en utilisant la clé de session spécifiée
def encrypt(data: Union[str, bytes], session_key: bytes) -> bytes:
    if type(data) == str:
        data = data.encode()
    cipher = AES.new(session_key, AES.MODE_GCM)
    cipher_data, tag = cipher.encrypt_and_digest(data)
    nonce = cipher.nonce
    return nonce + tag + cipher_data


# Déchiffre des données en AES GCM en utilisant la clé de session spécifiée
def decrypt(data: bytes, session_key: bytes) -> bytes:
    nonce = data[:16]
    tag = data[16:32]
    cipher_data = data[32:]
    cipher = AES.new(session_key, AES.MODE_GCM, nonce=nonce)
    return cipher.decrypt_and_verify(cipher_data, tag)
