import sqlite3
import os
import json
import requests
import hashlib
import hmac
import base64
from flask import Flask, request, jsonify

app = Flask(__name__)
db_name = "ordering.db"
sql_file = "ordering.sql"
db_flag = False

product_management_ms_URL = "http://products:5000"    # url for product management microservice
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


def P_info(product_name):
    try:
        val = requests.get(f"{product_management_ms_URL}/get_P", params = {"name": product_name})
        P_data = val.json()
        if not isinstance(P_data, list) or not P_data:
            return None
        return P_data[0]
    
    except Exception as e:
        return None


def storing(username, items, Tcost):
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("INSERT INTO orders (username, Tcost, date_of_order) VALUES (?, ?, CURRENT_TIMESTAMP)", (username, Tcost))
        ord_id = cursor.lastrowid 
        
        for i in items:
            cursor.execute("INSERT INTO order_items (IDorder, product_name, quantity) VALUES (?, ?, ?)", (ord_id, i['product'], i['quantity']))
        
        conn.commit()
        conn.close()
        
        return ord_id
    
    except Exception as e:
        return None


@app.route('/order', methods=['POST'])
def order():
    jwt_token = request.headers.get('Authorization')
    if not jwt_token:
        return jsonify({"status": 2, "cost": "NULL"})
    
    username = get_username_from_JWT(jwt_token)
    if not username:
        return jsonify({"status": 2, "cost": "NULL"})
    
    info = request.form
    r = info.get('order')
    if r is None:
        return jsonify({"status": 3, "cost": "NULL"})


    try:
        items = json.loads(r)
    
    except Exception as e:
        return jsonify({"status": 3, "cost": "NULL"})

    
    if not items or not isinstance(items, list) or len(items) == 0:
        return jsonify({"status": 3, "cost": "NULL"})
    
    #calculating total cost
    Tcost = 0.00
    for i in items:
        product_name = i.get('product')
        quantity = i.get('quantity')
        
        if not product_name or not quantity or not isinstance(quantity, int) or quantity <= 0:
            return jsonify({"status": 3, "cost": "NULL"})
        

        Pinfo = P_info(product_name)
        if not Pinfo:
            return jsonify({"status": 3, "cost": "NULL"})
        
        try:
            price = round(float(Pinfo.get('price', 0)),2)
        except:
            pice = 0.00
        Tcost += price * float(quantity)
    
    
    o_id = storing(username, items, Tcost)         # storing order
    if not o_id:
        return jsonify({"status": 3, "cost": "NULL"})
    
    return jsonify({"status": 1, "cost": f"{Tcost:.2f}"})
    



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
	
