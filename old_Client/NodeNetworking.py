import hashlib
import socket
import struct
import sys
import threading
import time
from base64 import b64encode, b64decode
from typing import Union

from Crypto.PublicKey.RSA import RsaKey

from CryptoHandler import CryptoHandler
from DbManager import ServerModel
from Utils import Singleton


class NodeClient:
    def __init__(self, ip, port):
        self.node_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.ip = ip
        self.port = port
        self.server_key = None
        self.server_key_str = None
        self.server_id = None
        self.session_key = None
        self.current_chat = None
        self.display_raw = False

    def initiate(self):
        self.node_socket.connect((self.ip, self.port))
        print("Connected to Node.")

    def interactive(self):
        # Starting auth loop
        while True:
            data = self.receive(is_encrypted=False).decode()
            if data.split()[1] == "WELCOME":
                print("Node banner : " + " ".join(data.split()[2:]))
            if data.split()[1] == "SERVER-KEY":
                # On stocke la clé publique du serveur sous forme de RsaKey mais aussi sous forme de String base64
                self.server_key_str: str = data.split()[2]
                self.server_key: RsaKey = ch.to_rsa(self.server_key_str)
                self.server_id = hashlib.sha256(self.server_key_str.encode()).hexdigest()
            if data.split()[1] == "SERVER-AUTH":
                server_authenticator = data.split()[2]
                break

        if ch.check_authenticator(self.server_key, server_authenticator):
            print("Node public key matches authentication challenge")
        else:
            print("FATAL ERROR : NODE HIJACKING DETECTED. EXITING NOW...")
            raise SystemExit

        # Vérif. adresse du serveur au cas où on le connaisse déjà
        check_server: ServerModel = ServerModel.get_or_none(ServerModel.address == self.ip)
        # Si le serveur est inconnu
        if not check_server:
            # On sauvegarde son identité dans la Db
            print("Server " + self.ip + " unknown. Saving server identity...")
            ServerModel.create(address=self.ip, public_key=self.server_key_str)
        # Si le serveur est connu et que sa clé enregistrée ne correspond PAS à la clé qu'il envoie
        elif check_server.public_key != self.server_key_str:
            print(
                "WARNING ! NODE IDENTITY HAS CHANGED ! This may be due to a man-in-the-middle attack. Proceed with "
                "care. Contact server owner if needed.")
            # On demande à l'utilisateur si il veut sauvegarder la nouvelle identité du serveur
            if input("Save new node identity ? [y/N] ") == "y":
                check_server.public_key = self.server_key_str
                check_server.save()
                print("Saving node identity...")
                print("Exiting, please re-connect to apply new server identity.")
                raise SystemExit
            else:
                print("Exiting...")
                raise SystemExit
        # Si le serveur enregistré correspond au serveur auquel on se connecte actuellement
        else:
            pass

        # On génère la clé de session et on l'envoie au serveur
        self.session_key: bytes = ch.generate_session_key()
        print("Session key : " + str(b64encode(self.session_key)))
        self.send(b"SESSION-KEY " + b64encode(ch.encrypt_rsa(self.session_key, self.server_key)), is_encrypted=False)

        while True:
            data = self.receive(is_encrypted=False).decode()
            if data.split()[1] == "SESSION-OK":
                print("Session key exchange successful")
                break

        # A partir de maintenant, les échanges se font en full chiffré

        # Envoi des données d'identité du client
        print("Sending client public key and identity")
        # Envoi de la clé publique
        self.send("CLIENT-KEY " + ch.str_public_key)
        # time.sleep(1)
        # Envoi de l'authenticator
        self.send("CLIENT-AUTH " + ch.get_authenticator())

        while True:
            data = self.receive().decode()
            if data.split()[1] == "AUTH-OK":
                print("Client authentication successful")
                break

        print("")
        time.sleep(0.2)

        # Envoi périodique de keepalives, utilisation d'un thread dédié
        keepalive_thread = threading.Thread(target=self.keepalive_sender)
        keepalive_thread.setDaemon(True)
        keepalive_thread.start()

        # Starting normal communication
        receive_thread = threading.Thread(target=self.listen_loop)
        receive_thread.setDaemon(True)
        receive_thread.start()
        time.sleep(0.2)

        self.input_loop()

    def input_loop(self):
        from ClientChat import Chat
        # Starting input infinite loop
        while True:
            # Si aucun chat n'est au premier plan
            if not self.current_chat:
                user_input = input("Client > ")
                if user_input == "":
                    pass
                elif user_input == "quit":
                    print("Exiting")
                    self.node_socket.close()
                    raise SystemExit
                # Si l'utilisateur écrit 'raw' cela signifie qu'il envoie une commande brute au serveur, on envoie.
                elif user_input.split()[0] == "raw":
                    self.send(user_input.replace("raw", ""))
                    self.display_raw = True
                # Si le client souhaite ouvrir une conversation avec un autre client :
                elif user_input.split()[0] == "open" and len(user_input.split()) == 2:
                    self.current_chat: Chat = Chat(self, user_input.split()[1])
                # Si le client souhaite lister les conversations ouvertes actuellement
                elif user_input == "list":
                    chat_list = []
                    for chat in Chat.instances:
                        chat_list.append(chat)
                    for i in range(0, len(chat_list)):
                        print(str(i + 1) + " : " + str(chat_list[i]))
                # Si le client souhaite ouvrir un chat, on récupère l'objet qui correspond :
                elif user_input.split()[0] == "chat" and len(user_input.split()) == 2:
                    print("Opening chat " + user_input.split()[1])
                    chat_list = []
                    for chat in Chat.instances:
                        chat_list.append(chat)
                    interlocutor_id = chat_list[int(user_input.split()[1]) - 1]
                    self.current_chat = Chat.instances[interlocutor_id]
                elif user_input == "fetch":
                    self.send(b"FETCH-OFFLINE")
                # Si les données ne sont pas vides et ne correspondent à rien
                elif user_input != "":
                    print("Client unknown command")
            # Si un chat est au premier plan
            else:
                user_input = input(str(self.current_chat) + " > ")
                if user_input == "/quit":
                    self.current_chat = None
                elif user_input != "":
                    self.send(
                        b"SEND-TO " + self.current_chat.interlocutor_id.encode() + b" " + b64encode(ch.encrypt_pgp(
                            user_input.encode(), self.current_chat.interlocutor_key)))
            # time.sleep(0.2)

    def listen_loop(self):
        from ClientChat import Chat
        while True:
            data = self.receive().decode()
            if self.display_raw:
                print("Node : " + data)
                self.display_raw = False
            data = data.split()
            if data[1] == "GET-CLIENT-KEY":
                chat: Chat = Chat.instances[data[2]]
                chat.set_key(data[3])
            elif data[1] == "DATA-FROM":
                timestamp = str(data[2])
                interlocutor_id = str(data[3])
                encrypted_data = b64decode(data[4])
                # Si le chat n'existe pas, on le crée
                if str(interlocutor_id) in Chat.instances:
                    chat = Chat.instances[interlocutor_id]
                else:
                    chat = Chat(self, interlocutor_id)
                # Puis on ajoute le message dans l'inbox du chat
                chat.inbox.put((timestamp, encrypted_data))
            elif data[1] == "OFFLINE-MESSAGES":
                if not data[2] == "0":
                    print("You received " + data[2] + " message(s) while offline")
            elif data[1] == "ANNOUNCE-REQUEST":
                # print(str([data[2], self.server_id]))
                signed_data = ch.sign_rsa(str([data[2], self.server_id]))
                self.send("ANNOUNCE-DATA " + data[2] + " " + signed_data)

    # Envoie un keepalive toutes les 8 secondes
    def keepalive_sender(self):
        while True:
            try:
                self.send("keepalive", False)
            # Si la fonction send renvoie OSError, alors le socket est fermé.
            except OSError:
                sys.exit()
            time.sleep(8)
            pass

    def receive(self, is_encrypted=True):
        def recvbytes(n):
            # Helper function to recv n bytes or return None if EOF is hit
            data = bytearray()
            while len(data) < n:
                packet = self.node_socket.recv(n - len(data))
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
        data = recvbytes(msglen)
        if is_encrypted:
            data = ch.decrypt_aes(data, self.session_key)
        return data

    def send(self, data: Union[bytes, str], is_encrypted=True):
        if type(data) == str:
            data = data.encode()
        if is_encrypted:
            data = ch.encrypt_aes(data, self.session_key)
        full_data = struct.pack('<i', len(data)) + data
        self.node_socket.send(full_data)


if __name__ == '__main__':
    # Init CryptoHandler
    # noinspection PyCallByClass,PyCallByClass
    ch: CryptoHandler = Singleton.Instance(CryptoHandler)
    print("Identity : " + ch.identity)
    print("Simple TCP client starting...")
    ip_input = input("IP address of server [127.0.0.1] : ")
    port_input = input("TCP port of server [37405] : ")
    if not ip_input:
        ip_input = "127.0.0.1"
    if not port_input:
        port_input = 37405

    node = NodeClient(ip_input, port_input)
    try:
        node.initiate()
        print("")
        node.interactive()
    except ConnectionRefusedError:
        print("Cannot connect to server. Exiting.")
        raise SystemExit
