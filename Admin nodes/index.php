<!DOCTYPE html>
<html lang="fr">
	<head>
		<meta charset="UTF-8">
		<title>Administration des nodes et des clients</title>
		<link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.0/css/bootstrap.min.css">
		<meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
		<script src="https://ajax.googleapis.com/ajax/libs/jquery/1.7.2/jquery.min.js"></script>
	</head>

	<body>
		<h1 class="text-center">Listes des différents nodes</h1>
		<br>
		    <div class="text-center">

			<?php include 'connexion_db.php';
			$reponse = $pdo->query('SELECT * FROM foreignnodemodel');
			// On affiche chaque entrée une à une
			while ($donnees = $reponse->fetch())
			{
			?>
				<div class="card" >
					<div class="card-header">
						Node <a href="infos_nodes.php?identity=<?php echo $donnees['identity']?>" class="btn btn-outline-primary">
							<?php echo $donnees['identity']; ?>
						</a>
					</div>
					<?php
					$id =$donnees['identity'];
					$requete_2="SELECT * FROM clientlocalizationmodel WHERE node='$id' ";
					$reponse_2 = $pdo->query($requete_2);
					while ($donnees_2 = $reponse_2->fetch())
					{
					?>
					<ul class="list-group list-group-flush">
						<li class="list-group-item">
							Client
							<a href="infos_clients.php?identity=<?php echo $donnees_2['identity']?>" class="btn btn-outline-secondary">
								<?php $raccourci = $donnees_2['identity'];
								echo  substr($raccourci,0,10); echo "...";?>
							</a>

						</li><?php
						}
						$reponse_2->closeCursor();

						?>
					</ul>
				</div> <br>
				<?php
				}
				$reponse->closeCursor(); // Termine le traitement de la requête
				?>
				<br>
				<br>




				<div class="text-center">
					<form action = "infos_clients.php" method = "get">
						<input type="text" name="identity" placeholder="Rechercher un client :" id="recherche"/>
						<input type="submit" class="btn btn-outline-secondary"/>
					</form>
				</div>
				<script>jQuery(document).ready(function(){
                        $('#recherche').autocomplete({
                            source : 'liste_clients.php'
                        });
                    });
				</script>
			<script src="https://code.jquery.com/jquery-3.5.1.slim.min.js" >
            <script src="https://cdn.jsdelivr.net/npm/popper.js@1.16.0/dist/umd/popper.min.js" >
            <script src="https://stackpath.bootstrapcdn.com/bootstrap/4.5.0/js/bootstrap.min.js" >
	</body>
</html>