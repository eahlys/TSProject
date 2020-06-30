import logging
import threading
import time
import weakref
from datetime import datetime
from typing import Union, Tuple

import crypto_manager
import dht_manager
import node_config
from Client import Client
from NodeDatabase import LocalClientModel, ClientKeyModel, FileShareModel

"""
client_manager rassemble les fonctions de gestion des clients, utilisables par d'autres méthodes
"""

logger = logging.getLogger(__name__)

instances = {}


# Récupère un client local
def get_local_client(client_identity: str):
    try:
        return instances[client_identity]
    except KeyError:
        return None


def get_local_client_last_connection(client_identity: str) -> Union[str, None]:
    client: LocalClientModel = LocalClientModel.get_or_none(
        LocalClientModel.identity == client_identity)
    if client:
        return str(client.last_seen)
    else:
        return None


# Renvoie le statut de connexion d'un user ("ONLINE"/"UNKNOWN" si en ligne, sinon le timestamp de dernière apparition):
# def get_client_status(client_identity: str):
#     # Si le client est connecté sur ce node on renvoie true et
#     if client_identity in instances:
#         return "ONLINE"
#     # Si le node est fédéré, on cherche dans la DHT
#     elif not node_config.config["standalone"]:
#         result = get_client_data(client_identity)
#         # Si on a pas de résultat, on renvoie UNKOWN:
#         if not result:
#             return "UNKNOWN"
#         # Sinon, on regarde si le timestamp est plus vieux de 10 min.
#         else:
#             tstamp = result[0]
#             node_id = result[1]
#             # Si oui, le client est forcément Offline
#             if int(tstamp) < round(datetime.timestamp(datetime.now()))-600:
#                 return tstamp
#             # Si non, on demande au node hébergeant le client si il est en ligne
#             node: ForeignNode = get_foreign_node(node_id)
#             if node:
#                 node.inbox_queue.put(("get-status",))


# Renvoie (dernière annonce, id node)
def get_client_data(client_identity: str) -> Union[Tuple[str, str], None]:
    # Si le client est connecté localement
    if client_identity in instances:
        logger.debug("Fetched client " + client_identity + " data : client is locally connected")
        # On retourne le timestamp actuel ainsi que l'ID du node actuel
        return str(round(datetime.timestamp(datetime.now()))), crypto_manager.identity
    # Sinon, on cherche les infos dans la DHT si le node n'est pas en standalone
    elif not node_config.config["standalone"]:
        dht_data = dht_manager.fetch_client_data(client_identity)
        # Si on a trouvé des données, on retourne
        if dht_data:
            timestamp = dht_data[0]
            node_id = dht_data[1]
            logger.debug("Fetched client " + client_identity + " data from federation : client is on " + node_id)
            return timestamp, node_id
        # Si on ne trouve rien (peut être qu'on est pas bootstrapé sur la DHT), on cherche en local
        else:
            timestamp = get_local_client_last_connection(client_identity)
            # Si on a trouvé des infos, on retourne
            if timestamp:
                logger.debug("Fetching client " + client_identity +
                             " data : client not found in federation, returning last local one")
                return timestamp, crypto_manager.identity
            else:
                logger.debug("Fetching client " + client_identity + " data : unknown locally and in federation")
                return None
    # Si le client n'est pas trouvé localement et que la fédération est désactivée
    else:
        # On cherche le client en local
        timestamp = get_local_client_last_connection(client_identity)
        # Si on a trouvé des infos, on retourne
        if timestamp:
            logger.debug("Fetched client " + client_identity + " data : client is local but currently offline")
            return timestamp, crypto_manager.identity
        else:
            logger.debug("Fetching client " + client_identity + " data : does not exists on this node database")


def get_client_key(client_identity: str):
    try:
        client_key: ClientKeyModel = ClientKeyModel.get_or_none(
            ClientKeyModel.identity == client_identity)
        # Si le client n'est pas connu localement et que le node n'est pas standalone, on cherche dans la DHT
        if not client_key and not node_config.config["standalone"]:
            dht_key = dht_manager.fetch_client_publickey(client_identity)
            # Si la clé existe dans la DHT on l'ajoute à la DB locale et on retourne
            if dht_key:
                ClientKeyModel.get_or_create(identity=client_identity, public_key=dht_key)
                logger.debug("Fetched client " + client_identity + " public key from DHT, storing in local cache")
                return dht_key
            # Sinon, on retourne None
            else:
                logger.debug("Unable to fetch client public key " + client_identity)
                return None
        # Sinon, on renvoie la clé publique trouvée en local
        else:
            if client_key:
                logger.debug("Fetched client " + client_identity + " public key from local cache")
            else:
                logger.debug("Unable to fetch client public key " + client_identity)
            return client_key.public_key

    except (KeyError, AttributeError):
        return None


def add_client(client_identity: str, client_object: Client):
    instances[client_identity] = weakref.proxy(client_object)


def del_client(client_identity: str):
    if client_identity in instances:
        instances.pop(client_identity)


def list_clients():
    print("Authenticated clients list :")
    for client in instances:
        try:
            print("- " + client)
        except ReferenceError:
            pass


def kill_all_clients():
    for client in instances:
        try:
            get_local_client(client).close("server terminated all connections")
        except ReferenceError:
            pass


def clients_count():
    return len(instances)


# Lance la demande d'annonce pour chaque client toutes les 10 minutes
def announce_all_clients_loop():
    while True:
        logger.debug("Requesting every connected client for federation announce data")
        for client_id in instances:
            try:
                # Ajout de l'announce-request dans l'inbox du client
                get_local_client(client_id).inbox_queue.put(("announce-request",))
            # Except AttribueError permet d'éviter le plantage du thread si le client n'est pas totalement initialisé
            except AttributeError:
                pass
        time.sleep(600)


# Si le node est configuré pour être fédéré, on lance announce_all_clients_loop dans un thread
if not node_config.config["standalone"]:
    clients_announce_thr = threading.Thread(target=announce_all_clients_loop)
    clients_announce_thr.setDaemon(True)
    clients_announce_thr.start()


# Retourne la taille totale utilisée par l'utilisateur pour le partage de fichiers (en octets)
def get_used_fileshare_size(client_identity):
    query = (FileShareModel.select().where(
        FileShareModel.owner_id == client_identity))
    used_size = 0
    for result in query:
        if result.size:
            used_size += result.size
    return used_size
