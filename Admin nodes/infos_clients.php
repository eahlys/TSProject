<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>Informations sur un client</title>
    <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.0/css/bootstrap.min.css">
    <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
</head>
    <body>
        <h1 class="text-center">Informations sur un client</h1> <br>


                    <div class="container">
                        <div class="row">
                            <div class="col-md-auto">
                                <?php include 'connexion_db.php';
                                $id = $_GET["identity"];
								?>
								<?php
								$reponse = $pdo->query("SELECT * FROM clientlocalizationmodel WHERE identity='$id' ");
								while ($donnees = $reponse->fetch())
                                    {
                                        $id_sql = $donnees['identity'];
                                        ?>
                                        <b>Identité du client : </b> <?php echo "$id"; ?> <br />
                                        <b>Node de rattachement : </b> <?php echo $donnees['node']; ?> <br />
                                        <b>Derniere modification du statut, le : </b> <?php echo date('d/m/Y', $donnees['last_seen']).' &agrave; '.date('H:i:s', $donnees['last_seen']); ?>
                                        <?php


                                    $reponse->closeCursor();
                                    }
								?>
                            </div>
                        </div>
                    </div>
                    <?php if ( $id!==$id_sql){ ?>
						<div class="text-center"><?php echo "Client inconnu"; ?></div>
					<?php } ?>
        <br>
        <div class="text-center">
            <a href="index.php" class="btn btn-outline-secondary"> Retour à l'accueil </a>
        </div>

            <script src="https://code.jquery.com/jquery-3.5.1.slim.min.js" >
            <script src="https://cdn.jsdelivr.net/npm/popper.js@1.16.0/dist/umd/popper.min.js" >
            <script src="https://stackpath.bootstrapcdn.com/bootstrap/4.5.0/js/bootstrap.min.js" >
    </body>
</html>