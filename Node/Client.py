import hashlib
import logging
import os
import random
import socket
import string
import threading
import time
from base64 import b64decode, b64encode
from datetime import datetime
from queue import Queue
from typing import Tuple

from Crypto.PublicKey.RSA import RsaKey
from func_timeout import FunctionTimedOut, func_set_timeout

import client_manager
import crypto_manager
import dht_manager
import fileshare_server
import mail_exchanger
import node_config
from ClientNetworking import ThrClientManagementRequestHandler
from NodeDatabase import LocalClientModel, ClientKeyModel, ClientLocalizationModel, FileShareModel

"""
Client est instancié à chaque fois qu'un nouveau client se connecte : il s'agît de la classe de gestion de chaque
client.
"""

logger = logging.getLogger(__name__)


class ClientDisconnected(Exception):
    pass


class Client:
    client_identity: str

    def __init__(self, comm_handler: ThrClientManagementRequestHandler):
        self.comm_handler: ThrClientManagementRequestHandler = comm_handler
        self.client_address = comm_handler.client_address
        self.client_identity = ""
        self.client_key_str = None
        self.client_key = None
        self.session_key = None
        self.inbox_queue: Queue = Queue()
        self.thread = threading.current_thread()
        self.database_model = None
        self.announce_data = ["0"]

        # Envoi de la bannière de bienvenue
        self.send("WELCOME " + node_config.config["banner"], is_encrypted=False)
        time.sleep(0.05)

        # Envoi de la clé publique du serveur
        self.send("SERVER-KEY " + crypto_manager.str_public_key, is_encrypted=False)
        time.sleep(0.05)

        # Envoi de l'authenticator
        self.send("SERVER-AUTH " + crypto_manager.get_authenticator(), is_encrypted=False)
        time.sleep(0.05)

        # Lancement de la phase de négociation de clé de session. Timeout de 5 sec
        try:
            self.client_crypto_exchange()
        except (Exception, FunctionTimedOut):
            logger.warning(str(self) + " client error during session encryption key exchange")
            raise ClientDisconnected

        # A partir de ce point, tous les échanges sont chiffrés avec la clé de session

        # Lancement de la phase d'authentification du client. Timeout de 5 sec
        try:
            self.client_auth()
        except (Exception, FunctionTimedOut):
            # except (FunctionTimedOut):
            logger.warning(str(self) + " client error during authentication")
            raise ClientDisconnected

        # Lancement de la boucle d'écoute des commandes client
        thr_main = threading.Thread(target=self.main_loop)
        thr_main.setDaemon(True)
        thr_main.start()

        # Lancement du thread d'attente avant d'envoyer les messages reçus hors ligne
        # Il est utile d'attendre pour laisser le temps au client de s'initialiser proprement
        thr_offline_receive = threading.Thread(target=self.wait_before_sending_offline)
        thr_offline_receive.setDaemon(True)
        thr_offline_receive.start()

        # Lancement de la boucle d'écoute des commandes internes
        self.inbox_listener()

    # Inbox listener récupère les commandes envoyées par d'autres thread puis les fait éxecuter par le thread
    # du client. Cela permet d'être thread-safe ainsi que de raise les exceptions au bon endroit.
    def inbox_listener(self):
        while True:
            message: Tuple = self.inbox_queue.get()
            # Pour chaque message ajouté à l'inbox
            logger.debug(self.client_identity + " processing inbox : " + str(message))
            # Si l'event correspond à la commande de fermeture, on appelle close()
            if message[0] == "close":
                self.close(message[1])
            # Si ce sont des données reçues (tstamp, émetteur, message)
            elif message[0] == "data-from":
                self.send(b"DATA-FROM " + message[1].encode() + b" " + message[2].encode() + b" " + message[3])
                # Délai minimal de 80ms entre deux réceptions de messages pour éviter tout soucis de connexion
                time.sleep(0.08)
            # Si l'event est une demande d'annonce, on demande au client les données d'annonce DHT
            elif message[0] == "announce-request":
                self.request_announce_dht()
            elif message[0] == "client-unknown":
                self.err_unknown_client(message[1])
            elif message[0] == "client-unreachable":
                self.err_unreachable_client(message[1])

    # Lance une demande des informations d'annonce du client pour la DHT
    def request_announce_dht(self):
        try:
            # Demande au client de signer ses informations (ID du node + timestamp actuel)
            self.send("ANNOUNCE-REQUEST " + str(
                round(datetime.timestamp(datetime.now()))) + " Please send announce data for federation")
        except OSError:
            pass

    # Gestion du handshake crypto avec le client
    @func_set_timeout(5)
    def client_crypto_exchange(self):
        while True:
            data = self.listen_wait(False).decode()
            if data.split()[0] == "SESSION-KEY":
                break
            else:
                self.send("SESSION-NEEDED Please send session key", True, False)
        self.session_key = crypto_manager.decrypt_rsa(b64decode(data.split()[1]))
        logger.debug(str(self) + " session key : " + str(b64encode(self.session_key)))
        self.send("SESSION-OK Session key exchange successful", is_encrypted=False)

    # Gestion de l'authentification d'un client
    @func_set_timeout(7)
    def client_auth(self):
        # On attend que le client envoie ses infos d'authentification
        while True:
            data = self.listen_wait().decode()
            if data.split()[0] == "CLIENT-KEY":
                break
            else:
                self.send("KEY-NEEDED Please send public key", True)

        self.client_key_str = data.split()[1]
        self.client_key: RsaKey = crypto_manager.to_rsa_key(self.client_key_str)

        while True:
            data = self.listen_wait().decode()
            if data.split()[0] == "CLIENT-AUTH":
                break
            else:
                self.send("AUTH-NEEDED Please auth", True)

        client_authenticator = data.split()[1]

        # Si le client est bien qui il prétend être
        if crypto_manager.check_authenticator(self.client_key, client_authenticator):
            # self.client_identity: str = hashlib.sha1(self.client_key.export_key(format="DER")).hexdigest()
            self.client_identity: str = hashlib.sha1(self.client_key_str.encode()).hexdigest()
            self.comm_handler.client_identity = self.client_identity
            self.send("AUTH-OK Successfully authenticated, welcome " + self.client_identity)
            # On vérifie que le client n'est pas déjà connecté
            existing_client: Client = client_manager.get_local_client(self.client_identity)
            # Si le client est déjà connecté, on ferme la connexion de l'ancien
            if existing_client:
                existing_client.close("connected from another place")
                self.send("ALREADY-CONNECTED You are logged in from another place. Killing old connection...")
                # Attente de la déconnexion de l'ancien client
                while True:
                    if self.client_identity not in client_manager.instances:
                        logger.debug(str(self) + " : old connection killed")
                        break
                    time.sleep(0.5)
            # Ajout du client à la liste des clients
            logger.info(
                str(self.client_address[0]) + ":" + str(self.client_address[1]) + " is now authenticated as " + str(
                    self))
            client_manager.add_client(self.client_identity, self)
            # Ajout du client à la base de données si il n'existe pas
            self.database_model: LocalClientModel = LocalClientModel.get_or_none(
                LocalClientModel.identity == self.client_identity)
            if not self.database_model:
                self.database_model = LocalClientModel.create(identity=self.client_identity,
                                                              last_seen=datetime.timestamp(datetime.now()))
                ClientKeyModel.get_or_create(identity=self.client_identity, public_key=self.client_key_str)
                logger.debug(str(self) + " creating new client identity in database")
                self.send("NEW-CLIENT You are new on this node. Welcome.")
            else:
                self.database_model.last_seen = datetime.timestamp(datetime.now())
                self.database_model.save()

            # Ajout du client à la database (projet db)
            client_db: ClientLocalizationModel = ClientLocalizationModel.get_or_none(
                ClientLocalizationModel.identity == self.client_identity)
            # Si il n'existe pas, on crée
            if not client_db:
                client_db = ClientLocalizationModel.create(identity=self.client_identity, node=crypto_manager.identity,
                                                           last_seen=datetime.timestamp(datetime.now()))
            # Si il existe, on update l'IP
            else:
                client_db.node = crypto_manager.identity
                client_db.last_seen = datetime.timestamp(datetime.now())
                client_db.save()

            # Envoi du nombre de messages hors-ligne au client
            self.send("OFFLINE-MESSAGES " + str(self.database_model.offline_messages.count()))
            time.sleep(0.2)
            # Si le node n'est pas configuré pour être standalone, on demande au client les données d'annonce DHT
            if not node_config.config["standalone"]:
                self.request_announce_dht()
        else:
            self.send("AUTH-ERROR Authentication error, wrong identity. Closing.")
            raise Exception

    # Envoie une erreur au client indiquant qu'un client est inconnu
    def err_unknown_client(self, client_id: str):
        # Si la commande est appelée depuis la boucle de gestion on envoie
        if self.thread == threading.current_thread():
            self.send("CLIENT-UNKNOWN " + client_id + " Client is not known on network", is_error=True)
        # Sinon on ajoute à l'inbox
        else:
            self.inbox_queue.put(("client-unknown", client_id))

    # Envoie une erreur au client indiquant qu'un client n'est pas joignable (Node down)
    def err_unreachable_client(self, client_id: str):
        # Si la commande est appelée depuis la boucle de gestion on envoie
        if self.thread == threading.current_thread():
            self.send("CLIENT-UNREACHABLE " + client_id + " Client is known but unreachable", is_error=True)
        # Sinon on ajoute à l'inbox
        else:
            self.inbox_queue.put(("client-unreachable", client_id))

    def do_hello(self, data):
        self.send("Hello user ! You said " + data)

    def do_whoami(self, data):
        self.send("You are " + self.client_identity)

    def do_quit(self, data):
        pass

    # Récupération de la clé publique d'un client
    def do_get_key(self, data):
        if len(data.split()) != 2:
            self.do_unknown_command()
        else:
            client_key = client_manager.get_client_key(data.split()[1])
            if not client_key:
                self.err_unknown_client(data.split()[1])
            else:
                self.send("GET-CLIENT-KEY " + data.split()[1] + " " + client_key)

    # Envoi d'un message à un client local ou distant (ajout à l'outbox du mail_exchanger)
    def do_send_to(self, data, force_online: bool = False):
        # Vérification du nombre d'arguments de la commande
        if len(data.split()) != 3:
            self.do_unknown_command()
        else:
            recipient_identity = data.split()[1]
            data = data.split()[2].encode()
            # Ajout à l'outbox du MailExchanger
            mail_exchanger.add_outbox(self.client_identity, recipient_identity, data, force_online=force_online)

    # Envoi d'un message à un client (pas de stockage offline possible)
    def do_send_to_online(self, data):
        self.do_send_to(data, force_online=True)

    # Récupération des messages reçus hors ligne
    def do_fetch_offline(self, data):
        for offline_message in self.database_model.offline_messages:
            self.inbox_queue.put(
                ("data-from", str(offline_message.timestamp), offline_message.sender, offline_message.data))
            offline_message.delete_instance()

    # Fonction permettant la récupération d'un token d'upload de fichiers
    def do_get_fileshare_token(self, data):
        # Boucle de génération
        while True:
            # Génération d'un token alphanumérique aléatoire (45 caractères)
            token = ''.join((random.choice(string.ascii_letters + string.digits) for i in range(45)))
            # On vérifie que le token généré n'existe pas déjà dans la db. Si il n'existe pas, on break
            existing_fileshare_model: FileShareModel = FileShareModel.get_or_none(FileShareModel.token == token)
            if not existing_fileshare_model:
                break
            else:
                logger.debug("Tried to generate existing fileshare token")

        # Ajout du nouveau token à la db
        FileShareModel.create(token=token, owner=self.client_identity,
                              timestamp=round(datetime.timestamp(datetime.now())))

        self.send("GET-FILESHARE-TOKEN " + token)
        logger.debug("New fileshare token generated and added to database")

    # Fonction permettant la récupération du quota de stockage du client
    def do_get_fileshare_quota(self, data):
        used_size = client_manager.get_used_fileshare_size(self.client_identity)
        max_size = node_config.config["user_storage"]
        self.send("GET-FILESHARE-QUOTA " + str(used_size) + " " + str(max_size))

    # Supprime tous les partages de fichiers en attente de l'utilisateur
    def do_delete_fileshare(self, data):
        query = (FileShareModel.select().where(
            FileShareModel.owner_id == self.client_identity))
        for result in query:
            # On delete le fichier
            os.remove(os.path.join(fileshare_server.app.config['UPLOAD_FOLDER'], result.token))
            # Puis le token
            result.delete_instance()
        self.send("DELETE-FILESHARE-OK")

    # Stocke les données d'annonce reçues par le client
    def do_announce_data(self, data):
        tstamp = data.split()[1]
        signature = data.split()[2]
        # On vérifie le timestamp avec 10 sec de tolérance
        if abs(int(tstamp) - round(datetime.timestamp(datetime.now()))) < 10:
            # On vérifie que la signature correpond bien à [timestamp, id node]
            client_announce = [tstamp, crypto_manager.identity]
            if crypto_manager.check_sign_rsa(self.client_key, signature, str(client_announce).encode()):
                # On ajoute la signature aux données
                client_announce.append(signature)
                # On envoie les infos du client dans la DHT (tstamp, id node, signature)
                dht_manager.send_client_data(self.client_identity, client_announce)
                # On envoie la clé publique du client dans la DHT
                dht_manager.send_client_public_key(self.client_identity, self.client_key_str)
                self.send("ANNOUNCE-OK Successfully announced client on federation")
            else:
                self.send("ANNOUNCE-ERROR-SIGN Cannot announce, signature error", is_error=True)
        else:
            self.send("ANNOUNCE-ERROR-TSTAMP Cannot announce, timestamp error", is_error=True)

    def do_unknown_command(self):
        self.send("Unknown command", True)

    # Thread d'écoute des commandes client
    def main_loop(self):

        # Liste des commandes client
        function_switcher = {
            "hello": self.do_hello,
            "whoami": self.do_whoami,
            "get-key": self.do_get_key,
            "send-to": self.do_send_to,
            "send-to-online": self.do_send_to_online,
            "fetch-offline": self.do_fetch_offline,
            "get-fileshare-token": self.do_get_fileshare_token,
            "get-fileshare-quota": self.do_get_fileshare_quota,
            "delete-fileshare": self.do_delete_fileshare,
            "announce-data": self.do_announce_data,
            "quit": self.do_quit,
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
                # noinspection PyArgumentList,PyTypeChecker
                function_call(data)
            else:
                self.do_unknown_command()

    # Attends que le client envoie quelque chose, et process les données reçues
    def listen_wait(self, is_encrypted: bool = True) -> bytes:
        try:
            while True:
                # On attend que le client envoie quelque chose et on renvoie cette valeur
                data: bytes = self.comm_handler.receive()
                # Si le socket n'envoie plus rien, alors le client est déconnecté
                if not data or data == b'':
                    self.close("client left")
                    time.sleep(2)
                # Si la donnée reçue n'est pas un keepalive, on process (sinon on recommence la boucle)
                if data != b"keepalive":
                    # Si on s'attend à des données chiffrées, alors on les déchiffre avec clé de session et un décode
                    # base64
                    if is_encrypted:
                        data: bytes = crypto_manager.decrypt(data, self.session_key)
                        # Si les données chiffrées ne correspondent à rien, alors le client est déconnecté
                        if data == b'':
                            self.close("client left")
                        logger.debug(str(self) + " (E) -> " + str(data))
                    else:
                        logger.debug(str(self) + " -> " + str(data))
                    break
            return data
        # Si le socket timeout alors on ferme la connexion
        except socket.timeout:
            self.close("timed out")
        except ValueError:
            self.close("encryption error, received cleartext data while expecting encrytion")
        # Si on a une erreur de chiffrement ou de récupération de valeurs, on ferme immédiatement
        except (TypeError, AttributeError):
            pass

    # Attend 4 secondes après la connexion du client puis lui envoie ses messages hors ligne
    def wait_before_sending_offline(self):
        time.sleep(4)
        self.do_fetch_offline(None)

    # Envoie des données au client connecté
    def send(self, data, is_error: bool = False, is_encrypted: bool = True):
        code: bytes = b"OK" if not is_error else b"ERR"
        if type(data) == str:
            data = data.encode()
        prefixed_data: bytes = code + b" " + data

        if is_encrypted:
            logger.debug(str(self) + " (E) <- " + str(prefixed_data))
            prefixed_data = (crypto_manager.encrypt(prefixed_data, self.session_key))
        else:
            logger.debug(str(self) + " <- " + str(prefixed_data))

        self.comm_handler.send(prefixed_data)

    # Ferme la connexion avec le client
    def close(self, message: str = "unknown"):
        # Si l'appel de close est réalisé depuis le thread du client, on raise l'exception et on ferme
        if self.thread == threading.current_thread():
            logger.debug(str(self) + " connection closed (" + message + ")")
            self.send("DISCONNECTED Node closed connection : " + message, is_error=True)
            # On indique l'heure de dernière connexion du client dans la db
            existing_db_client: LocalClientModel = LocalClientModel.get_or_none(
                LocalClientModel.identity == self.client_identity)
            if existing_db_client:
                existing_db_client.last_seen = datetime.timestamp(datetime.now())
                existing_db_client.save()
            raise ClientDisconnected
        # Sinon, on ajoute le message dans l'inbox_queue pour que le thread du client le process
        else:
            self.inbox_queue.put(("close", message))

    def __str__(self):
        return str(self.client_identity) if self.client_identity else str(self.client_address[0]) + ":" + \
                                                                      str(self.client_address[1])
