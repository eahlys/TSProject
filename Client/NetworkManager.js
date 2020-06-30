const net = require('net');
const CryptoManager = require('./CryptoManager');

class NetworkManager {

    constructor(_config, log, cryptMgmt, cliMgmt) {
        this.config = _config;
        this.addr;
        this.port;
        this.cliMgmt = cliMgmt;
        this.client = new net.Socket();
        this.connected = false;
        this.session = false;
        this.serverAuth = false;
        this.annonced = false;
        this.ready = false;
        this.tokenList = [];
        this.cmd = ['WELCOME', 'NEW-CLIENT', 'OFFLINE-MESSAGES'];
        this.logger;
        if (log) {
            this.logger = log;
        } else {
            this.logger = console;
        }
        this.CryptoMgmt = cryptMgmt;
        this.initialize();
        this.logger.log('Client Initialized');
    }

    initialize() {
        this.client.on('data', (data) => {
            //this.logger.log('(RECV) <= ' + data, 0);
            this.splitStream(data);
        });

        this.client.on('close', () => {
            this.connected = false;
            this.session = false;
            this.logger.log('Connection closed');
            //this.reconnect();
        });
        //setTimeout(this.keepAlive.bind(this), 2000); //2 seconde of delay before first keepalive
        this.keepAlive();
    }

    splitStream(buf) {
        if(buf.length < 4 ) { //drop if data size header not specified
            return
        }

        let size = buf.readInt32LE(0) + 4; //add little indian size (4 bytes)
        let data = buf.slice(4, size);

        if (this.session) {
            data = this.CryptoMgmt.decryptAES(buf.slice(4, size));
            this.logger.log('(RECV) (E) <= ' + data.toString('base64'), 0);
            this.handleData(data);
        } else {
            data = buf.slice(4, size);
            this.logger.log('(RECV) <= ' + data, 0);
            this.handleData(data);
        }
        this.splitStream(buf.slice(size));
    }

    handleData(data) {
        let dataS = data.toString().split(/\s/g);
        if (this.cmd.includes(dataS[1])) {
            this.logger.log(data);
            return
        } else if( dataS[0] == 'ERR') {
            this.logger.log(data, 2);
            return
        } else if (dataS[1] == 'AUTH-OK') {
            this.ready = true;
            this.logger.log('NETWORK MANAGER IS READY', 1)
        } else if (dataS[1] == 'SERVER-KEY') {
            this.logger.log('STARTING AUTH', 0);
            this.CryptoMgmt.setSrvPubKey('-----BEGIN PUBLIC KEY-----\n' + dataS[2] + '\n-----END PUBLIC KEY-----');
            this.CryptoMgmt.setNodeId(dataS[2]);
            this.send('SESSION-KEY ' + this.CryptoMgmt.getSessionEncrypt());
            return
        } else if(dataS[1] == 'SESSION-OK') {
            this.logger.log('SESSION-OK', 0)
            this.session = true;
            //CLIENT-KEY KEY
            //SEND CLIENT KEY
            this.sessionOk();
            return
        } else if(dataS[1] == 'SERVER-AUTH') {
            this.logger.log('SESSION-AUTHENTICATING', 0)
            if (this.CryptoMgmt.authServer(dataS[2])) {
                this.serverAuth = true;
                this.logger.log('NODE AUTH SUCESSFUL', 0)
            } else {
                this.logger.log('SERVER AUTH UNSUCESSFUL, EXITING')
                const remote = require('electron').remote
                remote.getCurrentWindow().close()
                return;
            };
            return
        } else if (dataS[1] == 'ANNOUNCE-REQUEST') {
            let timestamp = dataS[2];
            let RSAb64id = this.CryptoMgmt.signNodeID(timestamp);
            this.send('ANNOUNCE-DATA ' + timestamp + ' ' + RSAb64id);
            return
        } else if (dataS[1] == 'ANNOUNCE-OK') {
            this.logger.log('SUCCESSFULL ANNONCE ON DHT', 1);
            return
        } else if (dataS[1] == 'GET-CLIENT-KEY') {
            this.cliMgmt.recvKey(dataS[2], dataS[3]);
        } else if (dataS[1] == 'GET-FILESHARE-TOKEN') {
            this.cliMgmt.pushToken(dataS[2]);
            return
        } else if(dataS[1] == 'DATA-FROM' && this.serverAuth) {
            this.cliMgmt.recv(data);
            return
        } else if (!this.serverAuth) {
            this.logger.log('SERVER NOT AUTHENTICATED, DROPING', 2);
            return
        }
        return;
    }

    sessionOk() {
        if (this.CryptoMgmt.getPubDer() == undefined) {
            setTimeout(this.sessionOk.bind(this), 500);
        } else {
            this.send('CLIENT-KEY ' + this.CryptoMgmt.getPubDer().toString('base64'));
            this.send('CLIENT-AUTH ' + this.CryptoMgmt.getAuthenticator().toString('base64'));
        }
    }

    setClientManager(cmgmt) {
        this.cliMgmt = cmgmt;
    }

    reconnect() {
        if (!this.connected) {
            this.client.removeAllListeners();
            this.logger.log('Tentative de reconnection');
            this.client.connect(this.port, this.addr);
            this.connected = true;
            this.logger.log('Reconnected to ' + this.addr + '@' + this.port);
        }
    }

    connect() {
        this.addr = this.config.get('node_ip');
        this.port = this.config.get('node_port');
        this.client.connect(this.port, this.addr);
        this.connected = true;
        this.logger.log('Connected to ' + this.addr + '@' + this.port);
    }

    send(msg) {
        if (msg == '' || msg == null || msg == undefined) {return}
        if (this.session) {
            msg = this.CryptoMgmt.cryptAES(msg);
            
            let size = Buffer.byteLength(msg, 'utf8');
            let buf = Buffer.alloc(4)

            buf.writeInt32LE(size, 0);

            buf = Buffer.concat([buf, Buffer.from(msg, "binary")]);

            this.client.write(buf);

            this.logger.log('(SEND) (E) => ' + msg.toString('base64'), 0); 
        } else {
            let size = Buffer.byteLength(msg, 'utf8');
            let buf = Buffer.alloc(4)

            buf.writeInt32LE(size, 0);

            buf = Buffer.concat([buf, Buffer.from(msg, "binary")]);

            this.client.write(buf);

            this.logger.log('(SEND) => ' + msg, 0); 
        }
    }

    isReady() {
        return this.ready;
    }

    keepAlive() {
        if (this.connected) {
            this.logger.log('SEND KEEPALIVE', 0)
            let msg = 'keepalive';
            let size = Buffer.byteLength(msg, 'utf8');
            let buf = Buffer.alloc(4)

            buf.writeInt32LE(size, 0);

            buf = Buffer.concat([buf, Buffer.from(msg, "binary")]);

            this.client.write(buf);
        }
        setTimeout(this.keepAlive.bind(this), 8000);
    }

    getNodeAddr() {
        return this.addr;
    }
}

module.exports = NetworkManager;