**CO2PE**  
Messagerie instantanée décentralisée.  
Projet informatique 8445.  
Par Pablo Delgado, Pierre Tinard, Oann Binel, Enzo Da Ros et Clément Lecoq.  
Supervisé par Daniel Ranc.  
FIPA GOLF 1A, Télécom Sud Paris.  


Dans un premier temps, il faut faire un clone du projet depuis l’adresse suivante : git@gitlabens.imtbs-tsp.eu:co2pe/co2pe.git

Le client requiert le framework Node.js, qui doit être installé depuis https://nodejs.org

Pour démarrer un client, il faut se placer dans le répertoire “Client” du dossier téléchargé. 
Vous devez ensuite exécuter la commande npm install puis la commande npm start.

La première mise en place du client est effectuée, des fichiers supplémentaire de configuration se sont alors créés. Vous devez alors quitter le client et éditer, à l’aide de votre éditeur préféré, le fichier .config/co2pe.json

Editez le paramètre “NodeIP”: null et entrez l’IP (ou FQDN) du node auquel vous souhaitez vous connecter, entrez ce paramètre entre guillemets. Par exemple “NodeIP”:”127.0.0.1”.

Ensuite, vous pouvez modifier votre identité pour ce faire, il faut changer le paramètre “name”:”votre identité”. Enregistrez et quittez. 

Dans le répertoire “Client”, relancez la commande npm start. 

Vous pouvez désormais profiter pleinement de notre application.

VIII. Procédure de mise en œuvre du node

Le node requiert Python 3 et le gestionnaire de packages pip. Ces derniers sont installables depuis https://www.python.org/downloads/

Une fois le projet cloné à l’aide de l’adresse indiquée dans la partie sur la mise en œuvre du client, il est nécessaire de se rendre dans le répertoire “Node”.

Ensuite, l’installation des dépendances Python se fait à l’aide de la commande :
pip3 install -r requirements.txt

Lancez enfin le node avec la commande python3 main.py

Le node va générer sa configuration dans .config/config.ini, puis se fermer. Il faut maintenant éditer cette configuration.

