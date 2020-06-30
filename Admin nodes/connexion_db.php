<?php

//Liste de tous les nodes : ForeignNodeModel
//Liste de tous les clients : ClientLocalizationModel
try{
	$pdo = new PDO('sqlite:'.dirname(__FILE__).'/../Node/.config/db.sqlite');
	$pdo->setAttribute(PDO::ATTR_DEFAULT_FETCH_MODE, PDO::FETCH_ASSOC);
	$pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION); // ERRMODE_WARNING | ERRMODE_EXCEPTION | ERRMODE_SILENT
}
catch(Exception $e) {
	echo "Impossible d'accéder à la base de données SQLite : ".$e->getMessage();
	die();
}
?>
