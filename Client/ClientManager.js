const NetworkManager = require('./NetworkManager');
const Client = require('./Client');
const EventEmitter = require('events').EventEmitter;

class ClientManager extends EventEmitter {
    constructor(log, netMgmt, cryptMgmt, _config) {
        super();
        this.clients = {};
        this.tokens = [];
        this.netMgmt = netMgmt;
        this.cryptoMgmt = cryptMgmt;
        this.config = _config;
        this.logger;
        if (log) {
            this.logger = log;
        } else {
            this.logger = console;
        }
    }

    recv(data) {
        let dataS = data.split(/\s/g);
        let id = dataS[3]
        let c;
        //si n'existe pas, creer un nouveau client
        if (!(id in this.clients)) {
            c = this.newClient(id);
            this.emit('newContact', id);
        } else {
            c = this.clients[id];
        }
        if (this.clients.length == 0) {
            this.emit('setId', id);
        }
        c.receive(data);
    }

    recvKey(id, key) {
        if (!(id in this.clients)) { //NOT IN
            this.logger.log('CLIENT ' + id + ' UNKNOW, DROPING KEY', 2)
            return
        }
        this.logger.log('RECEIVE KEY FOR CLIENT ' + id);
        this.clients[id].setKey(key);
    } 

    newClient(id) {
        if (id in this.clients) {
            this.logger.log('Client with id ' + id + ' already exist', 2);
            return
        }
        this.logger.log('New client added with id : ' + id, 0)
        let c = new Client(this.logger, id, this.cryptoMgmt, this.config, this.db);
        c.on('send', (data) => {
            //on chiffer le message facon pgp
            this.netMgmt.send(data);
            //this.emit('updateDisplay', id);
        })
        c.on('send-online', (data) => {
            //on chiffer le message facon pgp
            this.netMgmt.send(data);
        })
        c.on('receive', () => {
            this.emit('updateDisplay', id);
        })
        c.on('display', () => {
            this.emit('updateDisplay', id);
        })
        c.on('get-token', () => {
            this.netMgmt.send('GET-FILESHARE-TOKEN');
            this.distributeToken(id)
        })
        c.on('status', (id, status) => {
            this.emit('status', id, status)
        })
        this.clients[id] = c;
        this.askpubKey(id);
        return this.clients[id];
    }

    distributeToken(id) {
        if (this.tokens.length == 0) {
            setTimeout(this.distributeToken.bind(this, id), 200);
        } else {
            this.clients[id].setToken(this.tokens[0]);
            this.tokens.shift(); //delete token
        }
    }

    pushToken(_token) {
        this.tokens.push(_token);
    }

    askpubKey(id) {
        if (this.netMgmt.isReady()) {
            this.logger.log('ASKING CLIENT KEY ' + id);
            this.netMgmt.send('GET-KEY ' + id);   
        } else {
            setTimeout(this.askpubKey.bind(this, id), 100);
        }
    }

    setNetworkManager(nmgmt) {
        this.netMgmt = nmgmt;
    }

    getClient(id) {
        return this.clients[id];
    }

    deleteClient(id) {
        delete this.clients[id];
    }
}

module.exports = ClientManager;