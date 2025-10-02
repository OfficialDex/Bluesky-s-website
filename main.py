from flask import Flask, request, jsonify, Response, send_from_directory, send_file, render_template
import json, os, requests, ipaddress, threading, shutil
app = Flask(__name__)
DB_file = 'data.json'
plans_loc = 'plans'
scripts_loc = 'scripts'
scripts_order = ["main.js", "plan.js"]
READ_PASSWORD = "Ankur2703"
WRITE_PASSWORD = "Ankur0327"
os.makedirs(plans_loc, exist_ok=True)
os.makedirs(scripts_loc, exist_ok=True)
lock = threading.Lock()
if not os.path.exists(DB_file):
    with open(DB_file, 'w') as f: json.dump({}, f)
def check_password():
    pw = request.headers.get('X-Password') or request.args.get('password')
    if request.is_json and not pw:
        pw = request.json.get('password')
    return pw
def save_data(data):
    with lock:
        with open(DB_file, 'w') as f: json.dump(data, f, indent=2)
def load_data():
    with lock:
        with open(DB_file) as f: return json.load(f)
def is_public_ip(host):
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved: return False
        return True
    except:
        return True

app = Flask(__name__)

@app.route("/")
def home():
    return render_template("home.html")

@app.route('/backend', methods=['GET', 'POST'])
def backend():
    pw = check_password()
    if request.method == 'GET':
        if pw != READ_PASSWORD: return jsonify({"error":"unauthorized"}),401
        data = load_data()
        username = request.args.get('username')
        return jsonify(data[username]) if username and username in data else jsonify(data)
    if pw != WRITE_PASSWORD: return jsonify({"error":"unauthorized"}),401
    data = load_data()
    if 'Username' not in request.form and not request.is_json: return jsonify({"error":"Username missing"}),400
    body = {}
    if request.is_json: body = request.json
    else:
        for k in request.form: body[k]=request.form[k]
    username = body.get('Username')
    if not username: return jsonify({"error":"Username missing"}),400
    plan_path = None
    if 'plan' in request.files:
        plan_file = request.files['plan']
        plan_content = plan_file.read()
        try: json.loads(plan_content)
        except: return jsonify({"error":"plan file invalid JSON"}),400
        plan_path = os.path.join(plans_loc,f"{username}.json")
        with open(plan_path,'wb') as f:f.write(plan_content)
    elif 'plan' in body:
        plan_content = json.dumps(body['plan']) if not isinstance(body['plan'],str) else body['plan']
        try: json.loads(plan_content)
        except: return jsonify({"error":"plan invalid JSON"}),400
        plan_path = os.path.join(plans_loc,f"{username}.json")
        with open(plan_path,'w') as f:f.write(plan_content)
    record = {
        "Origin":body.get("Origin"),
        "Arrival":body.get("Arrival"),
        "Call sign":body.get("Call sign"),
        "Flight":body.get("Flight"),
        "Image":body.get("Image"),
        "Origin weather":body.get("Origin weather"),
        "Arrival weather":body.get("Arrival weather"),
        "Username":username,
        "plan":plan_path
    }
    data[username]=record
    save_data(data)
    target="https://www.geo-fs.com/geofs.php?v=3.9"
    url=f"{request.host_url}{username}?target={target}"
    url_alt=f"{request.host_url}{username}?={target}"
    return jsonify({"status":"created","username":username,"proxy_url":url,"proxy_url_alt":url_alt}),201
    
    
@app.route('/backend/<username>',methods=['PUT','DELETE'])
def modify(username):
    pw = check_password()
    if pw != WRITE_PASSWORD: return jsonify({"error":"unauthorized"}),401
    data = load_data()
    if username not in data: return jsonify({"error":"not found"}),404
    if request.method=='PUT':
        body=request.json if request.is_json else request.form.to_dict()
        new_username=body.get('Username',username)
        record=data.pop(username)
        record.update(body)
        record["Username"]=new_username
        if username!=new_username:
            old_plan=record.get("plan")
            if old_plan and os.path.exists(old_plan):
                new_plan=os.path.join(plans_loc,f"{new_username}.json")
                shutil.move(old_plan,new_plan)
                record["plan"]=new_plan
        data[new_username]=record
        save_data(data)
        target="https://www.geo-fs.com/geofs.php?v=3.9"
        url=f"{request.host_url}{new_username}?target={target}"
        url_alt=f"{request.host_url}{new_username}?={target}"
        return jsonify({"status":"updated","username":new_username,"proxy_url":url,"proxy_url_alt":url_alt})
    else:
        plan=data[username].get("plan")
        if plan and os.path.exists(plan):os.remove(plan)
        del data[username]
        save_data(data)
        return jsonify({"status":"deleted"})
        
        
@app.route('/<username>')
def proxy_user(username):
    data=load_data()
    if username not in data: return "User not found",404
    target=request.args.get('target') or request.args.get('=') or "https://www.geo-fs.com/geofs.php?v=3.9"
    try:
        parsed=requests.utils.urlparse(target)
        if not is_public_ip(parsed.hostname):return "Blocked target",400
        resp=requests.get(target)
        if 'text/html' not in resp.headers.get('content-type',''):return "Not HTML",400
        html=resp.text
        scripts_content=""
        bookmarklets=[]
        for fname in scripts_order:
            path=os.path.join(scripts_loc,fname)
            if os.path.exists(path):
                with open(path,'r',encoding='utf-8') as f:
                    content=f.read()
                cstrip=content.strip()
                if cstrip.startswith("javascript:"):
                    bm = cstrip[len("javascript:"):].strip()
                    bookmarklets.append(bm)
                else:
                    scripts_content+=content+"\n"
        bm_json = json.dumps(bookmarklets)
        injection=f"""
<script>
window.PROXY_USERNAME={json.dumps(username)};
window.PROXY_BOOKMARKLETS = {bm_json};
window.runProxyBookmarklet = function(i){{{{ try{{{{ (new Function(window.PROXY_BOOKMARKLETS[i]))(); }}}}catch(e){{{{console.error(e);}}}} }}};
(function(){{{{{scripts_content}}}}})();
</script>
"""
        overlay=f"""<div style="position:fixed;bottom:10px;right:10px;background:#000;color:#fff;padding:5px;border-radius:4px;z-index:2147483647;">Viewing as: {username}</div>"""
        modified_html=html.replace('</body>',overlay+injection+'</body>')
        return Response(modified_html,content_type='text/html')
    except Exception as e:
        return f"Failed to load target URL: {str(e)}",500
        
        
@app.route('/scripts/<path:filename>')
def serve_script(filename):
    return send_from_directory(scripts_loc,filename)
    
    
@app.route('/plan/<username>')
def get_plan_protected(username):
    pw = check_password()
    if pw != READ_PASSWORD:
        return jsonify({"error":"unauthorized"}), 401
    data = load_data()
    if username not in data:
        return jsonify({"error":"not found"}), 404
    plan_path = data[username].get("plan")
    if not plan_path or not os.path.exists(plan_path):
        return jsonify({"error":"no_plan"}), 404
    return send_file(plan_path, mimetype='application/json', as_attachment=True, download_name=f"{username}.json")
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
