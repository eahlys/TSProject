import logging
import socket
import socketserver
import struct
import threading
from datetime import datetime

import client_manager
from NodeDatabase import LocalClientModel

"""
ClientNetworking contient les classes et méthodes correspondant aux couches basses réseau.
ThrClientManagementServer attend une connexion etinstancie ThrClientManagementRequestHandler dans un thread pour chaque 
nouveau client, qui appelle ensuite la classe Client.
"""

logger = logging.getLogger(__name__)


class ThrClientManagementRequestHandler(socketserver.BaseRequestHandler):
    request: socket

    def __init__(self, request, client_address, node_server):
        self.client = None
        self.client_identity = None
        self.client_thread: threading.Thread = threading.current_thread()
        super().__init__(request, client_address, node_server)

    # Point d'entrée de chaque connexion client établie
    def handle(self):
        # Si le client n'envoie rien pendant 12 secondes on considère qu'il a timeout (et Client raise ClientTimeout)
        self.request.settimeout(12)
        # Un nouveau client est connecté :
        from Client import Client, ClientDisconnected
        logger.info(str(self.client_address[0]) + ":" + str(self.client_address[1]) + " client connected")

        # Boucle de gestion du client (ne s'arrête que lorsque le client se déconnecte)
        try:
            self.client = Client(self)
        except ClientDisconnected:
            pass
        # On retourne lorsque le client a terminé
        return

    def finish(self):
        logger.info(str(self.client_address[0]) + ":" + str(
            self.client_address[1]) + " (" + str(self.client_identity) + ") client is now offline.")
        # Mise à jour du "last_seen" dans la db locale :
        client_db: LocalClientModel = LocalClientModel.get_or_none(LocalClientModel.identity == self.client_identity)
        if client_db:
            client_db.last_seen = datetime.timestamp(datetime.now())
            client_db.save()
        del self.client
        # Suppression du client dans la liste :
        client_manager.del_client(self.client_identity)
        super().finish()

    # On reçoit les données en prenant en compte leur taille
    def receive(self):
        def recvbytes(n):
            # Helper function to recv n bytes or return None if EOF is hit
            data = bytearray()
            while len(data) < n:
                packet = self.request.recv(n - len(data))
                if not packet:
                    return None
                data.extend(packet)
            return bytes(data)

        # Read message length and unpack it into an integer
        raw_msglen = recvbytes(4)
        if not raw_msglen:
            return None
        msglen = struct.unpack('<i', raw_msglen)[0]
        # Read the message data
        return recvbytes(msglen)

    def send(self, data: bytes):
        full_data = struct.pack('<i', len(data)) + data
        self.request.send(full_data)


class ThrClientManagementServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    # address_family = socket.AF_INET6
    socketserver.TCPServer.allow_reuse_address = True

    def handle_error(self, request, client_address):
        super().handle_error(request, client_address)

    socketserver.ThreadingMixIn.daemon_threads = True
