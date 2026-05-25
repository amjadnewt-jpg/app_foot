from flask import Flask, render_template, request, redirect, url_for, session, flash
from models import db, User, Club, Tribune, Match, Billet, Competition
from config import Config
from datetime import datetime
from flask_mail import Mail, Message
import os


from flask import request



app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)
mail = Mail(app)

import stripe
stripe.api_key = app.config['STRIPE_SECRET_KEY']
endpoint_secret = os.environ.get("STRIPE_WEBHOOK_SECRET")


# Création de la base et d'un club par défaut
with app.app_context():
    db.create_all()
    # Ajout de quelques compétitions par défaut
    if not Competition.query.first():
        competitions = [
            Competition(nom="Ligue 1", pays="France"),
            Competition(nom="Coupe de France", pays="France"),
            Competition(nom="Premier League", pays="Angleterre"),
            Competition(nom="La Liga", pays="Espagne"),
            Competition(nom="Ligue des Champions", pays="International"),
            Competition(nom="Europa League", pays="International")
        ]
        db.session.add_all(competitions)
        
    if not Club.query.first():
        db.session.add(Club(nom="Paris Saint-Germain", pays="France"))
        db.session.commit()

@app.route('/')
def home():

    user_id = session.get('user_id')

    if not user_id:
        return redirect(url_for('login'))

    user = User.query.get(user_id)

    if not user:
        return redirect(url_for('login'))

    # 🔥 ADMIN
    if user.is_admin == True:
        return render_template(
            'admin_dashboard.html',
            user=user
        )

    # 🔥 CLIENT
    maintenant = datetime.now().strftime('%Y-%m-%dT%H:%M')

    club_search = request.args.get("club_search", "")
    competition_id = request.args.get("competition_id", "")

    query = Match.query.filter(Match.date >= maintenant)

    # 🔥 filtre club
    if club_search:
        query = query.join(Club).filter(
            Club.nom.ilike(f"%{club_search}%")
        )

    # 🔥 filtre compétition
    if competition_id:
        query = query.filter(
            Match.competition_id == int(competition_id)
        )

    tous_les_matchs = query.all()
    competitions = Competition.query.all()

    return render_template(
        'client_dashboard.html',
        user=user,
        matchs=tous_les_matchs,
        competitions=competitions,
        selected_club_search=club_search,
        selected_competition=competition_id
    )


@app.route('/login', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':

        nom = request.form.get('username')
        mdp = request.form.get('password')

        user = User.query.filter_by(username=nom).first()

        if user and user.password == mdp:

            session['user_id'] = user.id

            # 🔥 ADMIN
            if user.is_admin == True:
                return render_template(
                    'admin_dashboard.html',
                    user=user
                )

            # 🔥 CLIENT
            maintenant = datetime.now().strftime('%Y-%m-%dT%H:%M')

            tous_les_matchs = Match.query.filter(
                Match.date >= maintenant
            ).all()

            competitions = Competition.query.all()

            return render_template(
                'client_dashboard.html',
                user=user,
                matchs=tous_les_matchs,
                competitions=competitions,
                selected_club_search="",
                selected_competition=""
            )

        flash("Identifiants incorrects", "error")

    return render_template('login.html') 

@app.route('/register/client', methods=['GET', 'POST'])
def register_client():
    if request.method == 'POST':
        nom = request.form.get('username')
        mail = request.form.get('email')
        mdp = request.form.get('password')

        existe = User.query.filter(
            (User.username == nom) | (User.email == mail)
        ).first()

        if existe:
            flash("Username ou email déjà utilisé", "error")
            return redirect(url_for('register_client'))

        nouveau = User(username=nom, email=mail, password=mdp, is_admin=False)
        db.session.add(nouveau)
        db.session.commit()

        # ✅ AJOUT ICI (IMPORTANT)
        envoyer_email(nouveau.email, nouveau.username)

        flash("Compte créé avec succès ! Connectez-vous.", "success")
        return redirect(url_for('login'))

    return render_template('register_client.html')
    
        
        

    return render_template('register_client.html')
    print("EMAIL TEST EN COURS")
    
    
@app.route('/register/admin', methods=['GET', 'POST'])
def register_admin():
    if request.method == 'POST':
        nom = request.form.get('username')
        mail = request.form.get('email')
        mdp = request.form.get('password')
        nom_club = request.form.get('club_name')
        pays_club = request.form.get('pays')

        club = Club.query.filter_by(nom=nom_club).first()
        if not club:
            club = Club(nom=nom_club, pays=pays_club)
            db.session.add(club)
            db.session.flush()

        # 🔴 CREATE STRIPE ACCOUNT
        compte = stripe.Account.create(
            type="express",
            country="FR",
            email=mail
        )

        # 🟢 CREATE ONBOARDING LINK (TON CODE ICI)
        link = stripe.AccountLink.create(
            account=compte.id,
            refresh_url=url_for('home', _external=True),
            return_url=url_for('home', _external=True),
            type="account_onboarding",
        )

        nouveau = User(
            username=nom,
            email=mail,
            password=mdp,
            is_admin=True,
            club_id=club.id,
            stripe_account_id=compte.id
        )

        db.session.add(nouveau)
        db.session.commit()

        return redirect(link.url)

    return render_template('register_admin.html')

def envoyer_email(destinataire, username):
    msg = Message(
        "Bienvenue sur Stadium Manager",
        recipients=[destinataire]
    )
    msg.body = f"Bonjour {username}, merci pour votre inscription !"
    
    mail.send(msg)


# 🔥 AJOUTE ICI ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓

import qrcode
import os

def generate_qr(data, filename):
    base_dir = os.path.dirname(os.path.abspath(__file__))

    folder = os.path.join(base_dir, "static", "qrcodes")

    # 🔥 crée le dossier SI il existe pas
    os.makedirs(folder, exist_ok=True)

    path = os.path.join(folder, filename)

    qr = qrcode.make(data)
    qr.save(path)

    return path


def envoyer_billet_email(destinataire, qr_filename):
    msg = Message(
        "🎟️ Ton billet",
        recipients=[destinataire]
    )

    msg.body = "Voici ton billet avec ton QR code"

    path = os.path.join("static", "qrcodes", qr_filename)

    with open(path, "rb") as fp:
        msg.attach(qr_filename, "image/png", fp.read())

    mail.send(msg)

@app.route('/add_tribune', methods=['POST'])
def add_tribune():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    if not user or not user.is_admin:
        return redirect(url_for('home'))
    
    nom = request.form.get('nom')
    capa = request.form.get('capacite')
    prix = request.form.get('prix')
    
    if nom and capa and prix:
        nouvelle_tribune = Tribune(
            nom=nom, 
            capacite=int(capa), 
            prix=float(prix), 
            club_id=user.club_id
        )
        db.session.add(nouvelle_tribune)
        db.session.commit()
        flash("Tribune ajoutée avec succès !", "success")
    
    return redirect(url_for('home'))

@app.route('/delete_tribune/<int:id>')
def delete_tribune(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    tribune = Tribune.query.get(id)
    
    # Sécurité : On vérifie que la tribune existe ET qu'elle appartient bien au club de l'admin
    if tribune and user and user.is_admin and tribune.club_id == user.club_id:
        db.session.delete(tribune)
        db.session.commit()
        flash("Tribune supprimée !", "success")
    
    return redirect(url_for('home'))

@app.route('/create_match')
def create_match():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    if not user or not user.is_admin:
        return redirect(url_for('home'))
    
    # On récupère tous les clubs pour la barre de recherche (sauf le nôtre)
    tous_les_clubs = Club.query.filter(Club.id != user.club_id).all()
    # On récupère les tribunes de l'admin
    ses_tribunes = Tribune.query.filter_by(club_id=user.club_id).all()
    
    # On récupère les compétitions éligibles (Pays du club + International)
    competitions = Competition.query.filter(
        (Competition.pays == user.club.pays) | (Competition.pays == "International")
    ).all()
    
    return render_template('create_match.html', user=user, clubs=tous_les_clubs, tribunes=ses_tribunes, competitions=competitions)

@app.route('/add_match', methods=['POST'])
def add_match():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    if not user or not user.is_admin:
        return redirect(url_for('home'))
    
    adversaire = request.form.get('adversaire')
    date_str = request.form.get('date')
    lieu = request.form.get('lieu')
    tribunes_ids = request.form.getlist('tribunes')
    competition_id = request.form.get('competition_id')
    
    # CONDITION 1 : On vérifie que TOUT est rempli
    if not adversaire or not date_str or not lieu or not tribunes_ids or not competition_id:
        flash("Erreur : Tous les champs doivent être remplis (n'oubliez pas la compétition et les tribunes !)", "error")
        return redirect(url_for('create_match'))
    
    # CONDITION 2 : On vérifie que la date n'est pas dans le passé
    date_objet = datetime.strptime(date_str, '%Y-%m-%dT%H:%M')
    maintenant = datetime.now()
    
    if date_objet < maintenant:
        flash("Erreur : Vous ne pouvez pas programmer un match dans le passé !", "error")
        return redirect(url_for('create_match'))
    
    nouveau_match = Match(
        adversaire=adversaire, 
        date=date_str, 
        lieu=lieu,
        club_id=user.club_id,
        competition_id=competition_id
    )
    
    for t_id in tribunes_ids:
        tribune = Tribune.query.get(t_id)
        if tribune:
            nouveau_match.tribunes_ouvertes.append(tribune)
            
    db.session.add(nouveau_match)
    db.session.commit()
    flash("Match programmé avec succès !", "success")
    return redirect(url_for('home'))

@app.route('/delete_match/<int:id>')
def delete_match(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    match = Match.query.get(id)
    
    if match and user and user.is_admin and match.club_id == user.club_id:
        db.session.delete(match)
        db.session.commit()
        flash("Match supprimé !", "success")
    
    return redirect(url_for('home'))

@app.route('/reserver/<int:match_id>')
def reserver(match_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    match = Match.query.get(match_id)

    if not match:
        flash("Match introuvable", "error")
        return redirect(url_for('home'))

    places_restantes = {
        tribune.id: tribune.capacite - Billet.query.filter_by(
            match_id=match.id,
            tribune_id=tribune.id
        ).count()
        for tribune in match.tribunes_ouvertes
    }

    return render_template(
        'reserver.html',
        user=user,
        match=match,
        places=places_restantes
    )


@app.route('/confirmer_achat', methods=['POST'])
def confirmer_achat():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    match = Match.query.get(request.form.get('match_id'))
    if not match:
        return redirect(url_for('home'))

    admin = User.query.filter_by(club_id=match.club_id, is_admin=True).first()
    if not admin or not admin.stripe_account_id:
        return "Erreur : compte Stripe non configuré pour ce club", 400

    tribunes_data = {}
    line_items = []
    total_centimes = 0

    for tribune in match.tribunes_ouvertes:
        qty = int(request.form.get(f'qty_{tribune.id}') or 0)

        if qty <= 0:
            continue

        prix_centimes = int(tribune.prix * 100)

        tribunes_data[tribune.id] = qty
        total_centimes += prix_centimes * qty

        line_items.append({
            'price_data': {
                'currency': 'eur',
                'product_data': {
                    'name': f"{match.adversaire} - {tribune.nom}",
                },
                'unit_amount': prix_centimes,
            },
            'quantity': qty,
        })

    if not line_items:
        flash("Sélectionne au moins un billet", "error")
        return redirect(url_for('reserver', match_id=match.id))

    session_stripe = stripe.checkout.Session.create(
        payment_method_types=['card'],
        line_items=line_items,
        mode='payment',
        payment_intent_data={
            "application_fee_amount": int(total_centimes * 0.10),
            "transfer_data": {
                "destination": admin.stripe_account_id
            }
        },
        success_url=url_for('success', _external=True) + f"?match_id={match.id}",
        cancel_url=url_for('reserver', match_id=match.id, _external=True),
        metadata={
            "match_id": str(match.id),
            "user_id": str(session['user_id']),
            "tribunes": str(tribunes_data)
        }
    )

    return redirect(session_stripe.url)


@app.route('/stripe/webhook', methods=['POST'])
def stripe_webhook():

    import uuid
    import ast

    try:
        event = stripe.Webhook.construct_event(
            request.data,
            request.headers.get('Stripe-Signature'),
            endpoint_secret
        )

    except Exception as e:
        print("❌ ERROR WEBHOOK:", e)
        return "error", 400

    if event['type'] != 'checkout.session.completed':
        return "ok", 200

    session_data = event['data']['object']
    session_id = session_data['id']

    # 🔥 anti doublon
    already_done = Billet.query.filter_by(
        stripe_session_id=session_id
    ).first()

    if already_done:
        print("⚠️ Déjà traité")
        return "ok", 200

    match = Match.query.get(
        int(session_data['metadata']['match_id'])
    )

    user = User.query.get(
        int(session_data['metadata']['user_id'])
    )

    tribunes = ast.literal_eval(
        session_data['metadata']['tribunes']
    )

    if not match or not user:
        return "error", 400

    emails_a_envoyer = []

    for tribune_id, qty in tribunes.items():

        tribune = Tribune.query.get(int(tribune_id))

        if not tribune:
            continue

        for _ in range(qty):

            qr_token = str(uuid.uuid4())
            filename = f"{qr_token}.png"

            generate_qr(qr_token, filename)

            billet = Billet(
                user_id=user.id,
                match_id=match.id,
                tribune_id=tribune.id,
                stripe_session_id=session_id,
                qr_code=qr_token,
                is_used=False
            )

            db.session.add(billet)

            emails_a_envoyer.append(filename)

    # 🔥 commit AVANT emails
    db.session.commit()

    # 🔥 emails après commit
    for filename in emails_a_envoyer:
        envoyer_billet_email(user.email, filename)

    print("✅ OK PAYEMENT + QR + EMAIL")

    return "ok", 200

@app.route('/success')
def success():
    match_id = request.args.get('match_id')

    match = Match.query.get(match_id)

    if not match:
        return redirect(url_for('home'))

    return render_template("success.html", match=match)










import requests

@app.route('/scan/<qr_token>')
def scan_qr(qr_token):
    billet = Billet.query.filter_by(qr_code=qr_token).first()

    if not billet:
        return "❌ QR invalide"

    if billet.is_used:
        return "⚠️ Déjà utilisé"

    # 🔥 MARQUE UTILISÉ
    billet.is_used = True
    db.session.commit()

    # 🔥 OUVRIR LE PORTIQUE (RASPBERRY)
    try:
        requests.get("http://192.168.0.189:5001/open")
    except:
        print("Erreur connexion Raspberry")

    return "✅ Accès autorisé"



@app.route('/scanner')
def scanner():
    return render_template("scanner.html")

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))




@app.route('/check/<qr_token>/<int:club_id>')
def check(qr_token, club_id):

    billet = Billet.query.filter_by(qr_code=qr_token).first()

    if not billet:
        return {"status": "invalid"}

    if billet.is_used:
        return {"status": "used"}

    # 🔥 vérif club
    if billet.match.club_id != club_id:
        return {"status": "wrong_club"}

    # ✅ OK → on valide le billet
    billet.is_used = True
    db.session.commit()

    return {"status": "ok"}

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=3000, debug=True)















