from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from app.models.database import db, User

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        name     = request.form['name'].strip()
        email    = request.form['email'].strip().lower()
        password = request.form['password']
        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return redirect(url_for('auth.register'))
        user = User(name=name, email=email, password=generate_password_hash(password))
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash(f'Welcome, {name}!', 'success')
        return redirect(url_for('main.home'))
    return render_template('register.html')

@auth_bp.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        email    = request.form['email'].strip().lower()
        password = request.form['password']
        user     = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('main.home'))
        flash('Invalid email or password.', 'danger')
    return render_template('login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))
