import asyncio
import hashlib
import json
import logging
import os
import pickle
import threading
from typing import Tuple, List, Union

from Crypto.PublicKey.RSA import RsaKey
from kademlia.network import Server
from kademlia.utils import digest

import client_manager
import crypto_manager
import node_config
from ForeignNodeNetworking import ThrForeignNodeRequestHandler, ThrForeignNodeServer
from NodeDatabase import ForeignNodeModel, ClientLocalizationModel

"""
dht_manager comporte les éléments permettant la gestion de la DHT: bootstrap, set et get de valeurs
"""

# Modification du niveau de log des loggers utilisés par kademlia
logging.getLogger('rpcudp').setLevel(logging.CRITICAL)
logging.getLogger('asyncio').setLevel(logging.INFO)
logging.getLogger('kademlia').setLevel(logging.ERROR)

logger = logging.getLogger(__name__)

# L'object DHT est initialisé avec l'identité déjà définie du node (hash de cla clé publique)
dht_server = Server(node_id=digest(crypto_manager.identity))

async_loop = asyncio.get_event_loop()


# Coroutine de récupération de valeur dans la DHT
async def get_value(key: str) -> str:
    result = await dht_server.get(key)
    return result


# Coroutine de définition de valeur dans la DHT
async def set_value(key: str, value: str):
    await dht_server.set(key, value)


# Coroutine de démarrage de la DHT
async def start_dht():
    global dht_server

    # Démarrage de la DHT
    await dht_server.listen(37415, interface=node_config.config["dht_listen_ip"])

    # Si le fichier de sauvegarde des nodes connus existe, on bootstrap avec eux :
    if os.path.isfile(".config/known_nodes.dat"):
        logger.info("Joining node federation using "
                    + node_config.config["bootstrap"] + " and previously known nodes...")
        bootstrap_nodes = [(node_config.config["bootstrap"], 37415)] + pickle.load(
            open(".config/known_nodes.dat", "rb"))
        await dht_server.bootstrap(bootstrap_nodes)

    # Sinon, on bootstrap seulement avec l'adresse indiquée dans .config/config.ini
    else:
        logger.info("Joining node federation using "
                    + node_config.config["bootstrap"] + "...")
        await dht_server.bootstrap([(node_config.config["bootstrap"], 37415)])

    # Ajout du node à la DHT (identité du node associée à ses IP signées + clé publique du node)
    await send_node_advertisement()

    # Vérification de l'ajout du node à la DHT
    check_dht = await dht_server.get("node-" + crypto_manager.identity)

    if check_dht:
        logger.info("Successfully connected to federation network")
        logger.info("Node will advertise " + node_config.config["public_ip"] + " on federation")
    else:
        logger.warning("Cannot connect to federation network. Starting node as first DHT node.")


# Coroutine de sauvegarde des nodes actuellement connectés pour un futur bootstrap
async def save_known_nodes():
    nodes = dht_server.bootstrappable_neighbors()
    # On supprime de la liste des nodes à sauvegarder l'adresse de bootstrap indiquée dans .config/config.ini
    if (node_config.config["bootstrap"], 37415) in nodes:
        nodes.remove((node_config.config["bootstrap"], 37415))
    if len(nodes) > 0:
        logger.debug("Saving neighbors for future bootstrap")
        pickle.dump(nodes, open(".config/known_nodes.dat", "wb"))


# Boucle de save_known_nodes toutes les 5 min
async def save_known_nodes_loop():
    while True:
        await asyncio.sleep(300)
        await save_known_nodes()


# Coroutine d'annonce sur la DHT : ajoute et signe les IPs auxquelles le node est joignable, ainsi que sa clé publique
async def send_node_advertisement():
    signature = crypto_manager.sign_rsa(node_config.config["public_ip"].encode())
    node_info = [node_config.config["public_ip"], signature, crypto_manager.str_public_key]
    try:
        await dht_server.set("node-" + crypto_manager.identity, json.dumps(node_info))
    except ValueError:
        logger.debug("No peers found on federation")


# Boucle de send_advertisement toutes les 10 min
async def send_node_advertisement_loop():
    while True:
        await asyncio.sleep(600)
        logger.debug("Sending federation advertisement for " + node_config.config["public_ip"])
        await send_node_advertisement()


# Envoi de l'annonce d'un client connecté dans la DHT
def send_client_data(client_id: str, client_data: List[str]):
    asyncio.run_coroutine_threadsafe(set_value("client-" + client_id, json.dumps(client_data)), loop=async_loop)


# Envoi de la clé publique d'un client dans la DHT
def send_client_public_key(client_id: str, client_key: str):
    asyncio.run_coroutine_threadsafe(set_value("key-" + client_id, client_key), loop=async_loop)


# Récupère les informations d'un client dans la DHT
def fetch_client_data(client_id: str) -> Union[Tuple[str, str], None]:
    raw_data = asyncio.run_coroutine_threadsafe(get_value("client-" + client_id), loop=async_loop).result()
    if raw_data:
        try:
            json_data = json.loads(raw_data)
            timestamp = json_data[0]
            node_id = json_data[1]
            signature = json_data[2]

            # Si la signature correspond à timestamp, node_id signé avec la clé publique du client
            if crypto_manager.check_sign_rsa(crypto_manager.to_rsa_key(client_manager.get_client_key(client_id)),
                                             signature,
                                             str([timestamp, node_id]).encode()):

                # Ajout du client à la database (projet db)
                client_db: ClientLocalizationModel = ClientLocalizationModel.get_or_none(
                    ClientLocalizationModel.identity == client_id)
                # Si il n'existe pas, on crée
                if not client_db:
                    client_db = ClientLocalizationModel.create(identity=client_id, node=node_id, last_seen=timestamp)
                # Si il existe, on update l'IP
                else:
                    client_db.node = node_id
                    client_db.last_seen = timestamp
                    client_db.save()

                return timestamp, node_id
            else:
                logger.warning("Rogue client " + client_id + ". Addresses do not match signature.")
                return None
        except Exception:
            return None
    else:
        return None


# Récupère la clé publique d'un client dans la DHT
def fetch_client_publickey(client_id: str):
    data = asyncio.run_coroutine_threadsafe(get_value("key-" + client_id), loop=async_loop).result()
    if data:
        # Vérifie que les données correspondent bien à une clé publique et que la clé publique correspond à l'identité
        try:
            key = crypto_manager.to_rsa_key(data)
            if hashlib.sha1(data.encode()).hexdigest() == client_id:
                return data
            else:
                logger.warning("Rogue client " + client_id + ". Public key does not match identity.")
                return None
        except Exception:
            return None
    else:
        return None


# Récupération des informations sur un node (IP, clé RSA). Retourne None si non trouvé ou si signature incorrecte
def fetch_node(node_identity: str) -> (Tuple[str, RsaKey], None):
    if node_config.config["standalone"]:
        return None
    raw_infos = asyncio.run_coroutine_threadsafe(get_value("node-" + node_identity), loop=async_loop).result()

    # Si des données ont été trouvées dans la DHT :
    if raw_infos:
        # try:
        json_data = json.loads(raw_infos)
        node_ips = json_data[0]
        signature = json_data[1]
        node_public_key: RsaKey = crypto_manager.to_rsa_key(json_data[2])

        # Si la clé publique reçue correspond à l'indentité du node recherché, on continue
        if hashlib.sha256(json_data[2].encode()).hexdigest() == node_identity:
            # Si la signature des adresses IP correspond (ce qui prouve que le node n'a pas été usurpé)
            if crypto_manager.check_sign_rsa(node_public_key, signature, node_ips.encode()):
                # Une fois le node authentifié, on retourne ses adresses IP ainsi que sa clé publique
                return node_ips, node_public_key
            else:
                logger.warning("Rogue node " + node_identity + ". Addresses do not match signature.")
        else:
            logger.warning("Rogue node " + node_identity + ". Public key does not match identity.")
            # Si un problème est rencontré pendant le traitement, on retourne None
            # except Exception:
            return None
    # Si aucune des conditions précédentes n'a été remplie, on renvoie None
    return None


# Si le node n'est pas configuré pour fonctionner en mode standalone, on démarre la DHT
if not node_config.config["standalone"]:
    # Démarrage de la DHT avec la boucle asyncio
    async_loop.run_until_complete(start_dht())

    # Ajout à la boucle asyncio des fonctions programmées
    async_loop.create_task(send_node_advertisement_loop())
    async_loop.create_task(save_known_nodes_loop())

    logger.info("Starting foreign nodes communication server on " + node_config.config["dht_listen_ip"] + ":37410")

    # Démarrage de la gestion réseau des nodes distants dans un thread
    node_server_address = (node_config.config["dht_listen_ip"], 37410)

    node_server = ThrForeignNodeServer(node_server_address, ThrForeignNodeRequestHandler)
    node_server_thr = threading.Thread(target=node_server.serve_forever)
    node_server_thr.setDaemon(True)
    node_server_thr.start()

    # Démarrage de la boucle asyncio dans un thread
    thr_loop = threading.Thread(target=async_loop.run_forever)
    thr_loop.setDaemon(True)
    thr_loop.start()

    # Ajout du node à la database si il n'existe pas, ou update de son adresse IP (projet db)
    db_model: ForeignNodeModel = ForeignNodeModel.get_or_none(ForeignNodeModel.identity == crypto_manager.identity)
    # Si il n'existe pas, on crée
    if not db_model:
        db_model = ForeignNodeModel.create(identity=crypto_manager.identity,
                                           ip_address=node_config.config["dht_listen_ip"],
                                           public_key=crypto_manager.str_public_key)
    # Si il existe, on update l'IP
    else:
        db_model.ip_address = node_config.config["dht_listen_ip"]
        db_model.save()

else:
    logger.info("Federation disabled in configuration. Starting node as standalone.")
