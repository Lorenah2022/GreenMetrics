from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
import secrets
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, EmailField, FileField, SubmitField, ValidationError
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from wtforms.validators import DataRequired, Length, Email, EqualTo  # IMPORTACIÓN CORREGIDA
import os
import re  # Necesario para la validación de contraseñas

app = Flask(__name__)

# Protege la aplicación Flask contra manipulaciones y ataques
app.secret_key = secrets.token_hex(32)
# Configuración de la base de datos PostgreSQL
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

 # Diccionario de traducciones
textos = {
    'en': {
        'perfil': 'Profile',
        'contenido': 'Content visible only for visitors.',
        'ajustes': 'Settings',
        'cerrar_sesion': 'Logout',
        'iniciar_sesion': 'Login',
        'crear_cuenta': 'Create account',
        'volver_atras': '← Go Back',
        'texto_bienvenida': 'Welcome to Greenmetrics',
        'introducir_anho': 'Enter the year from which you want to extract the metrics.',
        'aceptar': 'Accept',
        'titulo_visit': 'Visitor profile',
        'text_visit': 'Content visible only to visitors.',
        'cancelar': 'Cancel',
        'actualizar_perfil': 'Update profile',
        'confirmar_contrasenha': 'Confirm password',
        'nueva_contrasenha': 'New password. *',
        'correo': 'Email.',
        'usuario': 'User name.',
        'tit_user': 'User profile.',
        'ingles':'English',
        'espanol':'Spanish',
        'pequeno':'Small',
        'normal': 'Medium',
        'grande':'Big',
        'sel_idioma': 'Select language:',
        'sel_letra':'Select Font Size:',
        'guardar':'Save changes',
        'tit_admin': 'Administrator profile',
        'modo_daltonismo': 'Daltonism',
        'criterio_1': 'The password must have at least one uppercase letter, one lowercase letter, and one number.',
        'criterio_2':'Additionally, a minimum of 8 characters.',
        'criterio_3':'* If you do not fill in the password field, it will not be updated.'


    },
    'es': {
        'perfil': 'Perfil',
        'contenido': 'Contenido solo visible para visitantes.',
        'ajustes': 'Ajustes',
        'cerrar_sesion': 'Cerrar sesión',
        'iniciar_sesion': 'Iniciar sesión',
        'crear_cuenta': 'Crear cuenta',
        'volver_atras': '← Volver atrás',
        'texto_bienvenida': 'Bienvenido a Greenmetrics',
        'introducir_anho': 'Introduzca el año del que desea extraer las métricas.',
        'aceptar': 'Aceptar',
        'titulo_visit': 'Perfil de Visitante',
        'text_visit': 'Contenido solo visible para visitantes.',
        'cancelar': 'Cancelar',
        'actualizar_perfil': 'Actualizar perfil.',
        'confirmar_contrasenha': 'Confirmar contraseña',
        'nueva_contrasenha': 'Nueva contraseña. *',
        'correo': 'Correo electrónico.',
        'usuario': 'Nombre de usuario',
        'tit_user': 'Perfil de usuario',
        'ingles':'Inglés',
        'espanol':'Español',
        'pequeno':'Pequeño',
        'normal':'Medio',
        'grande':'Grande',
        'sel_idioma':'Seleccionar Idioma:',
        'sel_letra':'Seleccionar Tamaño de Letra:',
        'guardar':'Guardar cambios.',
        'tit_admin':'Perfil de administrador',
        'modo_daltonismo': 'Modo Daltonismo',
        'criterio_1':'La contraseña debe tener al menos una mayúscula, una minúscula y un número.',
        'criterio_2':'Además de un minimo de 8 caracteres.',
        'criterio_3':'* Si no rellena el campo de la contraseña, esta no se actualizará.'
    }
}





 # Modelo de Usuario
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), nullable=False , unique=True)
    email = db.Column(db.String(100), nullable=False , unique=True)
    password = db.Column(db.String(200), nullable=False)
    rol = db.Column(db.String(50), nullable=False, default='visitante')  # Default es 'usuario'



# Función de validación de contraseña
def validar_contrasena(password):
    if len(password) < 8:
        return "La contraseña debe tener al menos 8 caracteres."
    if not any(char.isupper() for char in password):
        return "La contraseña debe incluir al menos una letra mayúscula."
    if not any(char.islower() for char in password):
        return "La contraseña debe incluir al menos una letra minúscula."
    if not any(char.isdigit() for char in password):
        return "La contraseña debe incluir al menos un número."
    return None


# Ruta principal
@app.route('/')
def index():
    return redirect(url_for('login'))

# Ruta principal: Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        user = User.query.filter_by(email=email).first()
        
        if not user:
            flash('Correo incorrecto.', 'error')  # Mensaje de error si no se encuentra el correo
        elif not check_password_hash(user.password, password):
            flash('Contraseña incorrecta.', 'error')  # Mensaje de error si la contraseña es incorrecta
        else:
            session['user_id'] = user.id
            session['username'] = user.username
            session['rol'] = user.rol
            return redirect(url_for('pagina_principal', 
                               rol=user.rol))
    
    return render_template('login.html')

# Ruta para el registro de nuevos usuarios
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
            # Obtener datos del formulario
            username = request.form['username'] 
            email = request.form['email']  
            password = request.form['password']
            confirm_password = request.form['confirm_password']

            # Validar contraseña
            error = validar_contrasena(password)
            if error:
                flash(error, 'error')
                return render_template('register.html')  # Detener el proceso si hay errores
            
            # Validar datos
            if not username or not email or not password:
                flash('Por favor, completa todos los campos', 'error')
            elif password != confirm_password:
                flash('Las contraseñas no coinciden', 'error')
            else:
                # Verificar si el nombre de usuario o el correo electrónico ya están en uso
                existing_user_by_username = User.query.filter_by(username=username).first()
                existing_user_by_email = User.query.filter_by(email=email).first()

                if existing_user_by_username:
                    flash('El nombre de usuario ya está en uso', 'error')
                elif existing_user_by_email:
                    flash('El correo electrónico ya está en uso', 'error')
                else:
                    try:
                        # Hash de la contraseña con pbkdf2:sha256
                        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
                        new_user = User(username=username, email=email, password=hashed_password, rol ='usuario')  
                        db.session.add(new_user)
                        db.session.commit()
                        flash('Cuenta creada exitosamente', 'success')
                        print("Usuario guardado en la base de datos.")
                    except Exception as e:
                        db.session.rollback()
                        flash(f'Error al guardar el usuario: {str(e)}', 'error')
                        print(f"Error al guardar el usuario: {str(e)}")
            
    return render_template('register.html')


# Ruta para la página principal
@app.route('/pagina_principal')
def pagina_principal():
    # Comprobar el idioma seleccionado en la sesión, por defecto 'en'
    idioma = session.get('idioma', 'es')
    tamano_texto = session.get('tamano_texto', 'normal')
    daltonismo = session.get('daltonismo', False)
    # Comprobar si el usuario está autenticado
    if 'user_id' not in session:
        return render_template('pagina_principal.html', 
                               rol='visitante', 
                               textos=textos[idioma], 
                               tamano_texto=tamano_texto,daltonismo=daltonismo)  # Contenido para visitantes
    else:
        rol = session['rol']
        return render_template('pagina_principal.html', 
                               rol=rol, 
                               textos=textos[idioma], 
                               tamano_texto=tamano_texto,daltonismo=daltonismo)  # Contenido según el rol
# Cerrar sesión
@app.route('/logout')
def logout():
    session.clear()
    flash("Has cerrado sesión.", "info")
    return redirect(url_for('login'))

# Formulario para editar el perfil
class ProfileForm(FlaskForm):
    username = StringField('Nombre de usuario', validators=[
        DataRequired(), Length(min=3, max=50)
    ])
    email = EmailField('Correo electrónico', validators=[
        DataRequired(), Email()
    ])
    password = PasswordField('Nueva Contraseña', validators=[])
    confirm_password = PasswordField('Confirmar Contraseña', validators=[
        EqualTo('password', message='Las contraseñas deben coincidir.')
    ])
    submit = SubmitField('Guardar Cambios')
    
# Ruta para editar el perfil
@app.route('/perfil', methods=['GET', 'POST'])
def perfil():
    idioma = session.get('idioma', 'es')
    daltonismo = session.get('daltonismo', False)
    tamano_texto = session.get('tamano_texto', 'normal')
    rol = session.get('rol')
    # Verificación de si el usuario está logueado en la sesión
    if 'user_id' not in session:
        # Página que muestra el perfil de visitante
        return render_template('perfil_visitante.html', tamano_texto=tamano_texto,textos=textos[idioma],daltonismo=daltonismo)
    
    # Obtiene el usuario actual desde la sesión
    usuario = User.query.get(session['user_id'])  # Usar 'user_id' en lugar de 'id'
    
    # Crear el formulario de perfil
    form = ProfileForm()

    if request.method == 'POST':  # Validación explícita del método POST
        if form.validate():  # Valida los datos del formulario sin necesidad de submit
            # Actualizar solo los campos que se llenaron
            usuario.username = form.username.data
            usuario.email = form.email.data

            # Si el campo de contraseña no está vacío, actualiza la contraseña
            if form.password.data:
                # Validar contraseña
                error = validar_contrasena(form.password.data)
                if error:
                    flash(error, 'error')
                    return render_template(
                    'perfil_usuario.html', form=form, usuario=usuario,
                    tamano_texto=tamano_texto, textos=textos[idioma]
                    )
                usuario.password = generate_password_hash(form.password.data)
           
            # Guardar los cambios en la base de datos
            try:
                db.session.commit()
                if idioma=='es':
                    flash("Perfil actualizado correctamente.", "success")
                elif idioma=='en':
                    flash("Profile updated successfully", "success")

                return redirect(url_for('pagina_principal'))
            except Exception as e:
                db.session.rollback()
                flash(f"Error al actualizar el perfil: {str(e)}", "error")
        else:
            flash("Hay errores en el formulario. Por favor, corrígelos.", "error")

    # Rellenar los campos del formulario con los datos actuales del usuario
    form.username.data = usuario.username
    form.email.data = usuario.email

    # Pasar el tamaño de texto a las plantillas
    if rol == 'admin':
        return render_template('perfil_admin.html', form=form, usuario=usuario, tamano_texto=tamano_texto, textos=textos[idioma],daltonismo=daltonismo)
    else:
        return render_template('perfil_usuario.html', form=form, usuario=usuario, tamano_texto=tamano_texto, textos=textos[idioma],daltonismo=daltonismo)

@app.route('/ajustes', methods=['GET', 'POST'])
def ajustes():
    idioma = session.get('idioma', 'es')

    if request.method == 'POST':
        idioma = request.form.get('idioma')
        tamano_texto = request.form.get('tamano_texto')
        daltonismo = request.form.get('daltonismo') == 'on'  # Verificamos si el checkbox está seleccionado
        session['idioma'] = idioma
        session['tamano_texto'] = tamano_texto
        session['daltonismo'] = daltonismo  # Guardamos la opción de daltonismo en la sesión
        return redirect(url_for('ajustes'))  # Redirige para actualizar la página con los nuevos valores
    idioma = session.get('idioma', 'es')
    tamano_texto = session.get('tamano_texto', 'normal')
    daltonismo = session.get('daltonismo', False)  # Por defecto, el daltonismo está desactivado
    return render_template('ajustes.html', idioma=idioma, tamano_texto=tamano_texto,  daltonismo=daltonismo,textos=textos[idioma])


if __name__ == '__main__':
    # Crear las tablas de la base de datos
    with app.app_context():
        db.create_all()
    app.run(debug=True)