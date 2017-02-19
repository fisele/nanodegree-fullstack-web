import os
import hashlib
import hmac
import re
import random

import webapp2
import jinja2

from google.appengine.ext import db
from string import letters
from user import User

template_dir = os.path.join(os.path.dirname(__file__), 
				'templates')
jinja_env = jinja2.Environment(
			loader = jinja2.FileSystemLoader(template_dir),
            autoescape = True)

secret = 'shouldbearandomthing'

def render_str(template, **params):
	t = jinja_env.get_template(template)
	return t.render(params)

def make_secure_val(val):
	return '%s|%s' % (val, hmac.new(secret, val).hexdigest())

def check_secure_val(secure_val):
	val = secure_val.split('|')[0]
	if secure_val == make_secure_val(val):
		return val

class BlogHandler(webapp2.RequestHandler):
	def write(self, *a, **kw):
		self.response.out.write(*a, **kw)

	def render_str(self, template, **params):
		params['user'] = self.user
		return render_str(template, **params)

	def render(self, template, **kw):
		self.write(self.render_str(template, **kw))

	def set_secure_cookie(self, name, val):
		cookie_val = make_secure_val(val)
		self.response.headers.add_header(
			'Set-Cookie', '%s=%s; Path=/' % (name, cookie_val))

	def read_secure_cookie(self, name):
		cookie_val = self.request.cookies.get(name)
		return cookie_val and check_secure_val(cookie_val)

	def login(self, user):
		self.set_secure_cookie('user_id', str(user.key().id()))

	def initialize(self, *a, **kw):
		webapp2.RequestHandler.initialize(self, *a, **kw)
		uid = self.read_secure_cookie('user_id')
		self.user = uid and User.by_id(int(uid))
	def post(self):
		self.write("%s" % vars(self))
class BlogFront(BlogHandler):
	def get(self):
		self.render('blogfront.html')



### User

### implementation of posts goes here
class Post(db.Model):
	subject = db.StringProperty(required = True)
	content = db.TextProperty(required = True)
	created = db.DateTimeProperty(auto_now_add = True)
	last_modified = db.DateTimeProperty(auto_now = True)
	user = db.ReferenceProperty(User)

	def render(self):
		self._render_text = self.content.replace('\n', '<br>')
		return render_str("post.html", p = self)
		
	@classmethod
	def post_by_id(cls,uid):
		return Post.get_by_id(uid)

class PostPage(BlogHandler):
	def get(self, post_id):
		key = db.Key.from_path('Post', int(post_id))
		posts = []
		posts.append(db.get(key))

		if not posts:
			self.error(404)
			return

		self.render("blogfront.html", posts = posts)
	def post(self, post_id):
		self.delete(post_id)

	def delete(self, post_id):
		self.write('%s' % Post.get_by_id(int(post_id)).user.key().id())
		self.write('%s ' % post_id)
		self.write('%s ' % self.user.key().id())
		post = Post.get_by_id(int(post_id))
		if self.user and post.user.key().id() == self.user.key().id():
			self.write("mmhh")
		else:
			self.write("neeein")

class BlogFront(BlogHandler):
	def get(self):
		posts = Post.all().order('-created')
		self.render('blogfront.html', posts = posts)

class NewPost(BlogHandler):
	def get(self):
		if self.user:
			self.render("newpost.html")
		else:
			self.redirect("/login")

	def post(self):
		if not self.user:
			self.redirect('/blog')

		subject = self.request.get('subject')
		content = self.request.get('content')
	
		if subject and content and self.user:
			p = Post(subject = subject, content = content, user = self.user)
			p.put()
			self.redirect('/blog/%s' % str(p.key().id()))
		else:
			error = "subject and content, please!"
			self.render("newpost.html", subject = subject, content = content, error = error)

class PostDelete(BlogHandler):
	def post(self):
		if self.user:
			self.write("jaaa")
		else:
			self.write("neeein")

###User checks
USER_RE = re.compile(r"^[a-zA-Z0-9_-]{3,20}$")
def valid_username(username):
	return username and USER_RE.match(username)

PASS_RE = re.compile(r"^.{3,20}$")
def valid_password(password):
	return password and PASS_RE.match(password)

def valid_pw(name, password, h):
	salt = h.split(',')[0]
	return h == make_pw_hash(name, password, salt)

EMAIL_RE = re.compile(r'^[\S]+@[\S]+\.[\S]+$')
def valid_email(email):
	return not email or EMAIL_RE.match(email)

def make_salt(length = 5):
	return ''.join(random.choice(letters) for x in xrange(length))

def make_pw_hash(name, pw, salt = None):
	if not salt:
		salt = make_salt()
	h = hashlib.sha256(name + pw + salt).hexdigest()
	return '%s, %s' % (salt, h)
### registration
class Signup(BlogHandler):
	def get(self):
		self.render("signup-form.html")

	def post(self):
		have_error = False
		self.username = self.request.get('username')
		self.password = self.request.get('password')
		self.verify = self.request.get('verify')

		params = dict(username = self.username)

		if not valid_username(self.username):
			params['error_username'] = "That's not a valid username"
			have_error = True
		if not valid_password(self.password):
			params['error_password'] = "That was not a valid password"
			have_error = True
		elif self.password != self.verify:
			params['error_verify'] = "Your passwords did not match!"
			have_error = True
		if have_error:
			self.render('signup-form.html', **params)
		else:
			self.done()

	def done(self, *a, **kw):
		raise NotImplementedError

class Register(Signup):
	def done(self):
		u = User.by_name(self.username)
		if u:
			msg = 'That user already exists.'
			self.render('signup-form.html', error_username = msg)
		else:
			u = User.register(self.username, self.password)
			u.put()
			self.login(u)
			self.redirect('/blog')

### Login
class Login(BlogHandler):
	def get(self):
		self.render('login-form.html')

	def post(self):
		username = self.request.get('username')
		password = self.request.get('password')

		u = User.login(username, password)
		if u:
			self.login(u)
			self.redirect('/blog')
		else:
			msg = 'Invalid login'
			self.render('login-form.html', error = msg)



app = webapp2.WSGIApplication([('/', BlogFront),
								('/blog', BlogFront),
								('/login', Login),
								('/signup', Register),
								('/newpost', NewPost),
								('/blog/?', BlogFront),
								('/blog/([0-9]+)', PostPage),
								('/delete', PostDelete)
								], debug = True)