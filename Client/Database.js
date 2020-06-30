var sq = require('sqlite');

class Database {
    constructor(log) {
        this.logger;
        this.ready = false;
        if (log) {
            this.logger = log;
        } else {
            this.logger = console;
        }
        this.db = new sq.Database('.config/co2pedb.sqlite')
        this.dropTable();
        //this.db.serialize(() => {
        //    this.db.run('CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT , user_id VARCHAR NOT NULL, msg TEXT NOT NULL);');
        //    this.db.run('CREATE TABLE IF NOT EXISTS friends (user_id VARCHAR, user_name VARCHAR);');
        //    this.ready = true;
        //})
        this.db.run('CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT , user_id VARCHAR NOT NULL, msg TEXT NOT NULL);');
        this.db.run('CREATE TABLE IF NOT EXISTS friends (user_id VARCHAR, user_name VARCHAR);');
        //this.insertMsg('test-id', 'test-msg');
        //this.insertMsg('test-id', 'test-msg-2');
        //this.insertMsg('test-id-2', 'test-msg-3');
        //this.insertFriend('aaa', 'ccc');
        //this.insertFriend('bbb', 'aaa');
        //this.listAllMsg();
        //this.listAllFriends();
        //this.getUserMsg('test-id');
        //this.getFriends();
    }

    dropTable() {
        this.db.run('DROP TABLE IF EXISTS messages');
        this.db.run('DROP TABLE IF EXISTS friends');
    }

    insertFriend(id, name) {
        if(!this.ready) {
            setTimeout(this.insertFriend.bind(this, id, name), 100);
        } else {
            this.ready = false;
            this.db.run('INSERT INTO friends VALUES (?, ?)', [id, name], () => {
                //console.log('insert friend success')
                this.ready = true;
            });
        }
    }

    getFriends() {
        if(!this.ready) {
            setTimeout(this.getFriends.bind(this), 100);
        } else {
            this.db.each('SELECT * FROM friends', (err, row) => {
                return row;
            })
        }
    }

    getUserMsg(id) {
        if(!this.ready) {
            setTimeout(this.getUserMsg.bind(this, id), 100);
        } else {
            this.db.each('SELECT user_id, msg FROM messages WHERE user_id = ? ORDER BY id DESC LIMIT 50', [id] , (err, row) => {
                return row;
            })
        }
    }

    insertMsg(id, msg) {
        if(!this.ready) {
            setTimeout(this.insertMsg.bind(this, id, msg), 100);
        } else {
            this.ready = false;
            this.db.run('INSERT INTO messages(user_id, msg) VALUES (?, ?)', [id, msg], () => {
                //console.log('insert msg success')
                this.ready = true;
            });
        }
    }

    listAllMsg() {
        if(!this.ready) {
            setTimeout(this.listAllMsg.bind(this), 100);
        } else {
            //this.db.each('SELECT user_id, msg FROM messages', (err, row) => {
            this.db.each('SELECT * FROM messages', (err, row) => {
                console.log(row);
            })
        }
    }

    listAllFriends() {
        if(!this.ready) {
            setTimeout(this.listAllFriends.bind(this), 100);
        } else {
            //this.db.each('SELECT user_id, msg FROM messages', (err, row) => {
            this.db.each('SELECT * FROM friends', (err, row) => {
                console.log(row);
            })
        }
    }
}

module.exports = Database;