const { copyFile } = require("fs");

function addMsg(id) { //gestion de l'affichage des messages
    if (id != currentId) {
        return;
    }
    msg = CM.getClient(id).msgs[0]
    var iDiv = document.createElement('div');
    var iDiv2 = document.createElement('div');
    let css_commun = 'card mw-perso text-justify msg px-2 '
    if (msg[0] == 'r'){ //messages recus
        iDiv.id = 'block';
        iDiv.className = 'float-left bg-light ' + css_commun; //mise à gauche + mise en forme
        document.getElementById('msg-box').appendChild(iDiv);
        iDiv.innerHTML = msg[1];
    } else if(msg[0] == 's') { //messages envoyées
        iDiv2.id = 'block-2'
        iDiv2.className = 'align-self-end text-light bg-info border border-info text-right '+ css_commun; //mise en forme
        document.getElementById('msg-box').appendChild(iDiv2);
        iDiv2.innerHTML = msg[1];
    }
    updateScroll()
}

function drawMsg() {
    let id = currentId;
    msg = CM.getClient(id).msgs;
    document.getElementById('msg-box').innerHTML = '';
    for (let index = msg.length - 1; index >= 0; index--) {
        var iDiv = document.createElement('div');
        var iDiv2 = document.createElement('div');
        let css_commun = 'card mw-perso text-justify msg px-2 '
        if (msg[index][0] == 'r'){ //messages recus
            iDiv.id = 'block';
            iDiv.className = 'float-left bg-light ' + css_commun; //mise à gauche + mise en forme
            document.getElementById('msg-box').appendChild(iDiv);
            iDiv.innerHTML = msg[index][1];
        } else if(msg[index][0] == 's') { //messages envoyées
            iDiv2.id = 'block-2'
            iDiv2.className = 'align-self-end text-light bg-info border border-info text-right '+ css_commun; //mise en forme
            document.getElementById('msg-box').appendChild(iDiv2);
            iDiv2.innerHTML = msg[index][1];
        }
    }
    updateScroll()
}

function updateScroll(){
    var element = document.getElementById("msg-box");
    element.scrollTop = element.scrollHeight;
}

function ouvrirForm() {
    document.getElementById("myForm").style.display = "block";
}
function fermerForm() {
    document.getElementById("myForm").style.display = "none";
}

let tabContact=[]

function ajouterContact(id){
    if (id == null || id == undefined || id == '' || id == ' ') {
        return
    }
    //tabContact.push({pseudo: rename, nom : 'test-nom',  last_msg: 'test-msg' });
    CM.newClient(id);
    CF.addFriend(id, null)
    displayContact(tabContact);
    document.getElementById('psajouter').value = '';
}

function displayId() {
    if (CRM.getId() == undefined) {
        setTimeout(displayId, 500)
    } else {
        document.getElementById('setmyid').innerHTML = document.getElementById('setmyid').innerHTML + "<span style='font-size:12px'>"+CRM.getId()+"</span>";
        document.getElementById('setmynode').innerHTML = document.getElementById('setmynode').innerHTML + CF.config.node_ip
    }
}

//Variable de test pour display contact
//let tabContactTest =[{ pseudo: 'test-test', nom : 'test-nom',  last_msg: 'test-msg' },
    //{ pseudo: 'test-test-2', nom : 'test-nom-2',  last_msg: 'test-msg-2' }]

//Fonction permettant d'insérer un list-group-item par élément du tableau tabContact
function displayContact(){
    document.getElementById("list-contact").innerHTML = '';
    let friends = CF.getFriends();
    for(let k in friends) {
        let a = document.createElement('a')
        a.className = 'list-group-item '
        if (friends[k].status == 'online') {
            a.className = a.className + 'border-right-green border-width ';
        } else if (friends[k].status == 'offline') {
            a.className = a.className + 'border-right-red border-width ';
        }
        if (k == currentId) {
            a.className = a.className + 'list-group-item-info ';
        } else {
            a.className = a.className +  'list-group-item-light ';
        }
        a.href = '#'
        a.onclick = () => {setCurrentId(k)};
        //a.onclick = "setCurrentId(" + k + ");return false;"
        a.id = k;
        a.innerHTML = '<div class="row align-items-center"><div class="col-10 p-0 pl-3"><p class="m-0">' + friends[k].name + '</p><p class="m-0" style="font-size:8px">' + k + '</p></div>' + '<div class="col-2 p-0 pl-2"><button class="btn btn-danger" onclick="deleteContact(\''+k+'\')">x</button></div></div>'
        //a.innerHTML = a.innerHTML + '<div class="col-2"><button class="btn btn-danger px-3">x</button></div></div>'
        document.getElementById("list-contact").appendChild(a)
    }
    /*for (let i=0; i<tabContact.length; i++){
        //Contact clickable avec la balise onclick
        $("#list-contact").append("<a class=\"list-group-item\" id="+i+" >\n" +
            "                           <b>"+tabContact[i].pseudo+"</b><br>\n" +
            "                           "+tabContact[i].nom+"<br>\n" +
            "                           "+tabContact[i].last_msg+"\n" +
            "                                <span class=\"badge badge-primary badge-pill\">!</span><br>\n" +
            "                        </a>" +
            "                        <button class=\"btn btn-danger\" onclick=deleteContact("+i+")>Supprimer</button><br />");
    }*/
}

function updateContact(id, status) {
    let friends = CF.getFriends();
    if (friends[id] == undefined) {
        return;
    }
    friends[id].name = status.name;
    friends[id].status = status.status;
    displayContact()
}

function deleteContact(id) {
    let friends = CF.getFriends();
    delete friends[id];
    displayContact()
    CM.deleteClient(id);
    CF.deleteFriends(id);
}

function loadContact() {
    let friends = CF.getFriends();
    for(let k in friends) {
        CM.newClient(k);
    }
    displayContact()
}

function clear(){
    $("#list-contact").empty();
}
