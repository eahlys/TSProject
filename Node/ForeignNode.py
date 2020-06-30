import hashlib
import logging
import socket
import threading
import time
from base64 import b64decode, b64encode
from queue import Queue
from typing import Tuple, Union

from Crypto.PublicKey.RSA import RsaKey
from func_timeout import func_set_timeout, FunctionTimedOut

import crypto_manager
import dht_manager
import foreign_node_manager
import mail_exchanger
from ForeignNodeNetworking import ThrForeignNodeRequestHandler
from NodeDatabase import ForeignNodeModel

"""
ForeignNode est instancié à chaque fois qu'on traite avec un nouveau node de la fédération
"""

logger = logging.getLogger(__name__)


class ForeignNodeDisconnected(Exception):
    pass


class ForeignNode:
    node_identity: str

    def __init__(self, comm_handler: ThrForeignNodeRequestHandler, is_server, node_id: str = "",
                 node_key: RsaKey = None):
        self.comm_handler: ThrForeignNodeRequestHandler = comm_handler
        self.node_address = comm_handler.client_address
        self.node_identity = node_id
        self.node_key = node_key
        self.session_key = None
        self.is_server = is_server
        self.inbox_queue: Queue = Queue()
        self.thread = threading.current_thread()

        # Lancement de la phase d'authentification / négociation de clé (timeout de 4 secondes)
        try:
            self.node_auth()
        except (Exception, FunctionTimedOut):
            logger.warning(str(self) + " foreign node error during authentication")
            raise ForeignNodeDisconnected

        # Lancement de la boucle d'écoute des commandes client
        thr_main = threading.Thread(target=self.main_loop)
        thr_main.setDaemon(True)
        thr_main.start()

        # Lancement de la boucle d'écoute des commandes internes
        self.inbox_listener()

    # Inbox listener récupère les commandes envoyées par d'autres thread puis les fait éxecuter par le thread
    # du client. Cela permet d'être thread-safe ainsi que de raise les exceptions au bon endroit.
    def inbox_listener(self):
        while True:
            message: Tuple = self.inbox_queue.get()
            # Pour chaque message ajouté à l'inbox
            logger.debug(self.node_identity + " processing inbox : " + str(message))
            # Si l'event correspond à la commande de fermeture, on appelle close()
            if message[0] == "close":
                self.close(message[1])
            elif message[0] == "ping":
                self.ping()
            elif message[0] == "get-status":
                self.get_status(message[1])
            # Réception d'une communication à destination d'un client du node distant
            elif message[0] == "exchange":
                self.message_to_foreign_client(message[1], message[2], message[3], message[4], message[5])

    @func_set_timeout(4)
    def node_auth(self):
        # Si on est le serveur, alors on attend l'authentification du client (Session, identité, authenticator)
        if self.is_server:
            while True:
                data = self.listen_wait(is_encrypted=False)
                if data:
                    data = data.decode().split()
                    break
            encb64_session_key: str = data[0]
            encb64_foreign_identity = data[1]
            b64_foreign_authenticator = data[2]

            # On déchiffre la clé de session envoyée
            self.session_key: bytes = crypto_manager.decrypt_rsa(b64decode(encb64_session_key))

            logger.debug("Session key : " + b64encode(self.session_key).decode())

            # On déchiffre l'identité distante, chiffrée avec la clé de session
            self.node_identity = crypto_manager.decrypt(b64decode(encb64_foreign_identity), self.session_key).decode()

            logger.debug("Foreign node identity : " + self.node_identity)

            # On récupère les infos du node dans la DHT
            ip, self.node_key = dht_manager.fetch_node(self.node_identity)

            # Si l'IP de connexion ne matche pas avec l'IP advertisée, on kill (sauf en cas de tests locaux) :
            if ip != self.node_address[0] and self.node_address[0] not in ("127.0.0.1", "127.0.0.2"):
                logger.debug(self.node_identity + " connecting from " + self.node_address[
                    0] + ", does not match federation IP " + ip + ". Killing.")
                raise Exception

            # Si la clé publique ne matche pas avec l'identité envoyée, on kill :
            if self.node_identity != hashlib.sha256(b64encode(self.node_key.export_key(format="DER"))).hexdigest():
                logger.debug(self.node_identity + " ID does not match federation public key. Killing.")
                raise Exception

            # Si l'authenticator ne matche pas, on kill
            if not crypto_manager.check_authenticator(self.node_key, b64_foreign_authenticator):
                logger.debug(self.node_identity + " authenticator does not match public key. Killing.")
                raise Exception

            # Ensuite, on répond notre identité. On chiffre notre id avec la clé de session et on ajoute l'authenticator
            encb64_own_identity: bytes = b64encode(crypto_manager.encrypt(crypto_manager.identity, self.session_key))
            b64_own_authenticator: str = crypto_manager.get_authenticator()

            self.send(encb64_own_identity + b" " + b64_own_authenticator.encode(), is_encrypted=False)

        # Si on est client (à l'initiative de la connexion), alors on envoie en premier
        # (et on connait déjà la clé publique et l'identité d'en face)
        else:
            # On génère une clé de session, et on la chiffre en RSA
            self.session_key: bytes = crypto_manager.generate_session_key()
            logger.debug(self.node_identity + " session key is " + b64encode(self.session_key).decode())
            encb64_session_key: bytes = b64encode(crypto_manager.encrypt_rsa(self.session_key, self.node_key))

            # On chiffre notre propre identité en AES
            encb64_own_identity: bytes = b64encode(crypto_manager.encrypt(crypto_manager.identity, self.session_key))

            # On génère notre authenticator
            b64_own_authenticator: bytes = crypto_manager.get_authenticator().encode()

            # On envoie
            self.send(encb64_session_key + b" " + encb64_own_identity + b" " + b64_own_authenticator,
                      is_encrypted=False)

            # On attend les informations du serveur (identité, authenticator)
            while True:
                data = self.listen_wait(is_encrypted=False)
                if data:
                    data = data.decode().split()
                    break
            encb64_foreign_identity = data[0]
            foreign_identity = crypto_manager.decrypt(b64decode(encb64_foreign_identity), self.session_key).decode()
            b64_foreign_authenticator = data[1]

            # On vérifie que l'identité renvoyée correspond bien à l'identité attendue
            if self.node_identity != foreign_identity:
                logger.debug(self.node_identity + " received identity "
                             + foreign_identity + " does not match expected one. Killing.")
                raise Exception

            # On vérifie que l'authenticator reçu correspond bien. Si pas le cas, on kill
            if not crypto_manager.check_authenticator(self.node_key, b64_foreign_authenticator):
                logger.debug(self.node_identity + " authenticator does not match public key. Killing.")
                raise Exception

        # On vérifie que le node n'est pas déjà connecté en local
        existing_node: ForeignNode = foreign_node_manager.get_local_foreign_node(self.node_identity)
        try:
            if existing_node:
                existing_node.close("connected from another place")
                self.send("ALREADY-CONNECTED Node already authenticated. Killing old connection...")
                # Attente de la déconnexion de l'ancien node
                while True:
                    if self.node_identity not in foreign_node_manager.instances:
                        logger.debug(str(self) + " : old connection killed")
                        break
                    time.sleep(0.5)
        except ReferenceError:
            pass

        # On ajoute le node à la liste des nodes actuellement connectés
        logger.info(
            str(self.node_address[0]) + ":" + str(self.node_address[1]) + " is now authenticated as " + str(
                self))
        foreign_node_manager.add_node(self.node_identity, self)

        self.comm_handler.node_identity = self.node_identity

        # Ajout du node à la database si il n'existe pas, ou update de son adresse IP
        db_model: ForeignNodeModel = ForeignNodeModel.get_or_none(ForeignNodeModel.identity == self.node_identity)
        # Si il n'existe pas, on crée
        if not db_model:
            db_model = ForeignNodeModel.create(identity=self.node_identity, ip_address=self.node_address[0],
                                               public_key=b64encode(self.node_key.export_key(format="DER")).decode(
                                                   "utf-8"))
        # Si il existe, on update l'IP
        else:
            db_model.ip_address = self.node_address[0]
            db_model.save()

    def receive(self, sender_id: str, message: bytes):
        self.send(b"DATA-FROM " + sender_id.encode() + b" " + message)

    def ping(self):
        # Si l'appel de ping est réalisé depuis le thread du node, on envoie directement
        if self.thread == threading.current_thread():
            logger.debug(str(self) + " sending ping")
            self.send("PING")
        # Sinon, on ajoute le message dans l'inbox_queue pour que le thread du node le process
        else:
            self.inbox_queue.put(("ping",))

    def message_to_foreign_client(self, tstamp: str, recipient_id: str, sender_id: str, data, force_online: bool):
        if self.thread == threading.current_thread():
            logger.debug(str(self) + " inter node data exchange")
            if force_online:
                online_flag = b"1"
            else:
                online_flag = b"0"
            self.send(
                b"EXCHANGE " + tstamp.encode() + b" " + online_flag + b" "
                + recipient_id.encode() + b" " + sender_id.encode() + b" " + data)
        else:
            self.inbox_queue.put(("exchange", tstamp, recipient_id, sender_id, data, force_online))

    def get_status(self, client_id: str):
        # Si l'appel de get_status est réalisé depuis le thread du node, on envoie directement
        if self.thread == threading.current_thread():
            logger.debug(str(self) + " asking " + client_id + " status")
            self.send("GET-STATUS " + client_id)
        # Sinon, on ajoute le message dans l'inbox_queue pour que le thread du node le process
        else:
            self.inbox_queue.put(("get-status", client_id))

    def do_exchange_recv(self, data):
        data = data.split()
        if len(data) == 6:
            tstamp = data[1]
            online_flag = data[2]
            recipient_id = data[3]
            sender_id = data[4]
            sent_data = data[5]

            if online_flag == "0":
                force_online = False
            else:
                force_online = True

            # On ajoute à l'outbox de notre mailexchanger
            mail_exchanger.add_outbox(sender_id, recipient_id, sent_data.encode(), tstamp, force_online)

    def do_unknown_client(self, id: str):
        self.send("CLIENT-UNKNOWN " + id + " Client is not known from this node")

    def do_ping_reply(self, data):
        logger.debug("ping from " + self.node_identity)
        self.send("PONG")

    def main_loop(self):

        function_switcher = {
            "ping": self.do_ping_reply,
            "exchange": self.do_exchange_recv,
        }
        while True:
            data = self.listen_wait()
            if not data:
                break
            data = data.decode()
            # On redirige vers la fonction correspondant à la commande
            main_command = data.split()[0].lower()
            function_call = function_switcher.get(main_command)
            if function_call:
                # noinspection PyArgumentList
                function_call(data)

    def listen_wait(self, is_encrypted: bool = True) -> Union[bytes, None]:
        try:
            while True:
                # On attend que le client envoie quelque chose et on renvoie cette valeur
                data: bytes = self.comm_handler.receive()
                # Si le socket n'envoie plus rien, alors le client est déconnecté. On ferme le thread d'écoute
                if not data or data == b'':
                    self.close("closed")
                    time.sleep(2)
                # Si la donnée reçue n'est pas un keepalive, on process (sinon on recommence la boucle)
                if data != b"keepalive":
                    # Si on s'attend à des données chiffrées, alors on les déchiffre avec clé de session et un décode
                    # base64
                    if is_encrypted:
                        data: bytes = crypto_manager.decrypt(data, self.session_key)
                        # Si les données chiffrées ne correspondent à rien, alors le client est déconnecté
                        if data == b'':
                            self.close("node left")
                        logger.debug(str(self) + " (E) -> " + str(data))
                    else:
                        logger.debug(str(self) + " -> " + str(data))
                    break
            return data
        # Si le socket timeout alors on ferme la connexion
        except socket.timeout:
            self.close("connection left unused")
        except ValueError:
            self.close("encryption error, received cleartext data while expecting encrytion")
        # Si on a une erreur de chiffrement ou de récupération de valeurs, on ferme immédiatement
        except (TypeError, AttributeError):
            pass

    def send(self, data, is_encrypted: bool = True):
        if type(data) == str:
            data = data.encode()

        if is_encrypted:
            logger.debug(str(self) + " (E) <- " + str(data))
            data = (crypto_manager.encrypt(data, self.session_key))
        else:
            logger.debug(str(self) + " <- " + str(data))

        self.comm_handler.send(data)

    def close(self, message: str = "unknown"):
        # Si l'appel de close est réalisé depuis le thread du node, on raise l'exception et on ferme
        if self.thread == threading.current_thread():
            logger.debug(str(self) + " connection closed (" + message + ")")
            self.send("DISCONNECTED Node closed connection : " + message)
            raise ForeignNodeDisconnected
        # Sinon, on ajoute le message dans l'inbox_queue pour que le thread du node le process
        else:
            self.inbox_queue.put(("close", message))

    def __str__(self):
        return str(self.node_identity) if self.node_identity else str(self.node_address[0]) + ":" + \
                                                                  str(self.node_address[1])
