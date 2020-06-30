const conModule =  require('console');

class logger {
    constructor(minLvl, con) {
        this.console;
        this.minLvl;
        let console_type;
        if (con) {
            this.console = con;
            console_type = 'given'
        } else {
            this.console = new conModule.Console(process.stdout, process.stderr);
            console_type = 'default'
        }
        if (minLvl) {
            this.minLvl = minLvl;
        } else {
            this.minLvl = 0;
        }
        this.console.log('CONSOLE : Using ' + console_type + ' console, debug level = ' + this.minLvl)
    }

    setHead(lvl) {
        let head;
        switch (lvl) {
            case 0:
                head = '[DEBUG]';
                break;
            case 1:
                head = '[INFO]';
                break;
            case 2:
                head = '[WARN]';
                break;
            case 3:
                head = '[ERROR]';
                break;
            default:
                head = '[DEBUG]';
                break;
        }
        return head;
    }

    log(msg, lvl) {
        if (lvl == undefined) {
            lvl = 1;
        }
        msg = this.setHead(lvl) + ' ' + msg;
        if (lvl >= this.minLvl) {
            this.console.log(msg)
        }
    }
}

module.exports = logger;