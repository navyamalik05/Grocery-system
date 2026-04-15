import sqlite3
import os
import json
import requests
import hashlib
import hmac
import base64
from flask import Flask, request, jsonify
app = Flask(__name__)
db_name = "logs.db"
sql_file = "logging.sql"
db_flag = False

user_management_ms_URL = "http://username:5000"       #url for username management microservice


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
		
		try:
			decoded  = base64.urlsafe_b64decode(PL_part)
			payload = json.loads(decoded.decode('utf-8'))
			return payload.get('username')

		except Exception as e:
			return None
		
	except Exception as e:
		return None



def JWTverification(jwt_token):
	try:
		username = get_username_from_JWT(jwt_token)
		if not username:
			return None
		
		ISemp = check_user_is_employee(jwt_token)
		if not ISemp:
			return {"username": username, "employee": False}
			
		return {"username": username, "employee": ISemp.get("ISemployee", False)}

	except Exception as e:
		return None


def log_event(event, username, product = None):
    #Logging event to the database
	conn = get_db()
	cursor = conn.cursor()
	cursor.execute("INSERT INTO logs (event, username, product) VALUES (?, ?, ?)",(event, username, product))
	conn.commit()
	conn.close()


@app.route('/log', methods=['POST'])
def log():
	if request.method == 'GET':
		info = request.args
	else:  # POST
		info = request.json if request.is_json else request.form

	event = info.get('event')
	username = info.get('username')
	product = info.get('product', None)
	
	if not username or not event:
		return jsonify({"status": 0, 'data': 'NULL'})
	
	log_event(event, username, product)
	return jsonify({"status": 1, 'data': 'Success'})



def check_user_is_employee(jwt_token):
	#using user managemnt microserive to check if a user is an employee or not.
	try:
		headers = {'Authorization': jwt_token}
		ans = requests.post(f"{user_management_ms_URL}/check_employee", headers=headers)
		output = ans.json()
		if output.get('status') == 1:
			return {'username': output.get('username'),'is_employee': output.get('is_employee', False)}   # Return a dictionary with username and employee status
		else:
			return None
	
	except Exception as e:
		return None




@app.route('/view_log', methods=['GET'])
def view_log():
	jwt_token = request.headers.get('Authorization')
	if not jwt_token:
		return jsonify({"status": 2, 'data' : 'NULL'})
	
	jwt = JWTverification(jwt_token)
	if not jwt:
		return jsonify({"status": 2, 'data' : 'NULL'})
		 
	user = jwt['username']
	ISemployee = jwt['employee']
	
	info= request.args
	username = info.get('username')
	product = info.get('product')
	
	if product and not ISemployee:
		return jsonify({"status": 3, 'data': 'NULL'})
		
	if username and username != user and not ISemployee:
		return jsonify({"status": 3, 'data': 'NULL'})
		
	conn = get_db()
	cursor = conn.cursor()
	
	if username:
		cursor.execute('SELECT event, username, product FROM logs WHERE username = ? ORDER BY ID', (username,))
	
	elif product:
		cursor.execute('SELECT event, username, product FROM logs WHERE product = ? ORDER BY ID', (product,))
	
	else:
		cursor.execute("SELECT event, username, product FROM logs ORDER BY ID")
	
	curr = cursor.fetchall()
	conn.close()

	data={}
	for i, (e, u, p) in enumerate(curr):
		print(e,u,p)
		data[i+1] = {
			"event": e,
			"user": u,
			"name": p
		}
	
	return jsonify({"status": 1, "data": data})


@app.route('/modified_last', methods=['GET'])
def modified_last():

	info = request.args
	Pname = info.get('product_name')
	if not Pname:
		return jsonify({'status': 2, 'data' : 'NULL'})
	
	try:
		conn = get_db()
		cursor = conn.cursor()
		
		cursor.execute("SELECT username FROM logs WHERE product = ? AND event IN ('product_creation','product_edit') ORDER BY timestamp DESC LIMIT 1", (Pname,))
		curr = cursor.fetchone()
		conn.close()
		
		if curr:
			return jsonify({'status' : 1, 'last_mod': curr[0]})
		else:
			return jsonify({'status':2, 'last_mod': None})
	
	except Exception as e:
		return jsonify({'status': 2, 'data' : 'NULL'})


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
    import requests  # Importing here to remove circular import issues
    app.run(host='0.0.0.0', port=5000, debug=True)
	
