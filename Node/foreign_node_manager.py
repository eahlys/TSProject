import logging
import time
import weakref
from typing import Union

from func_timeout import func_set_timeout, FunctionTimedOut

import ForeignNodeNetworking
import crypto_manager
import dht_manager
from ForeignNode import ForeignNode

"""
foreign_node_manager rassemble les fonctions de gestion des nodes étrangers, utilisables par d'autres méthodes
"""

logger = logging.getLogger(__name__)

instances = {}


# Fonction de debug permettant d'envoyer un ping  à un node distant
def send_ping(node_identity: str):
    node: ForeignNode = get_foreign_node(node_identity)
    if node:
        node.inbox_queue.put(("ping",))


# Renvoie un ForeignNode local si déjà connecté ou fait une recherche DHT, lance une connexion et retourne le node
def get_foreign_node(node_identity: str) -> Union[ForeignNode, None]:
    # Tente de récupérer un node déjà connecté en local
    local_node = get_local_foreign_node(node_identity)
    if local_node:
        return local_node
    # Si pas de résultat, alors on essaye de le trouver dans la DHT et de s'y connecter:
    else:
        # Si connect_to_node renvoie True, alors la tentative de connexion est en cours et tout va bien
        if connect_to_node(node_identity):
            # On attend que le node s'authentifie et apparaisse dans la liste des nodes connectés
            try:
                logger.debug("Trying to get node")
                return wait_for_local_node(node_identity)
            except FunctionTimedOut:
                return None
        # Si elle renvoie False, alors le node n'a pas été trouvé ou il est impossible de s'y connecter, on renvoie None
        else:
            return None


# Tente de se connecte à un node étranger. Renvoie True si la tentative de connexion est en cours, False sinon
def connect_to_node(node_identity: str) -> bool:
    if node_identity == crypto_manager.identity:
        logger.warning("Cannot connect to self")
    else:
        result = dht_manager.fetch_node(node_identity)
        if result:
            try:
                ForeignNodeNetworking.ForeignNodeClient(node_identity, result[0], result[1])
                return True
            except ConnectionRefusedError:
                logger.debug(node_identity + " node found, but unable to connect")
                return False
        else:
            logger.debug(node_identity + " node not found")
            return False


# Attends qu'un node soit connecté
@func_set_timeout(4)
def wait_for_local_node(node_identity: str) -> ForeignNode:
    while True:
        result = get_local_foreign_node(node_identity)
        if result:
            return result
        time.sleep(0.3)


# Récupère un node actuellement connecté en local
def get_local_foreign_node(node_identity: str):
    try:
        return instances[node_identity]
    except KeyError:
        return None


def add_node(node_identity: str, node_object: ForeignNode):
    instances[node_identity] = weakref.proxy(node_object)


def del_node(node_identity: str):
    if node_identity in instances:
        instances.pop(node_identity)


def list_nodes():
    print("Authenticated nodes list :")
    for client in instances:
        try:
            print("- " + client)
        except ReferenceError:
            pass


def kill_all_nodes():
    for client in instances:
        try:
            get_local_foreign_node(client).close("server terminated all connections")
        except ReferenceError:
            pass
