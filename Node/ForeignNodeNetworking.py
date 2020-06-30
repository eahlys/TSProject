import logging
import socket
import socketserver
import struct
import threading

"""
ForeignNodeNetworking contient les classes et méthodes correspondant aux couches basses réseau.
ThrForeignNodeServer attend une connexion e itinstancie ThrForeignNodeRequestHandler dans un thread pour chaque 
nouveau node connecté, qui appelle ensuite la classe ForeignNode.
"""

logger = logging.getLogger(__name__)


class ThrForeignNodeRequestHandler(socketserver.BaseRequestHandler):
    request: socket

    def __init__(self, request, client_address, node_server, is_server: bool = True, node_id: str = "", node_key=None):
        self.foreign_node = None
        self.node_identity = node_id
        self.is_server = is_server
        self.node_key = node_key
        self.node_thread: threading.Thread = threading.current_thread()
        super().__init__(request, client_address, node_server)

    # Point d'entrée de chaque connexion node entrante établie
    def handle(self):
        # Si aucun échange n'a lieu pendant 1 minutes, on ferme la connexion
        self.request.settimeout(60)
        # Un nouveau node est connecté :
        from ForeignNode import ForeignNode, ForeignNodeDisconnected
        logger.info(str(self.client_address[0]) + ":" + str(self.client_address[1]) + " node connected")

        # Boucle de gestion du node (ne s'arrête que lorsque le node se déconnecte)
        try:
            self.foreign_node = ForeignNode(self, self.is_server, self.node_identity, self.node_key)
        except ForeignNodeDisconnected:
            pass
        # Fermeture du socket si il n'est pas fermé
        self.request.close()
        # On retourne lorsque le client a terminé
        return

    def finish(self):
        import foreign_node_manager
        logger.info(str(self.client_address[0]) + ":" + str(
            self.client_address[1]) + " (" + str(self.node_identity) + ") node is now offline.")
        del self.foreign_node
        # Suppression du client dans la liste :
        foreign_node_manager.del_node(self.node_identity)
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
        msglen = struct.unpack('>I', raw_msglen)[0]
        # Read the message data
        return recvbytes(msglen)

    def send(self, data: bytes):
        full_data = struct.pack('>I', len(data)) + data
        self.request.send(full_data)


class ThrForeignNodeServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    socketserver.TCPServer.allow_reuse_address = True

    def handle_error(self, request, client_address):
        super().handle_error(request, client_address)

    socketserver.ThreadingMixIn.daemon_threads = True


class ForeignNodeClient:
    def __init__(self, node_id, ip_address, node_key):
        self.node_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.node_address = (ip_address, 37410)
        self.node_socket.connect(self.node_address)
        self.node_id = node_id
        self.node_key = node_key

        # Création du thread
        thr_node = threading.Thread(target=ThrForeignNodeRequestHandler, args=(
            self.node_socket, self.node_address, self, False, self.node_id, self.node_key))
        thr_node.setDaemon(True)
        thr_node.start()
