from peewee import *

client_db: SqliteDatabase = SqliteDatabase('.config/db.sqlite')


class BaseModel(Model):
    class Meta:
        database = client_db


class ServerModel(BaseModel):
    address = CharField(unique=True, primary_key=True, max_length=50)
    public_key = CharField(max_length=450)


client_db.create_tables([ServerModel])
