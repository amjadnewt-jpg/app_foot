from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Club(db.Model):
    __tablename__ = 'clubs' # On donne un nom clair à la table
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    pays = db.Column(db.String(50), default="France") # Pays du club

class Competition(db.Model):
    __tablename__ = 'competitions'
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    pays = db.Column(db.String(50), nullable=False) # Nom du pays ou "International"

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(80), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    club_id = db.Column(db.Integer, db.ForeignKey('clubs.id'), nullable=True)
    club = db.relationship('Club', backref='membres')
    stripe_account_id = db.Column(db.String(255), nullable=True)

class Tribune(db.Model):
    __tablename__ = 'tribunes'
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    capacite = db.Column(db.Integer, nullable=False)
    prix = db.Column(db.Float, nullable=False)
    club_id = db.Column(db.Integer, db.ForeignKey('clubs.id'), nullable=False)
    club = db.relationship('Club', backref='tribunes')

# Table d'association pour l'accès aux tribunes par match
match_tribunes = db.Table('match_tribunes',
    db.Column('match_id', db.Integer, db.ForeignKey('matchs.id'), primary_key=True),
    db.Column('tribune_id', db.Integer, db.ForeignKey('tribunes.id'), primary_key=True)
)

class Match(db.Model):
    __tablename__ = 'matchs'
    id = db.Column(db.Integer, primary_key=True)
    adversaire = db.Column(db.String(100), nullable=False)
    date = db.Column(db.String(50), nullable=False)
    lieu = db.Column(db.String(20), default="Domicile") # Domicile ou Extérieur
    club_id = db.Column(db.Integer, db.ForeignKey('clubs.id'), nullable=False)
    club = db.relationship('Club', backref='matchs')
    
    # Lien avec la compétition
    competition_id = db.Column(db.Integer, db.ForeignKey('competitions.id'), nullable=True)
    competition = db.relationship('Competition', backref='matchs')
    
    # Relation avec les tribunes ouvertes pour ce match
    tribunes_ouvertes = db.relationship('Tribune', secondary=match_tribunes, backref='matchs_prevus')

class Billet(db.Model):
    __tablename__ = 'billets'
    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    match_id = db.Column(db.Integer, db.ForeignKey('matchs.id'), nullable=False)
    tribune_id = db.Column(db.Integer, db.ForeignKey('tribunes.id'), nullable=False)

    stripe_session_id = db.Column(db.String) # 🔥 AJOUT IMPORTANT

    user = db.relationship('User', backref='mes_billets')
    match = db.relationship('Match', backref='billets_vendus')
    tribune = db.relationship('Tribune', backref='reservations')
    qr_code = db.Column(db.String, unique=True)  # 🔥 IMPORTANT
    is_used = db.Column(db.Boolean, default=False)