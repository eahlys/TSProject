var EventEmitter = require('events').EventEmitter;
var crypto = require('crypto');
const fs = require('fs');
const request = require('request');
const https = require('https');

class Client extends EventEmitter {
    constructor(log, id, _cryptoMgmt, _config) {
        super()
        this.token;
        this.id = id;
        this.msgs = [];
        this.pubKey = null;
        this.logger;
        this.cryptoMgmt = _cryptoMgmt;
        this.config = _config;
        this.status = {
            status : 'unknown',
            name : 'unknown',
        };
        if (log) {
            this.logger = log;
        } else {
            this.logger = console;
        }
        //setTimeout(this.getStatus.bind(this), 3000);
        this.getStatus();
        setTimeout(this.updateStatus.bind(this), 5000)
    }

    getId() {
        return this.id;
    }

    setKey(key) {
        key = '-----BEGIN RSA PUBLIC KEY-----\n' + key + '\n-----END RSA PUBLIC KEY-----';
        this.pubKey = crypto.createPublicKey({
            key : key,
            format : 'pem',
            type : 'pkcs1',
        });
    }

    receive(data) {
        data = data.split(/\s/g);
        //TODO : USE TIMESTAMP
        let timestamp = data[3]
        data = data[4]
        data = Buffer.from(data, 'base64');
        data = data.toString('utf8');

        data = this.PGPdecrypt(data);
        data.toString('utf8');

        this.handleData(data);

        this.logger.log('Client ' + this.id + ' receive message : ' + data, 0);
    }

    handleData(data) {
        data = JSON.parse(data);
        if (data.cmd == 'MESSAGE') {
            this.msgs.unshift(['r', data.data]);
            this.emit('receive');
            return
        } else if(data.cmd == 'GET-STATUS') {
            if (this.config.get('publish_identity')) {
                this.write({
                    cmd : 'OK-STATUS',
                    data: {
                        status : 'online', //online, away, do not disturb, ...
                        name : this.config.get('name'),
                    },
                }, true);
            }
            return
        } else if(data.cmd == 'OK-STATUS') {
            this.logger.log('RECEIVE STATUS FROM ' + this.id);
            this.status =  {
                            status : data.data.status,
                            name : data.data.name,
                            }
            this.emit('status', this.id, this.status);
            return
        } else if(data.cmd == 'UPLOAD') {
            this.logger.log('DOWNLOAD FILE WITH TOKEN : ' + data.data.token);

            let agentOptions = {
                rejectUnauthorized: false
            };

            let agent = new https.Agent(agentOptions);
            
            request.get({
                url: 'https://' + data.data.node_ip + ':' + data.data.node_port + '/download/' + data.data.token,
                agent: agent,
            }, (err, res, body) => {
                let buf = this.PGPdecrypt(body);
                this.handleDownload(buf, data.data)
            })

            return
        } else {
            this.logger.log('UNKNOW CLIENT COMMAND : ' + data.cmd, 2);
        }
    }

    handleDownload(data, info) {
        fs.writeFileSync('download/' + info.filename, data)
        this.msgs.unshift(['r', 'Vous avez recu un fichier : <a href="#" onclick="shell.showItemInFolder(\'' + __dirname + '/download/' + info.filename + '\');return false">' + info.filename + '</a>']);
        this.emit('display');
    }

    write(data, online = false) {
        let updateDisplay = false;
        if (data =='' || data == null || data == undefined || data == " ") {return}
        if (data.cmd == 'MESSAGE') {
            updateDisplay = true;
            this.msgs.unshift(['s', data.data]);
        }
        data = JSON.stringify(data);

        this.logger.log('Client ' + this.id + ' send message  :' + data, 0);

        data = this.PGPcrypt(data);

        data = Buffer.from(data);

        data = data.toString('base64');

        if (online == true) {
            this.emit('send-online','SEND-TO-ONLINE '+ this.id + ' ' + data);
        } else {
            this.emit('send','SEND-TO '+ this.id + ' ' + data);
        }

        if (updateDisplay) {
            this.emit('display');
        }
    }

    getStatus() {
        if (this.pubKey == null) {
            setTimeout(this.getStatus.bind(this), 4000);
            return;
        }
        this.status.status = 'offline'
        this.write({
            cmd : 'GET-STATUS',
            data: null,
        }, true);
        setTimeout(this.getStatus.bind(this), 20100);
    }

    updateStatus() {
        setTimeout(this.updateStatus.bind(this), 15000);
        this.emit('status', this.id, this.status);
    }

    send(_data) {
        if (_data =='' || _data == null || _data == undefined || _data == " ") {return}
        this.write({
            cmd : 'MESSAGE',
            data: _data,
        });
    }

    uploadFile(file_path) {
        if(file_path == undefined || file_path == null || file_path == '') {
            return
        }
        this.getToken();
        this.handleUpload(file_path);
    }

    handleUpload(file_path) {
        if (this.token == undefined || this.token == null) {
            setTimeout(this.handleUpload.bind(this, file_path), 200)
        } else {
            //upload here 
            let myToken = this.token;
            this.token = null;

            let file = fs.readFileSync(file_path.path);

            let file_crypted = this.PGPcrypt(file);

            let formData = {
                file: {
                    value: file_crypted,
                    options: {
                        filename: file_path.name,
                    }
                }
            };

            let agentOptions = {
                rejectUnauthorized: false
            };

            let agent = new https.Agent(agentOptions);

            // Post the file to the upload server
            request.post({
                url: 'https://' + this.config.get('node_ip') + ':' + this.config.get('https_port') + '/upload/' + myToken,
                formData: formData,
                agent: agent
            }, (err, res, body) => {
                this.logger.log(body + ' , with token : ' + myToken, 2);
                if (body.split(/\s/g)[0] != 'ERROR') {
                    this.msgs.unshift(['s', 'Vous avez envoyé un fichier : <a href="#" onclick="shell.showItemInFolder(\'' + file_path.path + '\');return false">' + file_path.name + '</a>']);
                    this.emit('display');
                    this.write({
                        cmd : 'UPLOAD',
                        data: {
                            node_ip : this.config.get('node_ip'),
                            node_port : this.config.get('https_port'),
                            token : myToken,
                            filename : file_path.name,
                        },
                    })
                }
            });
        }
    }

    getToken() {
        this.emit('get-token');
        return;
    }

    setToken(_token) {
        this.token = _token;
    }

    PGPcrypt(data) {
        let sKey = crypto.randomBytes(16);

        let AES = this.cryptAES(data, sKey);

        let sessionRSA = crypto.publicEncrypt(this.pubKey, sKey);

        let PDU = sessionRSA.toString('base64') + ' ' + AES.toString('base64');
        
        //console.log('PGP_CRYPT = ' + PDU)

        this.logger.log('CRYPTING PGP', 0);

        return PDU
    }

    PGPdecrypt(data) {
        data = data.split(/\s/g)

        let sessionRSA = Buffer.from(data[0], 'base64');

        let AES = Buffer.from(data[1], 'base64');

        let session = crypto.privateDecrypt(this.cryptoMgmt.getPriv(), sessionRSA);

        let red = this.decryptAES(AES, session)

        //console.log('PGP_DECRYPT = ' + red);
        this.logger.log('DECRYPTING PGP', 0);
        return red;

    }

    cryptAES(data, sessionKey) {
        let iv = crypto.randomBytes(16);;
    
        let cipher = crypto.createCipheriv('aes-128-gcm', sessionKey, iv);
    
        let encrypted = Buffer.concat([cipher.update(data, 'utf8'), cipher.final()]);
    
        let tag = cipher.getAuthTag();
    
        let msg = Buffer.concat([iv, tag, encrypted])
    
        return msg;
    }
    
    decryptAES(data, sessionKey) {
        let iv = data.slice(0, 16);
        let tag = data.slice(16, 32);
        data = data.slice(32);
    
        let decipher = crypto.createDecipheriv('aes-128-gcm', sessionKey, iv);
        decipher.setAuthTag(tag);
        
        let decrypted = Buffer.concat([decipher.update(data, 'binary'), decipher.final()]);

        return decrypted;
    }

}

module.exports = Client;