const logger = require('./logger');
const NetworkManager = require('./NetworkManager');
const ClientManager = require('./ClientManager');
const CryptoManager = require('./CryptoManager');
const Config = require('./Config');
const {shell} = require('electron');

let log = new logger()

let currentId;

let CF = new Config(log, '.config');

const CRM = new CryptoManager(CF, log);
const NM = new NetworkManager(CF, log, CRM);
const CM = new ClientManager(log, NM, CRM, CF);

CM.on('updateDisplay', (id) => {addMsg(id)});
CM.on('setId', (id) => {setCurrentId(id)})
CM.on('newContact', (id) => {ajouterContact(id)})
CM.on('status', (id, status) => {updateContact(id, status)})
NM.setClientManager(CM);
//NM.connect();
setTimeout(NM.connect.bind(NM), 1500)

//CM.newClient(0);

currentId = null;
//initiateId();
displayId();

function setCurrentId(newId) {
    //console.log(newId);
    currentId = newId;
    drawMsg()
    displayContact()
}

function display(id) {
    if (id != currentId) {
        //console.log('ID : ' + id + '/ CURRENT ID : ' + currentId);
        return;
    }
    //document.getElementById('msg-box').innerHTML += (CM.getClient(id).msgs[0] + '<Br>');
    //displayMsg();
}

//A virer quand on aura le code de creation d'un conv
function initiateId() {
    if (CRM.getId() == undefined) {
        setTimeout(initiateId, 500);
    } else {
        currentId = CRM.getId();
        CM.newClient(currentId);
    }
}

