import socket
import struct

node_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
node_socket.connect(("127.0.0.1", 37405))


def send_msg(sock, msg):
    # Prefix each message with a 4-byte length (network byte order)
    print("sending " + str(len(msg)) + " bytes")
    msg = struct.pack('>I', len(msg)) + msg
    sock.sendall(msg)


while True:
    send_msg(node_socket, input("data?").encode())
