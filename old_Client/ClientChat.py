import hashlib
import threading
import time
from base64 import b64encode
from datetime import datetime
from queue import Queue
from typing import Tuple

from Crypto.PublicKey.RSA import RsaKey

from CryptoHandler import CryptoHandler
from NodeNetworking import NodeClient
from Utils import Singleton

ch: CryptoHandler = Singleton.Instance(CryptoHandler)


class Chat:
    # noinspection PyCallByClass
    instances = {}

    def __init__(self, node_socket: NodeClient, interlocutor_id: str):
        self.interlocutor_id: str = interlocutor_id
        self.interlocutor_key = None
        self.node_socket: NodeClient = node_socket
        self.interlocutor_status = None
        self.instances[self.interlocutor_id] = self
        self.inbox = Queue()

        # Demande de la clé publique du client
        self.lookup_key()

        # Démarrage du thread de processing de l'inbox :
        inbox_thr = threading.Thread(target=self.inbox_listener)
        inbox_thr.setDaemon(True)
        inbox_thr.start()

    def inbox_listener(self):
        # Attente de la réception de la clé publique
        while True:
            if self.interlocutor_key:
                break
            time.sleep(0.2)

        # Process de tous les items de l'inbox
        while True:
            item: Tuple = self.inbox.get()
            timestamp = item[0]
            encrypted_data = item[1]
            print(
                str(datetime.fromtimestamp(int(timestamp))) + " " + self.interlocutor_id + " says : " + ch.decrypt_pgp(
                    encrypted_data, self.interlocutor_key).decode())

    def lookup_key(self):
        self.node_socket.send("GET-KEY " + self.interlocutor_id)

    def set_key(self, public_key: str):
        print("Received public key for client " + self.interlocutor_id)
        self.interlocutor_key: RsaKey = ch.to_rsa(public_key)
        # Vérification de la concordance clé publique - identité de l'interlocuteur :
        if not hashlib.sha1(
                b64encode(self.interlocutor_key.export_key(format="DER"))).hexdigest() == self.interlocutor_id:
            print("WARNING Received public key does not match fellow user's id. This may be to rogue Node on network.")

    def __str__(self):
        return self.interlocutor_id
