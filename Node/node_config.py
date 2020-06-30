import configparser
import logging
import os
import socket
import sys
from typing import *

from Crypto.PublicKey import RSA
from Crypto.PublicKey.RSA import RsaKey

"""
node_config rassemble les fonctions de gestion de la configuration du Node, ainsi que la config du logging
"""

# Modifier le level ci-dessous en fonction des besoins
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(name)s - %(message)s', stream=sys.stdout,
                    level=logging.DEBUG)
logger = logging.getLogger(__name__)

if not os.path.exists(".config"):
    os.mkdir(".config")

config_file = configparser.ConfigParser(allow_no_value=True)

# On crée la config si elle n'existe pas
if not os.path.isfile(".config/config.ini"):
    config_file.add_section(section="general")
    config_file.set("general", "# Bannière de connexion affichée à l'utilisateur")
    config_file.set("general", "banner", "TSProject node, listening")
    config_file.set("general", "# adresse IP d'écoute pour les connexions client")
    config_file.set("general", "client_listen_ip", "0.0.0.0")
    config_file.set("general", "# Nombre de processus de remise de messages, donc de messages pouvant être remis "
                               "simultanément (200 par défaut)")
    config_file.set("general", "delivery_workers", "200")
    config_file.set("general", "# Stockage en Mo utilisable par chaque utilisateur pour le partage de fichiers")
    config_file.set("general", "user_storage", "1000")
    config_file.add_section(section="federation")
    config_file.set("federation", "# Si le node est utilisé sans fédération, mettre la valeur à True")
    config_file.set("federation", "standalone", "False")
    config_file.set("federation",
                    "# Adresse IPv4 publique du node qui sera publiée sur la fédération")
    config_file.set("federation", "public_ip", "")
    config_file.set("federation",
                    "# Adresse IPv4 qui écoutera la DHT (doit correspondre à une interface locale)")
    config_file.set("federation", "dht_listen_ip", "0.0.0.0")
    config_file.set("federation", "# Adresse d'un node déjà existant pour bootstrap la DHT")
    config_file.set("federation", "bootstrap_node", "dht-boot.edraens.eu")

    with open('.config/config.ini', 'w') as fp:
        config_file.write(fp)
    logger.info("Creating new configuration file with default values at .config/config.ini")

# Chargement du fichier de configuration
config_file.read(".config/config.ini")
logger.info("Loading configuration file at .config/config.ini")

# Peuplement des variables de configuration
try:
    config = {
        "banner": config_file.get("general", "banner"),
        "client_listen_ip": config_file.get("general", "client_listen_ip"),
        "delivery_workers": config_file.getint("general", "delivery_workers"),
        "user_storage": config_file.getint("general", "user_storage") * 1000 * 1000,
        "standalone": config_file.getboolean("federation", "standalone"),
        "public_ip": config_file.get("federation", "public_ip"),
        "dht_listen_ip": config_file.get("federation", "dht_listen_ip"),
        "bootstrap": config_file.get("federation", "bootstrap_node"),
    }
except (configparser.NoOptionError, configparser.NoSectionError):
    logger.error("Wrong configuration in .config/config.ini. Delete file to load default values")
    raise SystemExit

# Vérification de l'adresse IP d'écoute client
try:
    socket.inet_pton(socket.AF_INET, config["client_listen_ip"])
except socket.error:
    logger.critical("Client listening IPv4 address is not valid, fix in .config/config.ini")
    raise SystemExit

# Si le node n'est pas configuré pour être standalone, on vérifie l'adresse IP publique et l'addresse d'écoute
if not config["standalone"]:
    try:
        socket.inet_pton(socket.AF_INET, config["public_ip"])
    except socket.error:
        logger.critical("Public IPv4 address is not valid, fix in .config/config.ini or start node in standalone mode")
        raise SystemExit

    try:
        socket.inet_pton(socket.AF_INET, config["dht_listen_ip"])
    except socket.error:
        logger.critical("DHT listening IPv4 address is not valid, fix in .config/config.ini (set to 0.0.0.0 if unsure)")
        raise SystemExit

    # On refuse l'adresse publique 0.0.0.0, qui ne peut pas être annoncée sur la DHT
    if config["public_ip"] == "0.0.0.0":
        logger.critical("Public IPv4 cannot be 0.0.0.0. Please input a specific IP do be announced on federation")
        raise SystemExit


# Gestion des clés de chiffrement
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
