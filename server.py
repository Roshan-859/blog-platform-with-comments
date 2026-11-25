#!/usr/bin/env python3
"""Small, dependency-free REST API and static server for The Daily Draft."""
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
import hashlib, hmac, json, os, secrets, sqlite3, time, uuid

ROOT = Path(__file__).parent
DB = ROOT / "blog.db"
SECRET = os.environ.get("BLOG_SECRET", "local-development-secret-change-me").encode()

def connect():
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    return db

def init_db():
    with connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL, password TEXT NOT NULL, created_at INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS posts(id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), title TEXT NOT NULL, body TEXT NOT NULL, created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS comments(id TEXT PRIMARY KEY, post_id TEXT NOT NULL REFERENCES posts(id) ON DELETE CASCADE, user_id TEXT NOT NULL REFERENCES users(id), body TEXT NOT NULL, created_at INTEGER NOT NULL);
        """)

def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    key = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=2**14, r=8, p=1).hex()
    return f"{salt}${key}"

def check_password(password, stored):
    salt, key = stored.split("$", 1)
    return hmac.compare_digest(password_hash(password, salt).split("$", 1)[1], key)

def token(user_id):
    raw = f"{user_id}:{int(time.time()) + 60*60*24*14}"
    sig = hmac.new(SECRET, raw.encode(), hashlib.sha256).hexdigest()
    return (raw + ":" + sig).encode().hex()

def token_user(value):
    try:
        raw = bytes.fromhex(value).decode()
        user_id, expiry, sig = raw.split(":")
        expected = hmac.new(SECRET, f"{user_id}:{expiry}".encode(), hashlib.sha256).hexdigest()
        if int(expiry) < time.time() or not hmac.compare_digest(sig, expected): return None
        return user_id
    except Exception: return None

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs): super().__init__(*args, directory=str(ROOT), **kwargs)
    def log_message(self, fmt, *args): print("[%s] %s" % (self.log_date_time_string(), fmt % args))
    def send_json(self, data, status=200):
        body=json.dumps(data).encode(); self.send_response(status); self.send_header("Content-Type","application/json; charset=utf-8"); self.send_header("Content-Length",str(len(body))); self.send_header("Cache-Control","no-store"); self.end_headers(); self.wfile.write(body)
    def body_json(self):
        try: return json.loads(self.rfile.read(int(self.headers.get("Content-Length",0)) or 0) or b"{}")
        except Exception: return {}
    def current_user(self):
        cookie=self.headers.get("Cookie","")
        session=next((x.strip().split("=",1)[1] for x in cookie.split(";") if x.strip().startswith("session=")),"")
        uid=token_user(session)
        if not uid: return None
        with connect() as db:
            row=db.execute("SELECT id,name,email FROM users WHERE id=?",(uid,)).fetchone()
            return dict(row) if row else None
    def require_user(self):
        user=self.current_user()
        if not user: self.send_json({"error":"Please sign in to continue."},401)
        return user
    def do_GET(self):
        path=urlparse(self.path).path
        if path.startswith("/api/"):
            if path=="/api/me": self.send_json({"user":self.current_user()}); return
            if path=="/api/posts":
                with connect() as db:
                    rows=db.execute("""SELECT p.*,u.name author,(SELECT COUNT(*) FROM comments c WHERE c.post_id=p.id) comment_count FROM posts p JOIN users u ON u.id=p.user_id ORDER BY p.created_at DESC""").fetchall()
                    self.send_json({"posts":[dict(r) for r in rows]})
                return
            if path.startswith("/api/posts/") and path.endswith("/comments"):
                pid=path.split("/")[3]
                with connect() as db:
                    rows=db.execute("SELECT c.*,u.name author FROM comments c JOIN users u ON u.id=c.user_id WHERE c.post_id=? ORDER BY c.created_at ASC",(pid,)).fetchall()
                    self.send_json({"comments":[dict(r) for r in rows]})
                return
            self.send_json({"error":"Not found"},404); return
        if path=="/": self.path="/index.html"
        return super().do_GET()
    def do_POST(self):
        path=urlparse(self.path).path; data=self.body_json()
        if path=="/api/register":
            name=str(data.get("name","")).strip()[:60]; email=str(data.get("email","")).strip().lower(); password=str(data.get("password", ""))
            if len(name)<2 or "@" not in email or len(password)<8: self.send_json({"error":"Enter a name, a valid email, and a password with at least 8 characters."},400); return
            uid=uuid.uuid4().hex
            try:
                with connect() as db: db.execute("INSERT INTO users VALUES(?,?,?,?,?)",(uid,name,email,password_hash(password),int(time.time())))
            except sqlite3.IntegrityError: self.send_json({"error":"An account with that email already exists."},409); return
            self.auth_response({"id":uid,"name":name,"email":email}); return
        if path=="/api/login":
            email=str(data.get("email","")).strip().lower(); password=str(data.get("password", ""))
            with connect() as db: row=db.execute("SELECT id,name,email,password FROM users WHERE email=?",(email,)).fetchone()
            if not row or not check_password(password,row["password"]): self.send_json({"error":"Email or password doesn’t match."},401); return
            self.auth_response({"id":row["id"],"name":row["name"],"email":row["email"]}); return
        if path=="/api/logout":
            body=json.dumps({"ok":True}).encode(); self.send_response(200); self.send_header("Content-Type","application/json; charset=utf-8"); self.send_header("Content-Length",str(len(body))); self.send_header("Set-Cookie","session=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0"); self.end_headers(); self.wfile.write(body); return
        user=self.require_user()
        if not user: return
        if path=="/api/posts":
            title=str(data.get("title","")).strip()[:140]; body=str(data.get("body","")).strip()
            if len(title)<3 or len(body)<20 or len(body)>20000: self.send_json({"error":"Add a title and at least 20 characters of story (up to 20,000)."},400); return
            pid=uuid.uuid4().hex; now=int(time.time())
            with connect() as db: db.execute("INSERT INTO posts VALUES(?,?,?,?,?,?)",(pid,user["id"],title,body,now,now))
            self.send_json({"ok":True,"id":pid},201); return
        if path.startswith("/api/posts/") and path.endswith("/comments"):
            pid=path.split("/")[3]; body=str(data.get("body","")).strip()
            if not body or len(body)>2000: self.send_json({"error":"Comments must be 1–2,000 characters."},400); return
            with connect() as db:
                if not db.execute("SELECT 1 FROM posts WHERE id=?",(pid,)).fetchone(): self.send_json({"error":"Post not found."},404); return
                db.execute("INSERT INTO comments VALUES(?,?,?,?,?)",(uuid.uuid4().hex,pid,user["id"],body,int(time.time())))
            self.send_json({"ok":True},201); return
        self.send_json({"error":"Not found"},404)
    def auth_response(self,user):
        body=json.dumps({"user":user}).encode(); self.send_response(200); self.send_header("Content-Type","application/json; charset=utf-8"); self.send_header("Content-Length",str(len(body))); self.send_header("Cache-Control","no-store"); self.send_header("Set-Cookie",f"session={token(user['id'])}; HttpOnly; SameSite=Lax; Path=/; Max-Age=1209600"); self.end_headers(); self.wfile.write(body)
    def do_PATCH(self):
        path=urlparse(self.path).path
        if not path.startswith("/api/posts/"): self.send_json({"error":"Not found"},404); return
        user=self.require_user()
        if not user:return
        pid=path.split("/")[3]; data=self.body_json(); title=str(data.get("title","")).strip()[:140]; body=str(data.get("body","")).strip()
        if len(title)<3 or len(body)<20 or len(body)>20000: self.send_json({"error":"Add a title and at least 20 characters of story."},400); return
        with connect() as db:
            cur=db.execute("UPDATE posts SET title=?,body=?,updated_at=? WHERE id=? AND user_id=?",(title,body,int(time.time()),pid,user["id"]))
            if not cur.rowcount:self.send_json({"error":"Post not found or you don’t have permission to edit it."},404); return
        self.send_json({"ok":True})
    def do_DELETE(self):
        path=urlparse(self.path).path
        if not path.startswith("/api/posts/"): self.send_json({"error":"Not found"},404); return
        user=self.require_user()
        if not user:return
        pid=path.split("/")[3]
        with connect() as db:
            cur=db.execute("DELETE FROM posts WHERE id=? AND user_id=?",(pid,user["id"]))
            if not cur.rowcount:self.send_json({"error":"Post not found or you don’t have permission to delete it."},404); return
        self.send_json({"ok":True})
    def end_headers(self):
        self.send_header("X-Content-Type-Options","nosniff"); self.send_header("Referrer-Policy","strict-origin-when-cross-origin"); super().end_headers()

if __name__=="__main__":
    init_db(); port=int(os.environ.get("PORT","8000")); print(f"The Daily Draft is running at http://localhost:{port}")
    ThreadingHTTPServer(("127.0.0.1",port),Handler).serve_forever()
