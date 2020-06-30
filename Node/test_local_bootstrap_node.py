import asyncio
import logging

from kademlia.network import Server
from kademlia.utils import digest

handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
log = logging.getLogger('kademlia')
log.addHandler(handler)
log.setLevel(logging.DEBUG)

loop = asyncio.get_event_loop()
loop.set_debug(True)

server = Server(node_id=digest(b"bootstrapnodelocal"))
loop.run_until_complete(server.listen(37415, interface="127.0.0.3"))

try:
    loop.run_forever()
except KeyboardInterrupt:
    pass
finally:
    server.stop()
    loop.close()
