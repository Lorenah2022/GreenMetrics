from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
import secrets
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, EmailField, FileField, SubmitField
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from wtforms.validators import DataRequired, Length, Email, EqualTo  # IMPORTACIÓN CORREGIDA
import os

app = Flask(__name__)

# Protege la aplicación Flask contra manipulaciones y ataques
app.secret_key = secrets.token_hex(32)

# Configuración de la base de datos PostgreSQL
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://flask_user:securepassword@localhost/flask_users'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'  # Ruta donde se guardarán los archivos subidos
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}  # Extensiones permitidas

# Asegúrate de que la carpeta de uploads exista
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

db = SQLAlchemy(app)

# Modelo de Usuario
class Usuario(db.Model):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), nullable=False)
    apellido = db.Column(db.String(50), nullable=False)
    correo = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    foto_perfil = db.Column(db.String(200), nullable=True)
    rol = db.Column(db.String(50), nullable=False, default='usuario')  # Default es 'usuario'


# Crear las tablas en la base de datos
with app.app_context():
    db.create_all()

# Función para verificar si el archivo tiene una extensión permitida
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# Ruta principal: Login
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        correo = request.form['correo']
        password = request.form['password']

        # Buscar usuario en la base de datos
        usuario = Usuario.query.filter_by(correo=correo).first()
        if usuario and check_password_hash(usuario.password, password):
            session['usuario_id'] = usuario.id
            session['correo'] = usuario.correo
            session['rol'] = usuario.rol  # Guardamos el rol en la sesión

            flash("¡Inicio de sesión exitoso!", "success")
            return redirect(url_for('pagina_principal'))
        else:
            flash("Correo o contraseña incorrectos.", "danger")
    return render_template('login.html')

# Ruta para el registro de nuevos usuarios
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        nombre = request.form['nombre']
        apellido = request.form['apellido']
        correo = request.form['correo']
        password = request.form['password']

        # Validar si el correo ya existe
        if Usuario.query.filter_by(correo=correo).first():
            flash("Ya existe una cuenta con ese correo electrónico.", "danger")
            return redirect(url_for('register'))

        # Crear nuevo usuario
        hashed_password = generate_password_hash(password)
        nuevo_usuario = Usuario(nombre=nombre, apellido=apellido, correo=correo, password=hashed_password)
        db.session.add(nuevo_usuario)
        db.session.commit()
        flash("¡Cuenta creada exitosamente! Ahora puedes iniciar sesión.", "success")
        return redirect(url_for('login'))
    return render_template('register.html')

# Ruta para la página principal
@app.route('/pagina_principal')
def pagina_principal():
    if 'usuario_id' not in session:
        return render_template('pagina_principal.html', rol='visitante')  # Contenido para visitantes
    else:
        rol = session['rol']
        return render_template('pagina_principal.html', rol=rol)  # Contenido según el rol

# Cerrar sesión
@app.route('/logout')
def logout():
    session.clear()
    flash("Has cerrado sesión.", "info")
    return redirect(url_for('login'))

# Formulario para editar el perfil
class ProfileForm(FlaskForm):
    nombre = StringField('Nombre', validators=[
        DataRequired(), Length(min=3, max=50)
    ])
    apellido = StringField('Apellido', validators=[
        DataRequired(), Length(min=3, max=50)
    ])
    correo = EmailField('Correo electrónico', validators=[
        DataRequired(), Email()
    ])
    password = PasswordField('Nueva Contraseña', validators=[
        Length(min=6), EqualTo('confirm_password', message='Las contraseñas deben coincidir.')
    ])
    confirm_password = PasswordField('Confirmar Contraseña')
    profile_pic = FileField('Foto de perfil')
    submit = SubmitField('Guardar Cambios')



# Ruta para editar el perfil
@app.route('/perfil', methods=['GET', 'POST'])
def perfil():
    usuario_id = session.get('usuario_id')
    if usuario_id not in session:
        return render_template('perfil_visitante.html')  # Página que muestra el perfil de visitante
    else:
        # Obtén el rol y el usuario actual desde la sesión
        rol = session.get('rol')
        usuario = Usuario.query.get(session['usuario_id'])

        # Crea el formulario de perfil
        form = ProfileForm()

        # Si el formulario se envía, actualizar los datos del perfil
        if request.method == 'POST' and form.validate_on_submit():
            usuario.nombre = form.nombre.data
            usuario.apellido = form.apellido.data
            usuario.correo = form.correo.data

            # Si se proporciona una nueva contraseña, actualízala
            if form.password.data:
                usuario.password = generate_password_hash(form.password.data)

            # Si hay una nueva foto de perfil, procesarla
            if form.profile_pic.data:
                file = form.profile_pic.data
                if file and allowed_file(file.filename):  # Verificar si la imagen es válida
                    filename = secure_filename(file.filename)
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    usuario.foto_perfil = filename  # Guardar el nombre de la imagen en la base de datos

            db.session.commit()  # Guardar los cambios en la base de datos
            flash("Perfil actualizado correctamente.", "success")
            return redirect(url_for('perfil'))

        # Rellenar los campos del formulario con los datos actuales del usuario
        form.nombre.data = usuario.nombre
        form.apellido.data = usuario.apellido
        form.correo.data = usuario.correo
        if rol == 'admin':
            # Si el usuario es un administrador, mostrar más opciones
            return render_template('perfil_admin.html', form=form, usuario=usuario)
        else:
            # Si no es administrador, mostrar el perfil estándar
            return render_template('perfil_usuario.html', form=form, usuario=usuario)

if __name__ == '__main__':
    app.run(debug=True)
