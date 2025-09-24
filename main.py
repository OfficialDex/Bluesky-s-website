from flask import Flask, render_template
import htmlmin
import rcssmin
import rjsmin
import re

app = Flask(__name__)

def minify(html):
    html = htmlmin.minify(html, remove_comments=True, remove_empty_space=True)
    html = re.sub(r"<style.*?>(.*?)</style>", lambda x: f"<style>{rcssmin.cssmin(x.group(1))}</style>", html, flags=re.DOTALL)
    html = re.sub(r"<script.*?>(.*?)</script>", lambda x: f"<script>{rjsmin.jsmin(x.group(1))}</script>", html, flags=re.DOTALL)
    return html

@app.route("/")
def home():
    raw = render_template("home.html")
    return minify(raw)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
