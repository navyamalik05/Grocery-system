import sqlite3
import os
import json
import requests
import hashlib
import hmac
import base64
from flask import Flask, request, jsonify

app = Flask(__name__)
db_name = "products.db"
sql_file = "product_management.sql"
db_flag = False


user_management_ms_URL ="http://user:5000"  #url for user managemnet microservice


def create_db():
    conn = sqlite3.connect(db_name)
    
    with open(sql_file, 'r') as sql_startup:
    	init_db = sql_startup.read()
    cursor = conn.cursor()
    cursor.executescript(init_db)
    conn.commit()
    conn.close()
    global db_flag
    db_flag = True
    return conn

def get_db():
	if not db_flag:
		create_db()
	conn = sqlite3.connect(db_name)
	return conn

@app.route('/test_get/<post_id>', methods=(['GET']))
def test_get(post_id):
	result = {}
	result['numbers'] = request.args.get('numbers')
	result['post_id'] = post_id
	result['jwt'] = request.headers['Authorization']

	return json.dumps(result)


@app.route('/test_post', methods=(['POST']))
def test_post():
	result = request.form

	return result




def get_username_from_JWT(jwt_token):
	try:
		parts = jwt_token.split('.')
		if len(parts) != 3:
			return None
		
		#payload = parts[1]
		head_part,PL_part, sign_part = parts
		
		try:
			with open("key.txt",'r') as fp:
				key = fp.read().strip()
		except FileNotFoundError:
			raise Exception("key.txt file not found")
		
		result = f"{head_part}.{PL_part}".encode()
		resigned_part = hmac.new(key.encode('utf-8'), result, hashlib.sha256).hexdigest()
		
		if sign_part != resigned_part:
			return None
		
		try:
			decoded_bytes = base64.urlsafe_b64decode(PL_part)
			decoded_payload = json.loads(decoded_bytes.decode('utf-8'))
		except Exception as e:
			return None
		
		return decoded_payload.get('username')
	
	except Exception as e:
		return None




def check_user_is_employee(jwt_token):
	#using user managemnt microserive to check if a user is an employee or not.
	try:
		headers = {'Authorization': jwt_token}
		ans = requests.post(f"{user_management_ms_URL}/check_employee", headers=headers)
		output = ans.json()
		if output.get('status') == 1 and output.get("is_employee") is True:
			return True

	except Exception as e:
		return False




def log_to_service(event, username, product=None):
	"""Send a log event to the logging microservice"""
	try:
		log_service_url = "http://logs:5000/log"
		payload = {"event": event, "username": username}
		
		if product and product != "product_management":
			payload["product"] = product
		else:
			payload["product"] = 'NULL'

		
		headers = {"Content-Type": "application/json"}
		response = requests.post(log_service_url, json=payload, headers=headers)
		return response.json()
	
	except Exception as e:
		print(f"Error logging event: {e}")
		return None



@app.route('/create_product', methods=['POST'])
def create_product():
	jwt_token = request.headers.get('Authorization')
	if not jwt_token:
		log_to_service("product_creation_failed_no_jwt", "unknown", "product_management")
		return jsonify({"status": 2})
	
	username = get_username_from_JWT(jwt_token)
	if not username:
		log_to_service("product_creation_failed_invalid_jwt", "unknown", "product_management")
		return jsonify({"status": 2})

	if not check_user_is_employee(jwt_token):
		log_to_service("product_creation_failed_not_employee", username, "product_management")
		return jsonify({"status": 2}) 
	
	info = request.form
	name = info.get('name')
	price = info.get('price')
	category = info.get('category')
	
	if not all([name, price, category]):
		log_to_service("product_creation_failed_missing_fields", username, "product_management")
		return {"status": 2}
	
	try:
		conn = get_db()
		cursor = conn.cursor()

		cursor.execute("SELECT name FROM products_info WHERE name = ?", (name,))
		curr = cursor.fetchone()     #if product already exists
		if curr:
			conn.close()
			log_to_service("product_creation_failed_product_exists", username, name)
			return jsonify({"status": 2})
		
		cursor.execute("INSERT INTO products_info (name, price, category) VALUES (?, ?, ?)", (name, float(price), category))
		conn.commit()     # add products if they do not exist
		conn.close()
		log_to_service("product_creation", username, name)
		log_to_service("search", username, name)
		return jsonify({"status": 1})

	except Exception as e:
		log_to_service("product_creation_error", username, name)
		return jsonify({"status": 2})



@app.route('/edit_product', methods=['POST'])
def edit_product():
		jwt_token = request.headers.get('Authorization')
		if not jwt_token:
			log_to_service("product_edit_failed_no_jwt", "unknown", "product_management")
			return jsonify({"status": 2})
		
		username = get_username_from_JWT(jwt_token)
		if not username:
			log_to_service("product_creation_failed_invalid_jwt", "unknown", "product_management")
			return jsonify({"status": 2})

		if not check_user_is_employee(jwt_token):
			log_to_service("product_edit_failed_not_employee", username, "product_management")
			return jsonify({"status": 3}) 
	
		info = request.form
		name = info.get('name')

		if not name:
			log_to_service("product_edit_failed_no_product_name", username, "product_management")
			return jsonify({"status": 2})
	
		#only one can change at a time
		new_price = info.get("new_price")
		new_category = info.get('new_category') 

		if not new_price and not new_category:
			log_to_service("product_edit_failed_no_changes", username, name)
			return jsonify({"status": 2})
		
		try:
			conn = get_db()
			cursor = conn.cursor()

			cursor.execute("SELECT name from products_info WHERE name = ?", (name,))
			curr = cursor.fetchone()
			if not curr:      #product does not exist
				conn.close()
				log_to_service("product_edit_failed_product_not_found", username, name)
				return jsonify({"status": 2})
			
			if new_price:
				cursor.execute("UPDATE products_info SET price = ? WHERE name = ?", (float(new_price), name))
				conn.commit()
				conn.close()
				log_to_service("product_price_updated", username, name)
				return jsonify({"status": 1})
		
			
			if new_category:
				cursor.execute("UPDATE products_info SET category = ? WHERE name = ?", (new_category, name))
				conn.commit()
				conn.close()
				log_to_service("product_category_updated", username, name)
				return jsonify({"status": 1})
			
			
			conn.close()
			log_to_service("product_edit_failed_unknown_reason", username, name)
			return jsonify({"status": 2})

		except Exception as e:
			log_to_service("product_edit_error", username, name)
			return jsonify({"status": 2})


@app.route('/get_P', methods=['GET'])
def get_P():
	info = request.args
	name = info.get('name')
	
	jwt_token = request.headers.get('Authorization')
	username = get_username_from_JWT(jwt_token) if jwt_token else "anonymous"

	conn = get_db()
	cursor = conn.cursor()
	
	cursor.execute("SELECT name, price, category FROM products_info WHERE name = ?", (name,))
	curr = cursor.fetchone()
	conn.close()
	if curr:
		log_to_service("search", username, name)
		return jsonify([{"product_name": curr[0], "price": curr[1], "category": curr[2]}])
	
	log_to_service("search_not_found", username, name)
	return jsonify([])



@app.route('/get_C_of_P', methods=['GET'])
def get_C_of_P():
	info = request.args
	category = info.get('category')

	jwt_token = request.headers.get('Authorization')
	username = get_username_from_JWT(jwt_token) if jwt_token else "anonymous"
	
	conn = get_db()
	cursor = conn.cursor()
	
	cursor.execute("SELECT name, price, category FROM products_info WHERE category = ?", (category,))
	curr = cursor.fetchall()
	conn.close()
	log_to_service("category_search", username, category)
	return jsonify([{"product_name": c[0], "price": c[1], "category": c[2]} for c in curr])



@app.route('/clear', methods=['GET'])
def clear_db():
	conn = get_db()
	cursor = conn.cursor()
	if os.path.exists(db_name):
		conn.close()
		os.remove(db_name)
		global db_flag
		db_flag = False
		return "Database is cleared"
	conn.close()
	return "Database does not exist"


if __name__ == '__main__':
    import requests  # Importing here to avoid circular import issues
    app.run(host='0.0.0.0', port=5000, debug=True)
	


