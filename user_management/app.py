import sqlite3
import os
import json
import requests
import hashlib
import hmac
import base64
from flask import Flask, request, jsonify

app = Flask(__name__)
db_name = "user.db"
sql_file = "user_management.sql"
db_flag = False



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



#Hashing password
def hashing_pswd(password, salt):
	encoded_pswd = (password + salt).encode()
	#print(hashlib.sha256(encoded_pswd).hexdigest())
	return hashlib.sha256(encoded_pswd).hexdigest()


def checking_password(pswd, username, fname, lname):
	low_pswd = pswd.lower()
	low_user = username.lower()
	low_fname = fname.lower()
	low_lname = lname.lower()
	special_char = " /\"'|^[]{}()<>+="
	if low_user in low_pswd or low_fname in low_pswd or low_lname in low_pswd:
		return False
	
	if not any(char.isupper() for char in pswd):
		return False

	if len(low_pswd) < 8:
		return False
	
	if ' ' in pswd:
		return False
	if any(ch in pswd for ch in special_char):
		return False

	return True

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


def base64url_encode(user_data):
	return base64.urlsafe_b64encode(json.dumps(user_data).encode()).decode()

def base64url_encode_JWT(user_data):
	json_str = json.dumps(user_data, separators=(',', ': '))
	return base64.urlsafe_b64encode(json.dumps(user_data).encode('utf-8')).decode('utf-8')


def JWT(username):
	try:
		with open("key.txt",'r') as fp:
			key = fp.read().strip()
	except FileNotFoundError:
		raise Exception("key.txt file not found")
		
	conn = get_db()
	cursor = conn.cursor()
	cursor.execute("SELECT employee FROM users_info WHERE username = ?", (username,))
	employee_status = bool(cursor.fetchone()[0])
	conn.close()
	
	header = base64url_encode_JWT({"alg": "HS256", "typ": "JWT"})
	payload = base64url_encode_JWT({"username": username})
	
	result = f"{header}.{payload}".encode()
	#key = "QZkRdigqi2iRe0DcfUnYYML7eZx2yKbC"
	signature = hmac.new(key.encode('utf-8'), result, hashlib.sha256).hexdigest() 
	
	# Creating a JWT token
	jwt_token = f"{header}.{payload}.{signature}"
	
	return jwt_token


#base64.urlsafe_b64encode(json.dumps(user_data).encode()).rstrip(b"=").decode()
#Encode bytes-like object s using the URL- and filesystem-safe alphabet, which substitutes - instead of + and _ instead of / in the standard Base64 alphabet, and return the encoded bytes. The result can still contain =.


def JWTverification(jwt_token):
	try:
		username = get_username_from_JWT(jwt_token)
		if username:
			conn = get_db()
			cursor = conn.cursor()
			cursor.execute("SELECT employee FROM users_info WHERE username = ?", (username,))
			result = cursor.fetchone()
			conn.close()
			
			if result:
				return {"username": username, "employee": bool(result[0])}
		
		else:
			return None
			
	except Exception as e:
		return None

def log_to_service(event, username, product = 'NULL'):
	"""Send a log event to the logging microservice"""
	try:
		log_service_url = "http://logs:5000/log"
		payload = {"event": event, "username": username}
		
		if product:
			payload["product"] = product or 'NULL'
		
		headers = {"Content-Type": "application/json"}
		response = requests.post(log_service_url, json=payload, headers=headers)
		return response.json()
	
	except Exception as e:
		print(f"Error logging event: {e}")
		return None







@app.route('/create_user', methods=['POST'])
def create_users():
	info = request.form
	fname = info.get('first_name')
	lname = info.get('last_name')
	username = info.get('username')
	email= info.get('email_address')
	employee = 1 if info.get('employee') == 'True' else 0
	pswd= info.get('password')
	salt = info.get('salt')
	
	if not all([fname, lname, username, email, pswd]):
		return {"status": 4, "pass_hash": "NULL"}

	hashing = hashing_pswd(pswd,salt)
	
	conn=get_db()
	cursor = conn.cursor()

	cursor.execute("SELECT username FROM users_info WHERE username = ?", (username,))
	ALLusername = cursor.fetchall()
	#print(ALLusername)
	if username in [i[0] for i in ALLusername]:
		log_to_service("user_creation_failed_username_exists", username, "user_management")
		return {"status": 2, "pass_hash": "NULL"}  # Incorrect username

	cursor.execute("SELECT email_address FROM users_info WHERE email_address  = ?", (email,))
	ALLemail = cursor.fetchall()
	if email in [x[0] for x in ALLemail]:
		log_to_service("user_creation_failed_uemail_exists", username, "user_management")
		return {"status": 3, "pass_hash": "NULL"}  # Incorrect email address
	
	if not checking_password(pswd,username, fname, lname):
		log_to_service("user_creation_failed_password_requirements", username, "user_management")
		return {"status": 4, "pass_hash": "NULL"}

	try:	
		cursor.execute('''INSERT INTO users_info(first_name, last_name, username, email_address, employee, password, salt) VALUES (?,?,?,?,?,?,?)''',(fname, lname, username, email, employee, hashing, salt))
		conn.commit()
		log_to_service("user_creation", username)
		return {"status": 1, "pass_hash": hashing}    #If everything is correct
	
	except Exception as e:
		log_to_service("user_creation_error", username, "user_management")
		return {"status": 4, "pass_hash": "NULL"}
	
	finally:
		conn.close()

	

@app.route('/login', methods=['POST'])
def user_login():
	info = request.form
	username = info.get('username')
	pswd= info.get('password')

	if not all([username, pswd]):
		return jsonify({"status": 4, "jwt": "NULL"})

	conn = get_db()
	cursor = conn.cursor()
	cursor.execute("SELECT username FROM users_info;")
	existing_usernames = cursor.fetchall()

	#Checking if the username exists.
	if username in [i[0] for i in existing_usernames]:
		cursor.execute("SELECT password, salt FROM users_info WHERE username = ?", (username,))
		password_data = cursor.fetchone()
		if password_data:
			DBpswd, salt = password_data
			hashed_input = hashing_pswd(pswd, salt)

			#If the password is same
			if hashed_input == DBpswd:
				jwt_token = JWT(username)
				log_to_service("login", username)
				conn.close()
				return jsonify({"status": 1, "jwt": jwt_token})
	
	log_to_service("login", username)
	conn.close()
	return jsonify({"status": 2, "jwt": "NULL"})



@app.route('/check_employee', methods=['POST'])
def check_employee():
	#checking if a user is an employee or not.
	jwt_token = request.headers.get('Authorization')
	if not jwt_token:
		log_to_service("employee_check_failed_no_jwt", "unknown", "user_management")
		return jsonify({"status": 2, "is_employee": False})
	
	username = get_username_from_JWT(jwt_token)

	if username:
		conn = get_db()
		cursor = conn.cursor()

		cursor.execute("SELECT employee FROM users_info WHERE username = ?", (username,))
		ret = cursor.fetchone()
		conn.close()

		if ret and ret[0] ==1:
			return jsonify({"status": 1, "is_employee": True})
		else:
			return jsonify({"status": 3, "is_employee": False})
	else:
		log_to_service("employee_check_failed_invalid_jwt", "unknown", "user_management")
		return jsonify({"status": 3, "is_employee": False})


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
	
