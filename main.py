from flask import Flask, render_template, request, redirect, url_for
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required
import os
import time
from datetime import datetime
import pytz
from flask import send_file
import openpyxl
from werkzeug.utils import secure_filename
import os

moscow_tz = pytz.timezone('Europe/Moscow')
os.environ['TZ'] = 'Europe/Moscow'
time.tzset()

app = Flask(__name__)
app.secret_key = 'your_secret_key'

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

from flask_sqlalchemy import SQLAlchemy
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime


app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///crm.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
handler = RotatingFileHandler('app.log', maxBytes=10000, backupCount=1)
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
app.logger.addHandler(handler)
app.logger.setLevel(logging.INFO)

db = SQLAlchemy(app)


UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'xlsx'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


class User(UserMixin):
    def __init__(self, id):
        self.id = id

users = {
    "admin": {"password": "admin_password"},
"user": {"password": "user"},
    # Добавьте сюда других пользователей, если необходимо
}

class Contact(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    organization = db.Column(db.String(100), nullable=True)  # новое поле
    position = db.Column(db.String(100), nullable=True)      # новое поле
    email = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(100), nullable=True)
    source = db.Column(db.String(100), nullable=True)  # новое поле




class Deal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contact.id'), nullable=False)
    contact = db.relationship('Contact', backref='deals')
    stage = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(500), nullable=False)
    change_type = db.Column(db.String(20), nullable=True)  # новый столбец для типа изменения
    old_value = db.Column(db.String(100), nullable=True)  # новый столбец для старого значения
    new_value = db.Column(db.String(100), nullable=True)  # новый столбец для нового значения
    contact_id = db.Column(db.Integer, db.ForeignKey('contact.id'), nullable=False)
    contact = db.relationship('Contact', backref='comments')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    change_type = db.Column(db.String(50), nullable=True)  # добавьте эту строку


with app.app_context():
    db.create_all()

@app.route('/')
@login_required
def index():
    return render_template('index.html')
@login_manager.user_loader
def load_user(user_id):
    return User(user_id)

from sqlalchemy import distinct

@app.route('/export_contacts')
@login_required
def export_contacts():
    status_filter = request.args.get('status_filter', None)

    if status_filter:
        contacts = Contact.query.filter_by(status=status_filter).all()
    else:
        contacts = Contact.query.all()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(['Name', 'Organization', 'Position', 'Email', 'Phone', 'Status'])

    for contact in contacts:
        ws.append([contact.name, contact.organization, contact.position, contact.email, contact.phone, contact.status])

    filename = f'contacts_export_{status_filter if status_filter else "all"}.xlsx'
    wb.save(filename)

    return send_file(filename, as_attachment=True)

@app.route('/import_contacts', methods=['GET', 'POST'])
@login_required
def import_contacts():
    if request.method == 'POST':
        # проверка наличия файла
        if 'file' not in request.files:
            return "Файл не найден", 400

        file = request.files['file']

        # проверка имени файла
        if file.filename == '':
            return "Файл не выбран", 400

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            # Здесь вы можете добавить код для обработки файла (например, добавление контактов в базу данных)
            return "Файл успешно загружен и обработан", 200
        else:
            return "Файл с недопустимым расширением", 400

    return render_template('import_contacts.html')


@app.route('/contacts')
@login_required
def contacts():
    status_id = request.args.get('status')
    if status_id:
        contacts = Contact.query.filter_by(status=status_id).all()
    else:
        contacts = Contact.query.all()

    statuses = Contact.query.with_entities(distinct(Contact.status)).all()

    return render_template('contacts.html', contacts=contacts, statuses=statuses, selected_status=status_id)

@app.route('/contacts/<int:contact_id>/delete', methods=['POST'])
@login_required
def delete_contact(contact_id):
    contact = Contact.query.get_or_404(contact_id)
    db.session.delete(contact)
    db.session.commit()
    return redirect(url_for('contacts'))


@app.route('/add_contact', methods=['POST'])
@login_required
def add_contact():
    name = request.form['name']
    organization = request.form['organization']  # новое поле
    position = request.form['position']          # новое поле
    email = request.form['email']
    phone = request.form['phone']
    source = request.form['source']  # новое поле
    new_contact = Contact(name=name, organization=organization, position=position, email=email, phone=phone,
                          source=source)

    db.session.add(new_contact)
    db.session.commit()

    return redirect(url_for('contacts'))

@app.route('/contacts/<int:contact_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_contact(contact_id):
    contact = Contact.query.get_or_404(contact_id)
    statuses = Contact.query.with_entities(distinct(Contact.status)).all()

    if request.method == 'POST':
        old_name = contact.name
        old_organization = contact.organization
        old_position = contact.position
        old_email = contact.email
        old_phone = contact.phone
        old_status = contact.status

        contact.name = request.form['name']
        contact.organization = request.form['organization']
        contact.position = request.form['position']
        contact.email = request.form['email']
        contact.phone = request.form['phone']
        contact.status = request.form['status']
        old_source = contact.source
        contact.source = request.form['source']

        if old_source != contact.source:
            change_comment = Comment(text=f"Источник изменен", contact_id=contact.id, change_type="source",
                                     old_value=old_source, new_value=contact.source)
            db.session.add(change_comment)

        if old_name != contact.name:
            change_comment = Comment(text=f"Имя изменено", contact_id=contact.id, change_type="name", old_value=old_name, new_value=contact.name)
            db.session.add(change_comment)

        if old_organization != contact.organization:
            change_comment = Comment(text=f"Организация изменена", contact_id=contact.id, change_type="organization", old_value=old_organization, new_value=contact.organization)
            db.session.add(change_comment)

        if old_position != contact.position:
            change_comment = Comment(text=f"Должность изменена", contact_id=contact.id, change_type="position", old_value=old_position, new_value=contact.position)
            db.session.add(change_comment)

        if old_email != contact.email:
            change_comment = Comment(text=f"Email изменен", contact_id=contact.id, change_type="email", old_value=old_email, new_value=contact.email)
            db.session.add(change_comment)

        if old_phone != contact.phone:
            change_comment = Comment(text=f"Телефон изменен", contact_id=contact.id, change_type="phone", old_value=old_phone, new_value=contact.phone)
            db.session.add(change_comment)

        if old_status != contact.status:
            change_comment = Comment(text=f"Статус изменен", contact_id=contact.id, change_type="status", old_value=old_status, new_value=contact.status)
            db.session.add(change_comment)

        db.session.commit()
        return redirect(url_for('view_contact', contact_id=contact_id))
    return render_template('edit_contact.html', contact=contact, statuses=statuses)

@app.route('/deals')
@login_required
def deals():
    deals = Deal.query.all()
    return render_template('deals.html', deals=deals)

@app.route('/add_deal', methods=['POST'])
@login_required
def add_deal():
    contact_id = request.form['contact_id']
    stage = request.form['stage']
    amount = request.form['amount']

    new_deal = Deal(contact_id=contact_id, stage=stage, amount=amount)
    db.session.add(new_deal)
    db.session.commit()

    return redirect(url_for('deals'))

@app.route('/statuses')
@login_required
def statuses():
    return "Страница 'Управление статусами' находится в разработке"
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username in users and users[username]['password'] == password:
            user = User(username)
            login_user(user)
            return redirect(url_for('contacts'))
        else:
            return "Неправильный логин или пароль."
    return render_template('login.html')
@app.route('/contacts/<int:contact_id>/view')
@login_required
def view_contact(contact_id):
    contact = Contact.query.get_or_404(contact_id)
    modified_comments = Comment.query.filter_by(contact_id=contact_id).filter(Comment.change_type.is_(None)).order_by(Comment.created_at.desc()).all()
    changes = Comment.query.filter_by(contact_id=contact_id).filter(Comment.change_type.isnot(None)).order_by(Comment.created_at.desc()).all()
    return render_template('view_contact.html', contact=contact, modified_comments=modified_comments, changes=changes)
@app.route('/contact/<int:contact_id>/add_comment', methods=['POST'])
@login_required
def add_comment(contact_id):
    # Загрузка контакта из базы данных
    contact = Contact.query.get_or_404(contact_id)

    # Получение текста комментария из формы
    comment_text = request.form['commentText']

    # Создание и добавление нового комментария
    new_comment = Comment(text=comment_text, contact_id=contact_id)
    db.session.add(new_comment)
    db.session.commit()

    # Возврат на страницу контакта
    return redirect(url_for('view_contact', contact_id=contact_id))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))
if __name__ == '__main__':
    app.run(port=5000)