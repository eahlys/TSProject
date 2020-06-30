# noinspection DuplicatedCode
import logging

from peewee import *

"""
NodeDatabase contient l'ORM peewee, gestionnaire de la base de données du Node
"""

node_db: SqliteDatabase = SqliteDatabase('.config/db.sqlite')

logger = logging.getLogger("peewee")
# Désactivation du logging des requêtes SQL (logging.DEBUG pour réactiver, logging.INFO sinon)
logger.setLevel(logging.INFO)


class BaseModel(Model):
    class Meta:
        database = node_db


class LocalClientModel(BaseModel):
    identity = CharField(max_length=50, primary_key=True, unique=True)
    last_seen = BigIntegerField()


class ClientKeyModel(BaseModel):
    identity = CharField(max_length=50, primary_key=True, unique=True)
    public_key = CharField(max_length=450, unique=True)


class OfflineMessageModel(BaseModel):
    receiver = ForeignKeyField(model=LocalClientModel, backref="offline_messages")
    sender = CharField(max_length=50)
    timestamp = BigIntegerField()
    data = BlobField()


# Tables créées pour le projet base de données
class ForeignNodeModel(BaseModel):
    identity = CharField(max_length=50, primary_key=True, unique=True)
    ip_address = CharField(max_length=20)
    public_key = CharField(max_length=450)


class ClientLocalizationModel(BaseModel):
    identity = CharField(max_length=50, primary_key=True, unique=True)
    node = CharField(max_length=50)
    last_seen = BigIntegerField()


# Table de gestion du partage de fichier
class FileShareModel(BaseModel):
    token = CharField(max_length=50, primary_key=True, unique=True)
    owner = ForeignKeyField(model=LocalClientModel, backref="shared_files")
    size = BigIntegerField(null=True)
    timestamp = BigIntegerField()


node_db.create_tables([LocalClientModel])
node_db.create_tables([ClientKeyModel])
node_db.create_tables([OfflineMessageModel])
node_db.create_tables([ForeignNodeModel])
node_db.create_tables([ClientLocalizationModel])
node_db.create_tables([FileShareModel])
