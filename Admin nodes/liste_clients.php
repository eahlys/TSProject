<?php


include 'connexion_db.php';

$term = $_GET['identity'];

$requete = $pdo->prepare('SELECT * FROM clientlocalizationmodel like :term');
$requete->execute(array('term' => '%' . $term . '%'));

$array = array();

while ($donnee = $requete->fetch())
{
	array_push($array, $donnee['identity']);
}

echo json_encode($array);

