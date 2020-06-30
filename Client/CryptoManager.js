const crypto = require('crypto');

class CryptoManager {
    constructor(config, log) {
        this.ready = false;
        this.id;
        this.config = config;
        this.nodeId;
        this.logger;
        this.privKey;
        this.pubKey;
        this.SrvPubKey;
        this.SessionKey;
        this.typeKeyDer = {
            type : 'pkcs1',
            format : 'der',
        }
        this.typeKeyPem = {
            type : 'pkcs1',
            format : 'pem',
        }
        if (log) {
            this.logger = log;
        } else {
            this.logger = console;
        }
        this.logger.log('init crypto')
        this.loadConfig()
        this.SessionKey = crypto.randomBytes(16);
    }

    generateKeys() {
        this.logger.log('GENERATING KEYS');
        crypto.generateKeyPair('rsa', {modulusLength : 2048}, (err, publicKey, privateKey) => {
            this.pubKey = publicKey;
            this.privKey = privateKey;
            this.ready = true;
            this.config.set('pubKey', this.getPubPem());
            this.config.set('privKey', this.getPrivPem());
        });
    }

    loadKeys() {
        this.pubKey = crypto.createPublicKey({
            key : this.config.get('pubKey'),
            format : 'pem',
            type : 'pkcs1',
        });
        this.privKey = crypto.createPrivateKey({
            key : this.config.get('privKey'),
            format : 'pem',
            type : 'pkcs1',
        });
        this.ready = true;
    }

    loadConfig() {
        if (!this.config.isReady()) {
            setTimeout(this.loadConfig.bind(this), 500);
        } else {
            if (this.config.get('pubKey') == '') {
                this.logger.log('DEBUG GENERATE KEY')
                this.generateKeys();
            } else {
                this.logger.log('DEBUG LOAD KEY')
                this.loadKeys();
            }
            this.generateId()
        }
    }

    getId() {
        if (this.id == undefined || this.id == null) {
            setTimeout(this.getId.bind(this), 500);
        } else {
            return this.id;
        }
    }

    generateId() {
        if (!this.ready) {
            setTimeout(this.generateId.bind(this), 500);
        } else {
            const hash = crypto.createHash('sha1');

            hash.update(this.getPubDer().toString('base64'));

            this.id = hash.digest('hex');
        }
    }

    setSrvPubKey(pkey) {
        this.SrvPubKey = crypto.createPublicKey({
            key : pkey,
            format : 'pem',
            type : 'pkcs1',
        });
    }

    setNodeId(b64PubKey) {
        //SHA265 B64 CLE PUB NODE
        this.logger.log('SETTING UP NODE ID', 0);
        const hash = crypto.createHash('sha256');

        hash.update(b64PubKey);

        let id = hash.digest('hex');

        this.nodeId = id;
    }

    getSessionEncrypt() {
        return crypto.publicEncrypt(this.SrvPubKey, this.SessionKey).toString('base64');
    }

    authServer(data) {
        data = Buffer.from(data, "base64");

        let verifier = crypto.createVerify('RSA-SHA256');

        let date = new Date();
        let timestamp = date.getTime();

        timestamp = timestamp.toString();
        timestamp = timestamp.substring(0, timestamp.length - 4)

        verifier.update(timestamp)
        return verifier.verify(this.SrvPubKey, data);
    }

    getAuthenticator() {
        let date = new Date();
        let timestamp = date.getTime();

        timestamp = timestamp.toString();
        timestamp = timestamp.substring(0, timestamp.length - 4)

        let sign = crypto.createSign('RSA-SHA256')
        sign.update(timestamp);
        return sign.sign(this.privKey)
    }

    signNodeID(timestamp) {
        let sign = crypto.createSign('RSA-SHA256')

        let data = '[\'' + timestamp + '\', \'' + this.nodeId + '\']';
        sign.update(data);
        let RSA = sign.sign(this.privKey);
        RSA = RSA.toString('base64');

        return RSA;
    }

    decryptAES(data) {
        let iv = data.slice(0, 16);
        let tag = data.slice(16, 32);
        data = data.slice(32);

        let decipher = crypto.createDecipheriv('aes-128-gcm', this.SessionKey, iv);
        decipher.setAuthTag(tag);
        
        let decrypted = decipher.update(data, 'binary', 'utf8') + decipher.final('utf8');

        return decrypted;
    }

    cryptAES(data) {
        let iv = crypto.randomBytes(16);

        let cipher = crypto.createCipheriv('aes-128-gcm', this.SessionKey, iv);

        let encrypted = Buffer.concat([cipher.update(data, 'utf8'), cipher.final()]);

        let tag = cipher.getAuthTag();

        let msg = Buffer.concat([iv, tag, encrypted])

        return msg;
    }

    getPriv() {
        return this.privKey;
    }

    getPubDer() {
        if (!this.ready) {
            setTimeout(this.getPubDer.bind(this), 500);
        } else {
            return this.pubKey.export(this.typeKeyDer);
        }
    }

    getPubPem() {
        if (!this.ready) {
            setTimeout(this.getPubPem.bind(this), 500);
        } else {
            return this.pubKey.export(this.typeKeyPem);
        }
    }

    getPrivDer() {
        if (!this.ready) {
            setTimeout(this.getPrivDer.bind(this), 500);
        } else {
            return this.privKey.export(this.typeKeyDer);
        }
    }

    getPrivPem() {
        if (!this.ready) {
            setTimeout(this.getPrivPem.bind(this), 500);
        } else {
            return this.privKey.export(this.typeKeyPem);
        }
    }

    printKey() {
        if (!this.ready) {
            setTimeout(this.printKey.bind(this), 500);
        } else {
            //console.log(this.privKey);
            console.log(this.getPubDer());
        }
    }

}

module.exports = CryptoManager;