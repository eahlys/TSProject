<!DOCTYPE html>
<html lang="fr">
    <head>
        <meta charset="UTF-8">
        <title>Informations sur un node</title>
        <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.0/css/bootstrap.min.css">
        <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
    </head>

    <body>
        <h1 class="text-center">Information sur le node</h1> <br>
                    <div class="container">
                      <div class="row">
                        <div class="col-md-auto">
                            <?php include 'connexion_db.php' ?>
                                <b>Identifiant du node : </b><?php $id = $_GET["identity"];
                                echo "$id";
                                $requete = "SELECT * FROM foreignnodemodel WHERE identity='$id' ";
                                $reponse = $pdo->query($requete);
                            	while ($donnees = $reponse->fetch())
                            	{
                            	?>
                            	<br>
                                <b>Adresse ip : </b><?php echo $donnees['ip_address']; ?> <br>
                                <b>Clé publique : </b>  <?php echo $donnees['public_key']; ?>
                                <b>Liste des clients connectés sur ce node : </b> <br>
                            	<?php
                            	}

                            	$reponse->closeCursor();

                            	$requete_2="SELECT * FROM clientlocalizationmodel WHERE node='$id' ";
                            	$reponse_2 = $pdo->query($requete_2);
                            	while ($donnees_2 = $reponse_2->fetch())
                            	{
                            	?>

                                        <a href="infos_clients.php?identity=<?php echo $donnees_2['identity']?>" class="btn btn-outline-primary">
                                            <?php echo $donnees_2['identity']; ?>
                                        </a>
                                    <br> <br>
                            	<?php
                            	}
                            		$reponse_2->closeCursor();

                            	?>
                            <br>
                            <div class="text-center">
                                <a href="index.php" class="btn btn-outline-secondary"> Retour à l'accueil </a>
                            </div>
                        </div>
                      </div>
                    </div>

            <script src="https://code.jquery.com/jquery-3.5.1.slim.min.js" >
            <script src="https://cdn.jsdelivr.net/npm/popper.js@1.16.0/dist/umd/popper.min.js" >
            <script src="https://stackpath.bootstrapcdn.com/bootstrap/4.5.0/js/bootstrap.min.js" >
    </body>
</html>