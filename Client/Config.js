const fs = require("fs");

class Config {

    constructor(log, path) {
        this.ready = false;
        if (log) {
            this.logger = log;
        } else {
            this.logger = console;
        }
        this.dirPath = path;
        this.filePath = this.dirPath + '/co2pe.json';
        /* CONFIG STRCTURE */
        this.config = {
            pubKey : '',
            privKey : '',
            id: '',
            publish_identity: true,
            name: 'pseudo',
            pseudo: 'common name',
            node_ip: null,
            node_port: 37405,
            https_port: 37420,
            friends : {},
        }
        //download dir
        fs.mkdir('download', (err) => {return});
        /*     FIN     */
        fs.access(this.dirPath, (e) => {
            //create dir and file if not exist
            if (e) {
                this.logger.log('CREATE CONFIG', 1);
                fs.mkdir(this.dirPath, (err) => {return});
                fs.open(this.filePath, 'a+', (err, fd) => {return});
                fs.writeFile(this.filePath, this.config, () => {
                    this.ready = true; 
                });
                this.logger.log('CONFIG HAS BEEN GENERATED, EXITING', 2)
                const remote = require('electron').remote
                let w = remote.getCurrentWindow()
                setTimeout(w.close, 1000)
            } else {
                if (this.load()) {
                    this.ready = true;
                    this.logger.log('IP : ' + this.config.node_ip)
                }
            }
        });
    }

    load() {
        this.logger.log('LOAD CONFIG', 1);
        const raw = fs.readFileSync(this.filePath);
        this.config = JSON.parse(raw);
        return true;
    }

    update() {
        fs.writeFileSync(this.filePath, JSON.stringify(this.config));
    }

    isReady() {
        return this.ready;
    }

    getPubKey() {
        return this.config['pubKey'];
    }

    getPrivKey() {
        return this.config['privKey'];
    }

    get(key) {
        return this.config[key];
    }

    set(key, value) {
        this.logger.log('CONFIG : SET ' + key);
        this.config[key] = value;
        this.update();
    }

    setPubKey(key) {
        this.logger.log('CALL SET PUB KEY ' + key)
        this.config['pubKey'] = key;
        this.update();
    }

    setPrivKey(key) {
        this.config['privKey'] = key;
        this.update();
    }

    getFriends() {
        return this.config.friends;
    }

    addFriend(id, name) {
        this.config.friends[id] = {
            name : name,
            status : 'offline',
        }
        this.update();
    }

    deleteFriends(id) {
        delete this.config.friends[id];
        this.update();
    }
}

module.exports = Config;