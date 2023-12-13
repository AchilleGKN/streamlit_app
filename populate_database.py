import pandas as pd
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import sessionmaker, declarative_base

# Création de la connexion à la base de données
engine = create_engine("sqlite:///planning.db")
Session = sessionmaker(bind=engine)
session = Session()

Base = declarative_base()

class Projet(Base):
    __tablename__ = "Projets"

    projet_id = Column(Integer, primary_key=True)
    categorie = Column(String)
    titre_projet = Column(String)
    descriptif = Column(String)
    date_debut = Column(DateTime)
    date_fin = Column(DateTime)
    code_agence = Column(String, ForeignKey("Agences.code_agence"))

class Agence(Base):
    __tablename__ = "Agences"

    agence_id = Column(Integer, primary_key=True)
    code_agence = Column(String)
    longitude = Column(Float)
    latitude = Column(Float)

# Création de la table "Projets" et "Agences" s'ils n'existent pas déjà
Base.metadata.create_all(engine)

# Lecture du DataFrame d'agences
df_agences = pd.read_excel("localisation_agences.xlsx")

# Insertion des données d'agences dans la table "Agences"
for index, row in df_agences.iterrows():
    nouvelle_agence = Agence(code_agence=row['agence'], longitude=row['longitude'], latitude=row['latitude'])
    session.add(nouvelle_agence)
    session.commit()

date_debut = datetime(1996, 6, 1)
date_fin = datetime(2023, 6, 1)

# Création et ajout de la tâche dans la table "Projets"
nouvelle_tache = Projet(categorie="test", titre_projet="Test", descriptif="Ceci est un test", date_debut=date_debut, date_fin=date_fin, code_agence="72")
session.add(nouvelle_tache)
session.commit()

# Fermeture de la session
session.close()