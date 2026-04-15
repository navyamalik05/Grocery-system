import sqlite3
import os
import json
import requests
import hashlib
import hmac
import base64
from flask import Flask, request, jsonify

app = Flask(__name__)
db_name = "search.db"
sql_file = "product_searching.sql"
db_flag = False

product_management_ms_URL = "http://products:5000"     # url for product management microservice
logging_ms_URL = "http://logs:5000"     # url for logging microservice




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
		
		'''try:
			with open("key.txt",'r') as fp:
				key = fp.read().strip()
		except FileNotFoundError:
			raise Exception("key.txt file not found")
		
		result = f"{head_part}.{PL_part}".encode()
		resigned_part = hmac.new(key.encode('utf-8'), result, hashlib.sha256).hexdigest()
		
		if sign_part != resigned_part:
			return None'''
		
		
		decoded_bytes = base64.urlsafe_b64decode(PL_part)
		decoded_payload = json.loads(decoded_bytes.decode('utf-8'))
		return decoded_payload.get('username')
	
	except Exception as e:
		return None




def modified_last(product_name):
	try:
		val = requests.get(f"{logging_ms_URL}/modified_last?product_name={product_name}")
		data = val.json()
		if data.get('status') == 1:
			return data.get('last_mod')
		return None
	except Exception as e:
		return None



def log_to_service(event, username, product=None):
	"""Send a log event to the logging microservice"""
	try:
		log_service_url = "http://logs:5000/log"
		params = {"event": event, "username": username}
		
		if product:
			params["product"] = product
		
		response = requests.post(log_service_url, params=params)
		return response.json()
	
	except Exception as e:
		return None




@app.route('/search', methods=['GET'])
def search():
	jwt_token = request.headers.get('Authorization')
	if not jwt_token:
		return jsonify({"status": 2, "data": "NULL"})
	
	username = get_username_from_JWT(jwt_token)
	if not username:
		return jsonify({"status": 2, "data": "NULL"})

	info = request.args
	product_name = info.get('product_name')
	category = info.get('category')
	
	if not product_name and not category:
		log_to_service("search_invalid_params", username)
		return jsonify({"status": 3, "data": "NULL"})
	
	try:
		if category:
			try:
				val = requests.get(f"{product_management_ms_URL}/get_C_of_P",params={"category": category})
				data = val.json()
				if not isinstance(data, list) or len(data) == 0:
					return jsonify({"status": 3, "data": "NULL"})
		
				products = []
				for i in data:
					last = modified_last(i['product_name']) or  i.get("created_by", username)

					if not last:
						return jsonify({"status": 3, "data": "NULL"})

					item = {}
					item["product_name"] = i['product_name']
					item["price"] = i['price']
					item["category"] = i['category']
					item["last_mod"] = last
					
					products.append(item)          #appending items to the product list
				
				log_to_service("search", username, category)
				return jsonify({"status": 1, "data": products})
			
			except Exception as e:
				
				return jsonify({"status": 3, "data": "NULL"})
				

		elif product_name:
			try:
				log_to_service("search_by_product_attempt", username, product=product_name)
				val = requests.get(f"{product_management_ms_URL}/get_P", params={"name": product_name})
				data = val.json()

				if not isinstance(data, list) or len(data) == 0:
					log_to_service("search_by_product_no_results", username, product=product_name, results_count=0)
					return jsonify({"status": 3, "data": "NULL"})

				products = []
				for i in data:
					last = modified_last(i['product_name']) or i.get("created_by", username)

					if not last:
						return jsonify({"status": 3, "data": "NULL"})

					item = {}
					item["product_name"] = i['product_name']
					item["price"] = i['price']
					item["category"] = i['category']
					item["last_mod"] = last

					products.append(item)
				
				log_to_service("search", username, product_name) 
				return jsonify({"status": 1, "data": products})
				
			
			except Exception as e:
				log_to_service("search_by_product_error", username, product=product_name)
				return jsonify({"status": 3, "data": "NULL"})
        
	except Exception as e:
		event = "search_error"
		if category:
			log_to_service(event, username, product=None)
		else:
			log_to_service(event, username, product=product_name)
		return jsonify({"status": 3, "data": "NULL"})



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
	
