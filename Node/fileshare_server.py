import logging
import os

from flask import Flask, request, send_from_directory, after_this_request
from werkzeug.datastructures import FileStorage

import client_manager
import node_config
from NodeDatabase import FileShareModel

"""
fileshare_server est un serveur web minimaliste écrit en CherryPy permettant l'upload/download des fichiers partagés
"""

app = Flask(__name__)

# Récupération du logger et désactivation des messages intégrés
logging.getLogger('werkzeug').disabled = True
app.logger.disables = True
os.environ['WERKZEUG_RUN_MAIN'] = 'true'

logger = logging.getLogger(__name__)

# Configuration
if not os.path.exists("fileshare_storage"):
    os.mkdir("fileshare_storage")

app.config["UPLOAD_FOLDER"] = os.path.dirname(os.path.realpath(__file__)) + "/fileshare_storage"
# Taille max d'upload : 1Go
app.config['MAX_CONTENT_LENGTH'] = 1000 * 1024 * 1024


# Gestion 404
@app.errorhandler(404)
def page_not_found(e):
    return 'ERROR NOT-FOUND'


# Page d'upload (n'accepte que du POST)
@app.route('/upload/<token>', methods=['POST'])
def upload(token):
    # Vérification de l'existence du token
    existing_fileshare: FileShareModel = FileShareModel.get_or_none(FileShareModel.token == token)
    if not existing_fileshare:
        return 'ERROR TOKEN-NOT-FOUND'
    # Vérification que le token n'a pas déjà été utilisé (size différent de null)
    if existing_fileshare.size:
        return 'ERROR TOKEN-ALREADY-IN-USE'

    # Vérification du fichier uploadé
    if 'file' in request.files:
        file: FileStorage = request.files['file']
        # if file.filename != '':
        if file:
            # Sauvegarde du fichier
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], token))
            # Récupération de la taille en octets du fichier uploadé
            file_size = os.stat(os.path.join(app.config['UPLOAD_FOLDER'], token)).st_size

            # Récupération du stockage utilisé par l'utilisateur
            used_size = client_manager.get_used_fileshare_size(existing_fileshare.owner_id)

            # Si le quota n'est pas atteint, on autorise l'upload, et on sauvegarde la taille dans la db
            if used_size + file_size <= node_config.config["user_storage"]:
                logger.debug(
                    token + "uploaded, owned by " + str(existing_fileshare.owner)
                    + ", size : " + str(file_size) + " bytes")
                existing_fileshare.size = file_size
                existing_fileshare.save()
                return 'OK UPLOAD-OK'
            # Si le quota est atteint, on interdit l'upload, on supprime le fichier stocké et le token dans la db
            else:
                logger.debug(
                    "Upload of " + token + " denied. No more space for user " + str(existing_fileshare.owner))
                existing_fileshare.delete_instance()
                os.remove(os.path.join(app.config['UPLOAD_FOLDER'], token))
                return 'ERROR QUOTA-ERROR'
    return 'ERROR UPLOAD-ERROR'


# Page de download (n'accepte que du GET)
@app.route('/download/<token>')
def download(token):
    # Après le téléchargement, on supprime le fichier et le token associé
    @after_this_request
    def delete_file(response):
        try:
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], token))
        except FileNotFoundError:
            pass
        return response

    # Récupération du token d'upload, et suppression
    existing_fileshare: FileShareModel = FileShareModel.get_or_none(FileShareModel.token == token)
    if not existing_fileshare:
        logger.debug(token + " download failed as token not found")
        return 'ERROR TOKEN-NOT-FOUND'
    else:
        existing_fileshare.delete_instance()
    # On retourne le fichier au client
    logger.debug(token + " file downloaded and removed from node")
    return send_from_directory(directory=os.path.join(app.config["UPLOAD_FOLDER"]), filename=token)


def start():
    logger.info("Starting file sharing server on " + node_config.config["client_listen_ip"] + ":37420")
    app.run(host=node_config.config["client_listen_ip"], port='37420', ssl_context='adhoc')
