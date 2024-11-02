from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from pymongo import MongoClient
from bson import ObjectId
import json
import os
import requests

app = Flask(__name__)
CORS(app)

# Configuration de la connexion à MongoDB
mongo_uri = "mongodb://localhost:27017"
client = MongoClient(mongo_uri)
db = client['cookie_awareness']
users_collection = db['users']

# Charger les clés API
def load_api_keys():
    try:
        with open(os.path.join('ressources', 'api.json'), 'r') as f:
            api_data = json.load(f)
            return api_data['apiKey'], api_data['whoIs']
    except Exception as e:
        print(f"Erreur de chargement de la clé API : {e}")
        return None, None

api_key, who_is_api_key = load_api_keys()

# Fonction utilitaire pour convertir ObjectId en chaîne de caractères
def convert_objectid_to_str(doc):
    if isinstance(doc, list):
        return [convert_objectid_to_str(d) for d in doc]
    if '_id' in doc:
        doc['_id'] = str(doc['_id'])
    return doc

@app.route('/')
def index():
    return send_from_directory('public', 'index.html')

# Route pour traiter et sauvegarder les données des utilisateurs
@app.route('/update-db', methods=['POST'])
def update_db():
    user = request.json
    ip_address = request.remote_addr

    ip_info_url = f'https://ipinfo.io/{ip_address}/json?token={api_key}'
    ip_info = requests.get(ip_info_url).json()

    user.update({
        "ipAddress": ip_address,
        "location": {
            "city": ip_info.get("city"),
            "region": ip_info.get("region"),
            "country": ip_info.get("country"),
            "postal": ip_info.get("postal"),
            "org": ip_info.get("org"),
            "location": ip_info.get("loc")
        }
    })

    whois_url = f'https://www.whoisxmlapi.com/whoisserver/WhoisService?apiKey={who_is_api_key}&domainName={ip_address}&outputFormat=JSON'
    whois_data = requests.get(whois_url).json()
    user["whoisData"] = whois_data

    # Sauvegarder l'utilisateur dans la base de données MongoDB
    users_collection.insert_one(user)
    user = convert_objectid_to_str(user)

    return jsonify({"status": "success", "user_data": user}), 201

# Route pour charger tous les utilisateurs
@app.route('/load', methods=['GET'])
def load_users():
    users = list(users_collection.find({}))
    users = convert_objectid_to_str(users)
    return jsonify(users), 200

# Route pour envoyer des données spécifiques d'un utilisateur
@app.route('/send/<int:user_id>', methods=['GET'])
def send_user(user_id):
    user = users_collection.find_one({"id": user_id})
    if user:
        user = convert_objectid_to_str(user)
        return jsonify(user), 200
    else:
        return jsonify({"error": "User not found"}), 404

# Route pour sauvegarder de nouvelles données utilisateur
@app.route('/save', methods=['POST'])
def save_user():
    new_user = request.json
    users_collection.insert_one(new_user)
    new_user = convert_objectid_to_str(new_user)
    return jsonify({"status": "success", "user_data": new_user}), 201

# Route pour supprimer un utilisateur
@app.route('/delete/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    result = users_collection.delete_one({"id": user_id})
    if result.deleted_count > 0:
        return jsonify({"status": "success", "message": "User deleted"}), 200
    else:
        return jsonify({"error": "User not found"}), 404

# Route pour modifier un utilisateur
@app.route('/update/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    updated_data = request.json
    result = users_collection.update_one({"id": user_id}, {"$set": updated_data})
    if result.modified_count > 0:
        updated_user = users_collection.find_one({"id": user_id})
        updated_user = convert_objectid_to_str(updated_user)
        return jsonify({"status": "success", "user_data": updated_user}), 200
    else:
        return jsonify({"error": "User not found or no change detected"}), 404

# Route pour trier les utilisateurs
@app.route('/sort', methods=['GET'])
def sort_users():
    sort_field = request.args.get('field', 'id')
    sort_order = request.args.get('order', 'asc')

    sort_direction = 1 if sort_order == 'asc' else -1
    sorted_users = list(users_collection.find({}).sort(sort_field, sort_direction))
    sorted_users = convert_objectid_to_str(sorted_users)

    return jsonify(sorted_users), 200

# Route pour obtenir le nombre d'utilisateurs
@app.route('/count-users', methods=['GET'])
def count_users():
    user_count = users_collection.count_documents({})
    return jsonify({"user_count": user_count}), 200

# Servir les fichiers statiques (HTML, CSS, JS)
@app.route('/<path:path>')
def static_files(path):
    return send_from_directory('public', path)

# Lancer l'application
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000, debug=True)