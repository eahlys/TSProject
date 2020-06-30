**CO2PE**  
Messagerie instantanée décentralisée.  
Projet informatique 8445.  
Par Pablo Delgado, Pierre Tinard, Oann Binel, Enzo Da Ros et Clément Lecoq.  
Supervisé par Daniel Ranc.  
FIPA GOLF 1A, Télécom Sud Paris.  

## Mise en place du Client

Le client requiert le framework Node.js, qui doit être installé depuis https://nodejs.org

Pour démarrer un client, il faut se placer dans le répertoire “Client”.
Vous devez ensuite exécuter la commande npm install puis la commande `npm start`.

La première mise en place du client est effectuée, des fichiers supplémentaire de configuration se sont alors créés. Vous devez alors quitter le client et éditer, à l’aide de votre éditeur préféré, le fichier `.config/co2pe.json`

Editez le paramètre “`NodeIP`”: `null` et entrez l’IP (ou FQDN) du node auquel vous souhaitez vous connecter, entrez ce paramètre entre guillemets. Par exemple “`NodeIP`”:”`127.0.0.1`”.

Ensuite, vous pouvez modifier votre identité pour ce faire, il faut changer le paramètre “`name`”:”`votre identité`”. Enregistrez et quittez. 

Dans le répertoire “Client”, relancez la commande npm start. 

Vous pouvez désormais profiter pleinement de notre application.

## Mise en place du Node

Le node requiert Python 3 et le gestionnaire de packages pip. Ces derniers sont installables depuis https://www.python.org/downloads/

Il est nécessaire de se rendre dans le répertoire “Node”.

Ensuite, l’installation des dépendances Python se fait à l’aide de la commande :
`pip3 install -r requirements.txt`

Lancez enfin le node avec la commande `python3 main.py`

Le node va générer sa configuration dans .config/config.ini`, puis se fermer. Il faut maintenant éditer cette configuration.

Si vous souhaitez que le node fasse partie d’une fédération, indiquez son adresse IP publique à la ligne “public_ip`”. Sinon, mettez “`standalone`” sur “`True`”.
Les autres paramètres de la configuration sont documentés dans le fichier. Ceux-ci n’ont cependant pas besoin d’être modifiés pour que le node soit fonctionnel.

Si vous souhaitez que votre node rejoigne une fédération, ce dernier doit connaître l’adresse IP ou le nom DNS d’un node déjà existant. Cette valeur correspond à “`bootstrap_node`”. Elle contient par défaut “`dht-boot.edraens.eu`”, qui est un node public déjà fonctionnel et ouvert sur Internet.

Une fois la configuration effectuée, vous pouvez démarrer le node en réutilisant la commande `python3 main.py

Le node est désormais fonctionnel, et est à l’écoute des connexions clients.

