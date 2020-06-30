import logging
import threading
from datetime import datetime
from queue import Queue

import client_manager
import crypto_manager
import dht_manager
import foreign_node_manager
import node_config
from ForeignNode import ForeignNode
from NodeDatabase import LocalClientModel, OfflineMessageModel

"""
mail_exchanger s'occupe de la gestion de l'outbox : dès qu'un message y est placé, un des threads workers le gère
"""

logger = logging.getLogger(__name__)

# Constantes pour la gestion d'erreur
ERR_UNKNOWN_CLIENT = 0
ERR_UNREACHABLE_CLIENT = 1

# Queue dans laquelle chaque Client vient déposer ses messages à envoyer
outbox = Queue()


def add_outbox(sender_id: str, recipient_id: str, data: bytes, tstamp: str = None, force_online: bool = False):
    if not tstamp:
        tstamp = str(round(datetime.timestamp(datetime.now())))
    outbox.put((sender_id, recipient_id, data, tstamp, force_online))


def mail_dispatch_worker():
    from Client import Client
    while True:
        # Récupération des données dans l'outbox
        item = outbox.get()
        logger.debug(str(threading.current_thread().name) + " processing outbox " + str(item))
        sender_id: str = item[0]
        recipient_id: str = item[1]
        data: bytes = item[2]
        tstamp: str = item[3]
        force_online: bool = item[4]

        if force_online:
            logger.debug("Processing forced online message")

        # Si le client est connecté localement, on dépose dans son inbox
        recipient: Client = client_manager.get_local_client(recipient_id)
        if recipient:
            logger.debug("Message to local online client")
            # On dépose les données dans l'inbox du client
            recipient.inbox_queue.put(
                ("data-from", tstamp, sender_id, data))
        # Si le node est fédéré, on le recherche sur la fédération
        elif not node_config.config["standalone"]:
            result = dht_manager.fetch_client_data(recipient_id)
            if result:
                node_id = result[1]
                # Si le node est nous même, on stocke en hors ligne si le force online est off
                if node_id == crypto_manager.identity:
                    # Si le message peut être délivré hors ligne, on envoie
                    if not force_online:
                        logger.debug("Message for local offline client")
                        # On tente de stocker en hors ligne, et si ça ne marche pas on envoie une erreur au sender
                        if not store_offline(recipient_id, sender_id, data):
                            send_error(sender_id, recipient_id, ERR_UNREACHABLE_CLIENT)
                    else:
                        logger.debug("Message dropped as client offline")
                # Sinon, on recherche le node
                else:
                    node: ForeignNode = foreign_node_manager.get_foreign_node(node_id)
                    if node:
                        logger.debug("Message to foreign client")
                        node.message_to_foreign_client(tstamp, recipient_id, sender_id, data, force_online)
                    else:
                        logger.debug("Message to foreign client but node not found")
                        send_error(sender_id, recipient_id, ERR_UNREACHABLE_CLIENT)
                        pass

            # Si pas de résultats, on cherche dans la db offline si pas désactivé
            elif not force_online:
                # On tente de stocker hors ligne, et si ça ne marche pas on prévient
                if not store_offline(recipient_id, sender_id, data):
                    send_error(sender_id, recipient_id, ERR_UNREACHABLE_CLIENT)
                    pass

        # Si le client n'est pas connecté au node actuellement
        else:
            # On tente de stocker en hors ligne, et si ça ne marche pas on prévient
            if not store_offline(recipient_id, sender_id, data):
                send_error(sender_id, recipient_id, ERR_UNREACHABLE_CLIENT)
                pass


def send_error(original_sender_id: str, original_recipient_id: str, error_type: int):
    from Client import Client
    # On récupère l'émetteur original du message uniquement si il est local (pour éviter une boucle infinie)
    sender_client: Client = client_manager.get_local_client(original_sender_id)
    if sender_client:
        # Ensuite on envoie l'erreur correspondante : inconnu ou unreachable
        if error_type == ERR_UNKNOWN_CLIENT:
            sender_client.err_unknown_client(original_recipient_id)
        elif error_type == ERR_UNREACHABLE_CLIENT:
            sender_client.err_unreachable_client(original_recipient_id)


# Stocke un message hors ligne. Retourne False en car d'erreur
def store_offline(recipient_id: str, sender_id: str, data: bytes):
    db_recipient: LocalClientModel = LocalClientModel.get_or_none(LocalClientModel.identity == recipient_id)
    if db_recipient:
        logger.debug("Storing offline message for " + recipient_id + " : " + str(data))
        OfflineMessageModel.create(receiver=recipient_id, sender=sender_id, data=data,
                                   timestamp=round(datetime.timestamp(datetime.now())))
        return True
    else:
        return False


def start_workers():
    # Démarrage des workers de livraison de courrier
    logger.info("Starting Mail Exchanger daemon with " + str(node_config.config["delivery_workers"]) + " workers")
    for i in range(node_config.config["delivery_workers"]):
        worker = threading.Thread(target=mail_dispatch_worker)
        worker.setDaemon(True)
        worker.start()
