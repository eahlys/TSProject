import logging
import threading
import time
from datetime import datetime

import client_manager
import dht_manager
import fileshare_server
import foreign_node_manager
import mail_exchanger
import node_config
from ClientNetworking import ThrClientManagementServer, ThrClientManagementRequestHandler
from NodeDatabase import LocalClientModel

logger = logging.getLogger("main")


def interactive():
    while True:
        # Debug functions
        user_input = input("")
        if user_input == "list":
            print("List of currently connected clients :")
            client_manager.list_clients()
        elif user_input == "listall":
            print("List of known clients :")
            for client_list in LocalClientModel.select():
                if client_manager.get_local_client(client_list.identity):
                    print("- " + client_list.identity + " - Online")
                else:
                    print(
                        "- " + client_list.identity + " - last seen : " + str(
                            datetime.fromtimestamp(client_list.last_seen)))
        elif user_input == "killall":
            logger.info("Terminating all client connections")
            client_manager.kill_all_clients()
        elif user_input == "fetch":
            print(dht_manager.fetch_node("7f39d31b32085314606ec3166b452319d2b95c310f7225a086d562d9c9d8175b"))
        elif user_input == "getkey":
            print(client_manager.get_client_key("2357ca71c837159013961f2e948b94b3a3bb6010"))
        elif user_input == "getdata":
            print(client_manager.get_client_data("2357ca71c837159013961f2e948b94b3a3bb6010"))
        elif user_input == "thr":
            print(threading.enumerate())
        elif user_input.split()[0] == "ping" and len(user_input.split()) == 2:
            foreign_node_manager.send_ping(user_input.split()[1])
        elif user_input == "killallnodes":
            foreign_node_manager.kill_all_nodes()
            logger.info("Terminating all nodes connections")
        elif user_input == "listallnodes":
            foreign_node_manager.list_nodes()


# Starting mail_exchanger workers
mail_exchanger.start_workers()

# Starting user input thread
interactive_thr = threading.Thread(target=interactive)
interactive_thr.setDaemon(True)
interactive_thr.start()

# Starting fileshare server
fileshare_thr = threading.Thread(target=fileshare_server.start)
fileshare_thr.setDaemon(True)
fileshare_thr.start()

# Starting Client Management server
# address = ('::1', 37405) # pour l'IPv6, à venir
address = (node_config.config["client_listen_ip"], 37405)

server = ThrClientManagementServer(address, ThrClientManagementRequestHandler)
logger.info("Node listening for client connections on " + str(server.server_address[0]) + ":"
            + str(server.server_address[1]) + ", banner : " + node_config.config["banner"])

time.sleep(2)

try:
    server.serve_forever()
except KeyboardInterrupt:
    logger.info("Terminating all client connections and exiting...")
    # Arrêt propre de la DHT
    dht_manager.dht_server.stop()
    client_manager.kill_all_clients()
    foreign_node_manager.kill_all_nodes()
    # Attente de la déconnexion de tous les clients
    while True:
        if client_manager.clients_count() == 0:
            break
        time.sleep(0.5)
    # Besoin d'appeler server.shutdown() dans un autre thread (limitation de socketserver)
    stop_thr = threading.Thread(target=server.shutdown)
    stop_thr.setDaemon(True)
    stop_thr.start()
    time.sleep(2)
