# --- Flask Core Modules ---
from flask import Flask, render_template, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask import request, session, jsonify

# --- Flask Extensions ---
from flask_wtf import FlaskForm
from flask_dance.contrib.google import make_google_blueprint, google

# --- WTForms for Form Handling ---
from wtforms import StringField, PasswordField, EmailField, FileField, SubmitField, ValidationError
from wtforms.validators import DataRequired, Length, Email, EqualTo  

# --- Security and Authentication ---
from werkzeug.security import generate_password_hash, check_password_hash
import secrets  # For generating secret keys

# --- Google OAuth2 ---
from google.oauth2 import id_token
from google.auth.transport import requests

# --- System and Utility Modules ---
import os
from dotenv import load_dotenv
import subprocess
import re
import threading
import sys
from sqlalchemy import or_

from werkzeug.utils import secure_filename
from config import cargar_configuracion, guardar_configuracion



#Cargar el diccionario con los textos
from textos import textos
from mensajes_flash import mensajes_flash

# Cargar variables desde .env
load_dotenv()


app = Flask(__name__)




# Protege la aplicación Flask contra manipulaciones y ataques
app.secret_key = secrets.token_hex(32)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")

app.config['SQLALCHEMY_BINDS'] = {
    'busqueda': os.getenv("DATABASE_BINDS")  
}

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# Configuración de OAuth con Google
app.config["GOOGLE_OAUTH_CLIENT_ID"] = os.getenv("GOOGLE_CLIENT_ID")
app.config["GOOGLE_OAUTH_CLIENT_SECRET"] = os.getenv("GOOGLE_CLIENT_SECRET")
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

db = SQLAlchemy(app)


# Variable global para el estado del proceso
estado_proceso = {"en_proceso": False, "mensaje": "", "porcentaje": 0, "completado": False}
lock = threading.Lock()  # Para controlar el acceso concurrente a estado_proceso


# Crear el blueprint de Google OAuth
google_bp = make_google_blueprint(client_id=os.getenv("GOOGLE_CLIENT_ID"), client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),  redirect_to='pagina_pedir_anho')
app.register_blueprint(google_bp, url_prefix='/google_login')


# Definir el directorio de subida
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')

# Configurar el directorio de subida
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Asegurarse de que la carpeta de subida exista
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
 


# ----------------------- BASES DE DATOS -----------------------------------------------------
class User(db.Model):
    """
    Modelo de base de datos para los usuarios.
    """
    id = db.Column(db.Integer, primary_key=True)
    google_id = db.Column(db.String(50), unique=True, nullable=True)  # Campo opcional
    username = db.Column(db.String(50), nullable=False , unique=True)
    email = db.Column(db.String(100), nullable=True, unique=True)
    password = db.Column(db.String(200), nullable=False)
    rol = db.Column(db.String(50), nullable=False, default='visitante')  # Default es 'usuario'

class Busqueda(db.Model):
    """
    Modelo de base de datos para almacenar los resultados de las búsquedas de guías docentes.
    """
    __bind_key__ = 'busqueda'
    id = db.Column(db.Integer, primary_key=True)
    anho = db.Column(db.String(20), nullable=False)
    codigo_asignatura = db.Column(db.String(100), nullable=True)
    tipo_programa = db.Column(db.String(100), nullable=True)
    nombre_archivo=db.Column(db.String(100), nullable=True)
    modalidad=db.Column(db.String(100), nullable=True)
    sostenibilidad = db.Column(db.String(10), nullable=True)

    
    __table_args__ = (
        db.UniqueConstraint('anho','codigo_asignatura','modalidad', name='unique_modalidad_anho_codigo'),
    )


# ----------------------- FORMULARIOS -----------------------------------------------------
class ProfileForm(FlaskForm):
    """
    Formulario WTForms para la edición del perfil de usuario.
    """
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
    

#  ----------------------- PÁGINAS PRINCIPALES ----------------------------------------------------
@app.route('/')
def index():
    """
    Ruta principal que redirige al usuario a la página de login.
    """
    return redirect(url_for('login'))

@app.route('/logout')
def logout():
    """
    Ruta principal que redirige al usuario a la página de login.
    """
    idioma = session.get('idioma', 'es')  # Leer antes de limpiar sesión
    session.clear()
    flash(mensajes_flash[idioma]['cerrada_sesion'], "info")
    return redirect(url_for('login', idioma=idioma))  # Pasar idioma por URL


# Ruta para la página principal
@app.route('/pagina_principal')
def pagina_principal():
    """
    Renderiza la página principal.
    """
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

# Ruta principal: Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    Maneja el proceso de login de usuarios, tanto con credenciales locales como con Google OAuth.
    """
    google_client_id = app.config["GOOGLE_OAUTH_CLIENT_ID"]

    if request.method == 'POST':
        idioma = request.form.get('idioma', 'es')
        session['idioma'] = idioma


        identifier = request.form['identifier']
        password = request.form['password']
        
        if re.match(r"[^@]+@[^@]+\.[^@]+", identifier):  # Si es un correo
            user = User.query.filter_by(email=identifier).first()
        else:  # Si no es un correo, tratamos como nombre de usuario
            user = User.query.filter_by(username=identifier).first()

        if not user:
            flash(mensajes_flash[idioma]['usuario_no_encontrado'], 'error')
        elif not check_password_hash(user.password, password):
            flash(mensajes_flash[idioma]['contrasena_incorrecta'], 'error')
        else:
            session['user_id'] = user.id
            session['username'] = user.username
            session['rol'] = user.rol

            return redirect(url_for('pagina_principal', 
                               rol=user.rol))
    else:
        # ✅ Restaurar idioma desde la URL si se pasó como argumento
        idioma = session.get('idioma') or request.args.get('idioma', 'es') 
        session['idioma'] = idioma  

    return render_template('login.html',google_client_id=google_client_id,textos=textos[idioma])




@app.route('/cambiar_idioma', methods=['POST'])
def cambiar_idioma():
    """
    Cambia el idioma de la sesión del usuario basado en la solicitud POST.

    Returns:
        tuple: Una tupla vacía y un código de estado 200 para indicar éxito.
    """
    data = request.get_json()
    idioma = data.get('idioma', 'es')  # Obtener idioma enviado por el cliente
    session['idioma'] = idioma  # Guardar el idioma en la sesión
    return '', 200  # Respuesta exitosa



# Ruta para el registro de nuevos usuarios
@app.route('/register', methods=['GET', 'POST'])
def register():
    """
    Maneja el registro de nuevos usuarios. Valida los datos del formulario,
    verifica si el usuario o email ya existen y crea un nuevo usuario en la base de datos.
    """
    if request.method != 'POST':
        idioma = session.get('idioma', 'es')
        return render_template('register.html', idioma=idioma)

    username = request.form.get('username', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '')
    confirm_password = request.form.get('confirm_password', '')

    error = validar_contrasena(password)
    if error:
        flash(mensajes_flash[idioma]['contrasena_incorrecta'], 'error')
        return render_template('register.html', idioma=idioma)

    if is_form_incomplete(username, email, password):
        flash(mensajes_flash[idioma]['campos_incompletos'], 'error')
        return render_template('register.html', idioma=idioma)

    if is_password_mismatch(password, confirm_password):
        flash(mensajes_flash[idioma]['contrasenas_no_coinciden'], 'error')
        return render_template('register.html', idioma=idioma)

    existing_user, existing_email = is_username_or_email_taken(username, email)
    if existing_user:
        flash(mensajes_flash[idioma]['usuario_existente'], 'error')
        return render_template('register.html', idioma=idioma)
    if existing_email:
        flash(mensajes_flash[idioma]['email_existente'], 'error')
        return render_template('register.html', idioma=idioma)

    try:
        create_user(username, email, password)
        flash(mensajes_flash[idioma]['cuenta_creada'], 'success')
        print("Usuario guardado en la base de datos.")
        return redirect(url_for('login'),textos=textos[idioma])
    except Exception as e:
        db.session.rollback()
        flash(mensajes_flash[idioma]['error_guardar'] + str(e), 'error')
        print(f"Error al guardar el usuario: {str(e)}")

    return render_template('register.html', idioma=idioma)


def is_form_incomplete(username, email, password):
    """
    Verifica si los campos obligatorios del formulario de registro están incompletos.

    Args:
        username (str): Nombre de usuario.
        email (str): Correo electrónico.
        password (str): Contraseña.

    Returns:
        bool: True si algún campo está vacío, False en caso contrario.
    """
    return not username or not email or not password

def is_password_mismatch(password, confirm_password):
    """
    Verifica si la contraseña y la confirmación de contraseña coinciden.

    Args:
        password (str): Contraseña.
        confirm_password (str): Confirmación de contraseña.

    Returns:
        bool: True si las contraseñas no coinciden, False en caso contrario.
    """

    return password != confirm_password

def is_username_or_email_taken(username, email):
    """
    Verifica si un nombre de usuario o correo electrónico ya existen en la base de datos.

    Args:
        username (str): Nombre de usuario a verificar.
        email (str): Correo electrónico a verificar.

    Returns:
        tuple: Una tupla conteniendo el objeto User si el nombre de usuario existe
               y el objeto User si el correo electrónico existe.
    """
    return (
    User.query.filter_by(username=username).first(),
    User.query.filter_by(email=email).first()
    )

def create_user(username, email, password):
    """
    Crea un nuevo usuario en la base de datos con la contraseña hasheada.

    Args:
        username (str): Nombre de usuario para el nuevo usuario.
        email (str): Correo electrónico para el nuevo usuario.
        password (str): Contraseña para el nuevo usuario (se hasheará antes de guardar).
    """
    hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
    user = User(username=username, email=email, password=hashed_password, rol='usuario')
    db.session.add(user)
    db.session.commit()


#  ----------------------- PÁGINAS DE MODIFICACIÓN DE PARÁMETROS ----------------------------------------------------
# Ruta para cambiar los ajustes (idioma, tamaño de la letra y habilitar la opción de daltonismo)
@app.route('/ajustes', methods=['GET', 'POST'])
def ajustes():
    """
    Crea un nuevo usuario en la base de datos con la contraseña hasheada.

    Args:
        username (str): Nombre de usuario para el nuevo usuario.
        email (str): Correo electrónico para el nuevo usuario.
        password (str): Contraseña para el nuevo usuario (se hasheará antes de guardar).
    """

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



def get_user_preferences():
    """
    Obtiene las preferencias de usuario (idioma, daltonismo, tamaño de texto, rol)
    almacenadas en la sesión.

    Returns:
        dict: Un diccionario con las preferencias del usuario.
    """
    return {
    'idioma': session.get('idioma', 'es'),
    'daltonismo': session.get('daltonismo', False),
    'tamano_texto': session.get('tamano_texto', 'normal'),
    'rol': session.get('rol')
    }

def is_user_logged_in():
    """
    Verifica si hay un usuario logueado en la sesión.

    Returns:
        bool: True si 'user_id' está en la sesión, False en caso contrario.
    """
    return 'user_id' in session

def get_logged_in_user():
    """
    Obtiene el objeto User del usuario logueado a partir del 'user_id' en la sesión.

    Returns:
        User | None: El objeto User si hay un usuario logueado, None en caso contrario.
    """
    return User.query.get(session['user_id'])

def update_user_profile(form, user, idioma):
    """
    Actualiza el perfil de un usuario con los datos del formulario.

    Valida la nueva contraseña si se proporciona y hashea antes de guardar.
    Realiza un commit a la base de datos.

    Args:
        form (ProfileForm): El formulario con los datos actualizados.
        user (User): El objeto User a actualizar.
        idioma (str): El idioma actual del usuario para mensajes flash.

    Returns:
        tuple: Una tupla (success, response). Success es True si la actualización
               fue exitosa, False en caso contrario. Response es la respuesta
               (redirección o renderizado de plantilla) a devolver.
    """
    user.username = form.username.data
    user.email = form.email.data
    if form.password.data:
        error = validar_contrasena(form.password.data)
        if error:
            flash(mensajes_flash[idioma]['error_contrasena'], 'error')
            
            return False, render_template('perfil_usuario.html', form=form, usuario=user,
                                        tamano_texto=session.get('tamano_texto'),
                                        textos=textos[idioma],
                                        daltonismo=session.get('daltonismo'))
        user.password = generate_password_hash(form.password.data)

    try:
        db.session.commit()
        flash(mensajes_flash[idioma]['perfil_actualizado'], 'success')
        return True, redirect(url_for('perfil'))
    except Exception as e:
        db.session.rollback()
        flash(f"{mensajes_flash[idioma]['error_actualizar']}{str(e)}", "error")
        return False, None

  
def cargar_datos_formulario(form, user):
    """
    Carga los datos del usuario en el formulario de perfil.

    Args:
        form (ProfileForm): El formulario a llenar.
        user (User): El objeto User con los datos a cargar.
    """
    form.username.data = user.username
    form.email.data = user.email

def render_perfil(form, user, prefs):
    """
    Renderiza la plantilla de perfil de usuario o administrador.

    Selecciona la plantilla adecuada según el rol del usuario y pasa los datos
    del formulario, usuario y preferencias.

    Args:
        form (ProfileForm): El formulario de perfil.
        user (User): El objeto User del usuario logueado.
        prefs (dict): Diccionario con las preferencias del usuario.

    Returns:
        str: El HTML renderizado de la plantilla de perfil.
    """
    template = 'perfil_admin.html' if prefs['rol'] == 'admin' else 'perfil_usuario.html'
    return render_template(template, form=form, usuario=user,
    tamano_texto=prefs['tamano_texto'],
    textos=textos[prefs['idioma']],
    daltonismo=prefs['daltonismo'])

# Ruta para editar el perfil
@app.route('/perfil', methods=['GET', 'POST'])
def perfil():
    """
    Maneja la página de perfil del usuario. Permite a los usuarios logueados
    ver y editar su información. Los visitantes ven una página de perfil de visitante.
    """
    prefs = get_user_preferences()
    if not is_user_logged_in():
        return render_template('perfil_visitante.html',
                            tamano_texto=prefs['tamano_texto'],
                            textos=textos[prefs['idioma']],
                            daltonismo=prefs['daltonismo'])

    user = get_logged_in_user()
    form = ProfileForm()

    if request.method == 'POST':
        if form.validate():
            success, response = update_user_profile(form, user, prefs['idioma'])
            if success:
                return response
            elif response:
                return response
        else:
            flash(mensajes_flash[prefs['idioma']]['errores_formulario'], "error")

    cargar_datos_formulario(form, user)
    return render_perfil(form, user, prefs)


# Función de validación de contraseña
def validar_contrasena(password):
    """
    Valida si una contraseña cumple con los requisitos mínimos de seguridad.

    Requiere al menos 8 caracteres, una mayúscula, una minúscula y un número.

    Args:
        password (str): La contraseña a validar.

    Returns:
        str | None: Un mensaje de error si la contraseña no cumple los requisitos,
                    o None si la contraseña es válida.
    """
    idioma = session.get('idioma', 'es')
    textos = mensajes_flash.get(idioma, mensajes_flash['es'])
    if len(password) < 8:
        return textos['contrasena_longitud']
    if not any(char.isupper() for char in password):
        return textos['contrasena_mayuscula']
    if not any(char.islower() for char in password):
        return textos['contrasena_minuscula']
    if not any(char.isdigit() for char in password):
        return textos['contrasena_numero']
    return None


#  ----------------------- CONFIGURACIÓN DE INICION SESIÓN CON GOOGLE ----------------------------------------------------
# Login con google
def get_google_user_info():
    """
    Obtiene la información del usuario desde Google si la autenticación con Google está autorizada.

    Returns:
        dict | None: Un diccionario con la información del usuario de Google si la solicitud es exitosa,
                     None en caso contrario.
    """
    if not google.authorized:
        print("No autorizado con Google.")
        return None
    try:
        resp = google.get("/oauth2/v1/userinfo")
        if resp.ok:
            user_info = resp.json()
            print(f"Información obtenida de Google: {user_info}")
            return user_info
        else:
            print(f"Error al obtener la información del usuario, respuesta no OK: {resp.status_code}")
            return None

    except Exception as e:
        print(f"Error al obtener información del usuario de Google: {e}")
        return None

# Ruta de login con Google
@app.route("/google_login", methods=["POST"])
def google_login():
    """
    Maneja el proceso de autenticación con Google OAuth.
    Verifica el token recibido del frontend, busca o crea el usuario en la base de datos
    y establece la sesión del usuario.

    Returns:
        tuple: Una tupla conteniendo una respuesta JSON y un código de estado HTTP.
               Retorna un mensaje de éxito y código 200 si la autenticación es exitosa,
               o un mensaje de error y código 400 si el token es inválido o falta.
    """

    # Carga el client_id desde las variables de entorno
    google_client_id = app.config["GOOGLE_OAUTH_CLIENT_ID"]
    print(f"Google Client ID: {google_client_id}")  # Verifica que el Client ID esté correcto

    print("Entrando a google_login...")

    # Recibir el token desde el frontend
    data = request.get_json()
    token = data.get("token")

    if not token:
        return jsonify({"error": "Token de Google no proporcionado"}), 400

    try:
        # Verificar el token con Google
        idinfo = id_token.verify_oauth2_token(
            token, 
            requests.Request(), 
            google_client_id  # Usamos el client_id desde .env
        )

        # Si el token es válido, obtener la información del usuario
        user_info = {
            "id": idinfo["sub"],  # Google ID
            "email": idinfo["email"],
            "name": idinfo.get("name", ""),
        }

        # Buscar si el usuario ya existe
        user = User.query.filter(
            (User.google_id == user_info["id"]) | (User.email == user_info["email"])
        ).first()

        if not user:
            user = User(
                google_id=user_info["id"],
                username=user_info.get("name", "Usuario de Google"),
                email=user_info["email"],
                password=generate_password_hash(""),  # Asignar un hash vacío como "contraseña"
                rol="usuario"
            )
            db.session.add(user)
            db.session.commit()

        # Iniciar sesión
        session["user_id"] = user.id
        session["rol"] = user.rol

        return jsonify({"message": "Usuario autenticado", "user": user.username}), 200

    except ValueError as e:
        # El token es inválido
        print(f"Error al verificar el token de Google: {e}")
        return jsonify({"error": "Token inválido"}), 400

    
#  ----------------------- PÁGINAS PARA DESCARGAR LAS GUÍAS DOCENTES PARA UN CURSO ACADÉMICO DETERMINADO ----------------------------------------------------
@app.route('/pagina_pedir_anho')
def pagina_pedir_anho():
    """
    Renderiza la página para solicitar el año académico y tipo de estudio para la descarga de guías.
    """
    # Comprobar el idioma seleccionado en la sesión, por defecto 'en'
    idioma = session.get('idioma', 'es')
    tamano_texto = session.get('tamano_texto', 'normal')
    daltonismo = session.get('daltonismo', False)
    # Comprobar si el usuario está autenticado
    if 'user_id' not in session:
        return render_template('pagina_pedir_anho.html', 
                               rol='visitante', 
                               textos=textos[idioma], 
                               tamano_texto=tamano_texto,daltonismo=daltonismo)  # Contenido para visitantes
    else:
        rol = session['rol']
        return render_template('pagina_pedir_anho.html', 
                               rol=rol, 
                               textos=textos[idioma], 
                               tamano_texto=tamano_texto,daltonismo=daltonismo)  # Contenido según el rol



def verificar_si_existen_datos(anho, tipo_estudio):
    """
    Verifica si ya existen datos de búsqueda para un año y tipo de estudio dados en la base de datos.

    Args:
        anho (str): El año académico (ej. "2023-2024").
        tipo_estudio (str): El tipo de estudio ("grado", "master", o "ambos").

    Returns:
        bool: True si existen datos para la combinación año/tipo, False en caso contrario.
    """
    count = Busqueda.query.filter_by(anho=anho, tipo_programa=tipo_estudio).count()
    return count > 0



@app.route('/verificar_datos', methods=['POST'])
def verificar_datos():
    """
    Para verificar si ya existen datos para un año y tipo de estudio.

    Recibe el año y tipo de estudio de una solicitud POST (típicamente AJAX)
    y llama a `verificar_si_existen_datos` para comprobar la base de datos.
    Devuelve el resultado como un objeto JSON.

    Returns:
        json: Un objeto JSON indicando si existen datos (`datos_existentes`).
    """
    anho = request.form.get('anho')
    tipo_estudio = request.form.get('tipo_estudio')
    datos_existentes = verificar_si_existen_datos(anho, tipo_estudio)
    return jsonify({'datos_existentes': datos_existentes})


@app.route("/", methods=["GET", "POST"])
def procesar_anho():
    """
    Maneja la solicitud POST para procesar un año académico y tipo de estudio.
    Inicia un hilo para ejecutar los scripts de descarga y procesamiento de guías.

    Si la solicitud es POST:
    - Obtiene el año y tipo de estudio del formulario.
    - Valida el formato del año y el tipo de estudio.
    - Verifica si los datos para esa combinación ya existen en la base de datos.
    - Si no existen y las validaciones pasan, actualiza el estado global del proceso
      e inicia un nuevo hilo para ejecutar los scripts externos (`ejecutar_procesos`).
    - Redirige a la página de solicitud de datos de IA.
    Si la solicitud es GET, simplemente redirige a la página de solicitud de datos de IA.

    Returns:
        redirect: Redirige a la página de solicitud de datos de IA o a la página de solicitud de año si hay errores.
    """
    global estado_proceso
    if request.method == "POST":
        anho = request.form.get("anho")
        idioma = session.get('idioma', 'es')  # Obtener el idioma actual

        # Verificar el formato del año (####-####)
        if not anho_pattern(anho):
            flash(mensajes_flash[idioma]['formato_anho_invalido'], "error")
            return redirect(url_for('pagina_pedir_anho'))

       
        # Obtener los datos de tipo de estudio y grado/máster específico del formulario
        tipo_estudio = request.form.get("tipo_estudio", "ambos")

        # Validar si el tipo de estudio es correcto
        if tipo_estudio not in ["grado", "master", "ambos"]:
            flash(mensajes_flash[idioma]['tipo_estudio_invalido'], "error")
            return redirect(url_for('pagina_pedir_anho'))
        if verificar_si_existen_datos(anho, tipo_estudio):
            flash(mensajes_flash[idioma]['datos_ya_existen'], "info")
            return redirect(url_for('pagina_pedir_anho'))
        with lock:
            estado_proceso["en_proceso"] = True
            estado_proceso["mensaje"] = textos[idioma]['mensaje_cargando']
            estado_proceso["porcentaje"] = 0
            estado_proceso["completado"] = False

        
        # Crear y lanzar un hilo para ejecutar ambos scripts con los parámetros
        hilo = threading.Thread(target=ejecutar_procesos, args=(anho, tipo_estudio, idioma))
        hilo.start()
        
        return redirect(url_for('pagina_pedir_ia'))

    return redirect(url_for('pagina_pedir_ia'))

def anho_pattern(anho):
    """
    Verifica si el año tiene el formato correcto (####-####).

    Utiliza una expresión regular para validar el formato.

    Args:
        anho (str): El string del año a verificar.

    Returns:
        bool: True si el formato es correcto, False en caso contrario.
    """
    return bool(re.match(r"\d{4}-\d{4}", anho))


# Función que ejecuta los scripts en el orden correcto.
def ejecutar_procesos(anho, tipo_estudio="ambos", idioma='es'):
    """
    Ejecuta los scripts de descarga y procesamiento de guías docentes en un hilo separado.
    Actualiza el estado global del proceso durante la ejecución.

    Esta función se ejecuta en un hilo separado para no bloquear la aplicación Flask.
    Llama a scripts externos (`grados.py`, `guias_docentes.py`, `procesadoAsignaturas.py`)
    usando `subprocess.run` y actualiza el estado global (`estado_proceso`)
    con mensajes y porcentajes de progreso. Maneja posibles errores en la ejecución de los scripts.

    Args:
        anho (str): El año académico a procesar.
        tipo_estudio (str, optional): El tipo de estudio ("grado", "master", "ambos"). Por defecto es "ambos".
        idioma (str, optional): El idioma actual para los mensajes de estado. Por defecto es 'es'.
    """
    global estado_proceso
    try:
        # Ejecutar guias_docentes.py
        ruta_grados = os.path.join(os.getcwd(), 'sostenibilidad', 'grados.py')
        actualizar_estado(textos[idioma]['ejecutando_grados'], 10)

        # Ejecutar guias_docentes.py (un solo paso si no se necesita dividir)
        subprocess.run(['python3', ruta_grados, anho, tipo_estudio], check=True)
        actualizar_estado(textos[idioma]['ejecutando_grados'], 20)

        
        # Ejecutar guias_docentes.py
        ruta_guias = os.path.join(os.getcwd(), 'sostenibilidad', 'guias_docentes.py')
        actualizar_estado(textos[idioma]['ejecutando_guias'], 30)

        # Ejecutar guias_docentes.py (un solo paso si no se necesita dividir)
        subprocess.run(['python3', ruta_guias, anho, tipo_estudio], check=True)
        actualizar_estado(textos[idioma]['ejecutando_guias'], 60)

        # Ejecutar procesadoAsignaturas.py
        ruta_procesado = os.path.join(os.getcwd(), 'sostenibilidad', 'procesadoAsignaturas.py')
        actualizar_estado(textos[idioma]['ejecutando_asignaturas'], 70)

        # Ejecutar procesadoAsignaturas.py
        subprocess.run(['python3', ruta_procesado, tipo_estudio], check=True)
        actualizar_estado(textos[idioma]['ejecutando_asignaturas'], 90)

        # Marcar el proceso como completado
        actualizar_estado(textos[idioma]['proceso_completado'], 100)

        with lock:
            estado_proceso["completado"] = True  # Marcar el proceso como completado
    except subprocess.CalledProcessError as e:
        with lock:
            estado_proceso["mensaje"] = f"{textos[idioma]['error_script']} {e}"
    finally:
        with lock:
            estado_proceso["en_proceso"] = False
        

#  ----------------------- PÁGINA PARA EJECUTAR LA API ----------------------------------------------------
@app.route('/pagina_pedir_ia', methods=['GET','POST'])
def pagina_pedir_ia():
    """
    Renderiza la página para solicitar los datos de configuración de la API de IA.

    Obtiene el origen de la solicitud (para saber qué informe se quiere generar)
    y el año seleccionado de la sesión. Renderiza la plantilla `pagina_pedir_ia.html`
    pasando las preferencias del usuario y el año seleccionado.

    Returns:
        str: El HTML renderizado de la plantilla `pagina_pedir_ia.html`.
    """
    origen = session.get('origen', '')  # Obtiene el valor de sesión
    anho_seleccionado = request.form.get('anho')
    session['anho'] = anho_seleccionado

    # Comprobar el idioma seleccionado en la sesión, por defecto 'en'
    idioma = session.get('idioma', 'es')
    tamano_texto = session.get('tamano_texto', 'normal')
    daltonismo = session.get('daltonismo', False)
    # Comprobar si el usuario está autenticado
    if 'user_id' not in session:
        return render_template('pagina_pedir_ia.html', origen=origen,
                               rol='visitante', 
                               textos=textos[idioma], 
                               tamano_texto=tamano_texto,daltonismo=daltonismo,anho_seleccionado=session.get('anho'))  # Contenido para visitantes
    else:
        rol = session['rol']
        return render_template('pagina_pedir_ia.html', origen=origen,
                               rol=rol, 
                               textos=textos[idioma], 
                               tamano_texto=tamano_texto,daltonismo=daltonismo,anho_seleccionado=session.get('anho'))  # Contenido según el rol
    

def obtener_configuracion_actualizada(config_actual):
    """
    Obtiene la configuración de la API (base_url, api_key, model) de la solicitud POST.

    Si un campo no se proporciona en la solicitud, utiliza el valor de la configuración actual.

    Args:
        config_actual (dict): Diccionario con la configuración actual de la API.

    Returns:
        dict: Un diccionario con la configuración de la API actualizada.
    """ 
    base_url = request.form.get('base_url', '').strip() or config_actual.get("base_url")
    api_key = request.form.get('api_key', '').strip() or config_actual.get("api_key")
    model = request.form.get('model', '').strip() or config_actual.get("model")
    return {"base_url": base_url, "api_key": api_key, "model": model}

def validar_campos_por_informe(informe):
    """
    Valida que los campos necesarios para generar un informe específico estén presentes en la sesión.

    Args:
        informe (str): El tipo de informe a validar (ej. "6_8", "6_4").

    Returns:
        tuple | None: Una tupla (mensaje de error, código HTTP) si falta algún campo,
                      o None si todos los campos necesarios están presentes.
    """
    if informe == "6_8":
        anho = session.get('anho')
        if not anho:
            return "Error: No se seleccionaron todos los campos", 400
        return None
    elif informe == "6_4":
        excel = session.get('ruta_excel')
        if not excel:
            return "Error: No se ha subido ningún fichero.", 400
        return None
    return None

def manejar_informe_con_hilo(informe):
    """
    Inicia un hilo para ejecutar el script de generación de informe con los parámetros necesarios.

    Valida los campos necesarios para el informe, obtiene los parámetros de la sesión
    y lanza un nuevo hilo que ejecuta la función `ejecutar_informe`.

    Args:
        informe (str): El tipo de informe a generar.

    Returns:
        redirect | tuple: Redirige a la página principal si el hilo se inicia correctamente,
                          o retorna una tupla (mensaje de error, código HTTP) si la validación falla.
    """
    anho_seleccionado = ''
    excel = ''
    error = validar_campos_por_informe(informe)
    if error:
        return error

    if informe == "6_8":
        anho_seleccionado = session.get('anho')
    elif informe == "6_4":
        excel = session.get('ruta_excel')

    hilo = threading.Thread(target=ejecutar_informe, args=(anho_seleccionado, informe, excel))
    hilo.start()
    return redirect(url_for('pagina_principal'))

@app.route('/actualizar_api', methods=['GET','POST'])
def actualizar_api():
    """
    Maneja la solicitud POST para actualizar la configuración de la API y generar informes.

    Carga la configuración actual, obtiene la configuración actualizada del formulario,
    la guarda, determina el tipo de informe a generar y llama a la función
    correspondiente (`ejecutar_api` o `manejar_informe_con_hilo`) en un hilo separado.

    Returns:
        redirect | tuple: Redirige a la página principal si la operación es exitosa,
                          o retorna un mensaje de error y código HTTP si ocurre un problema.
    """
    try:
        informe_seleccionado = determinar_tipo_informe()
        config_actual = cargar_configuracion()

        nueva_config = obtener_configuracion_actualizada(config_actual)
        guardar_configuracion(nueva_config)

        if informe_seleccionado == "6_1":
            hilo = threading.Thread(target=ejecutar_api)
            hilo.start()
            return redirect(url_for('pagina_principal'))

        # Para otros informes: 1_19, 6_8, 6_4...
        response = manejar_informe_con_hilo(informe_seleccionado)
        if isinstance(response, tuple):  # Error con código HTTP
            return response
        return response

    except Exception as e:
        return f"Error al actualizar la API o generar el informe: {str(e)}", 500


def ejecutar_api():
    """
    Ejecuta el script `API.py` en un hilo separado.

    Este script es responsable de procesar las guías docentes y actualizar la base de datos
    con información de sostenibilidad utilizando la API de IA.

    Imprime mensajes de éxito o error en la consola.
    """
    try:
        ruta_api = os.path.join(os.getcwd(), 'sostenibilidad', 'API.py')
        # Ejecutar el archivo API.py (esto puede tomar tiempo)
        subprocess.run(['python3', ruta_api], check=True)
        print("Proceso completado correctamente.")
    except subprocess.CalledProcessError as e:
        print(f"Error ejecutando el script: {str(e)}")
    except Exception as e:
        print(f"Error en el hilo de ejecución: {str(e)}")


#  ----------------------- PÁGINA PARA VISUALIZAR LA BASE DE DATOS ----------------------------------------------------
@app.route('/consultar_busquedas', methods=['GET'])
def consultar_busquedas():
    """
    Maneja la página de consulta de la base de datos de búsquedas.

    Permite filtrar los resultados por año, tipo de programa, código de asignatura,
    nombre de archivo y modalidad. También maneja la paginación y la selección de columnas.
    Si la solicitud es AJAX, devuelve sugerencias para el autocompletado del código de asignatura.
    Si no es AJAX, renderiza la plantilla `consultar_busquedas.html` con los datos filtrados y paginados.

    Returns:
        json | str: Un objeto JSON con sugerencias si es una solicitud AJAX,
                    o el HTML renderizado de la página de consulta si no es AJAX.
    """
    # --- Si es una petición AJAX, devolvemos JSON para autocompletar ---
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        codigo_asignatura = request.args.get('codigo_asignatura', '')

        sugerencias = [a[0] for a in db.session.execute(
            db.select(Busqueda.codigo_asignatura)
              .distinct()
              .filter(Busqueda.codigo_asignatura.like(f'%{codigo_asignatura}%'))
              .execution_options(bind_key='busqueda')
        ).all()]

        return jsonify(sugerencias)

    # --- Si no es AJAX, se continúa con el flujo normal para renderizar la página ---
    idioma = session.get('idioma', 'es')
    tamano_texto = session.get('tamano_texto', 'normal')
    daltonismo = session.get('daltonismo', False)

    # Filtros desde la URL
    anho_seleccionado = request.args.get('anho')
    tipo_programa = request.args.get('tipo_programa')
    codigo_asignatura = request.args.get('codigo_asignatura')
    nombre_archivo = request.args.get('nombre_archivo')
    modalidad = request.args.get('modalidad')

    # Paginación
    page = request.args.get('page', 1, type=int)
    per_page = 100

    anhos_disponibles = [a[0] for a in db.session.execute(
        db.select(Busqueda.anho).distinct().execution_options(bind_key='busqueda')
    ).all()]

    tipos_programa = ["grado", "master"]

    codigo_asignaturas = [a[0] for a in db.session.execute(
        db.select(Busqueda.codigo_asignatura).distinct().execution_options(bind_key='busqueda')
    ).all()]

    nombre_archivos = [a[0] for a in db.session.execute(
        db.select(Busqueda.nombre_archivo).distinct().execution_options(bind_key='busqueda')
    ).all()]

    modalidad_disponibles = [a[0] for a in db.session.execute(
        db.select(Busqueda.modalidad).distinct().execution_options(bind_key='busqueda')
    ).all()]

    query = db.session.query(Busqueda).execution_options(bind_key='busqueda')

    if anho_seleccionado:
        query = query.filter(Busqueda.anho == anho_seleccionado)
        if tipo_programa and tipo_programa != "Todos":
            query = query.filter(Busqueda.tipo_programa == tipo_programa)
        if codigo_asignatura and codigo_asignatura != "Todos":
            query = query.filter(Busqueda.codigo_asignatura == codigo_asignatura)
        if nombre_archivo and nombre_archivo != "Todos":
            query = query.filter(Busqueda.nombre_archivo == nombre_archivo)
        if modalidad and modalidad != "Todos":
            query = query.filter(Busqueda.modalidad == modalidad)

    busquedas_paginadas = query.paginate(page=page, per_page=per_page, error_out=False)

    params = request.args.to_dict(flat=False)
    if 'page' in params:
        del params['page']

    total_pages = busquedas_paginadas.pages
    start_page = max(1, page - 3)
    end_page = min(total_pages, page + 3)
    
    columnas_disponibles = ["anho", "tipo_programa", "codigo_asignatura", "modalidad", "sostenibilidad", "nombre_archivo"]
    columnas_seleccionadas = request.args.getlist('columnas') or columnas_disponibles

    mapeo_columnas_a_claves = {
        "anho": "anho_tabla",
        "tipo_programa": "tipo",
        "codigo_asignatura": "codigo_Asignatura",
        "modalidad": "modalidad",
        "sostenibilidad": "sostenibilidad",
        "nombre_archivo": "nombre_archivo"
    }


    return render_template(
        'consultar_busquedas.html',
        columnas_disponibles=columnas_disponibles,
        columnas_seleccionadas=columnas_seleccionadas,
        claves_columnas=mapeo_columnas_a_claves,
        textos=textos[idioma],
        tamano_texto=tamano_texto,
        daltonismo=daltonismo,
        anhos=anhos_disponibles,
        tipos_programa=tipos_programa,
        codigo_asignaturas=codigo_asignaturas,
        nombre_archivos=nombre_archivos,
        modalidad=modalidad_disponibles,
        selected_anho=anho_seleccionado,
        selected_tipo_programa=tipo_programa,
        selected_codigo_asignatura=codigo_asignatura,
        selected_nombre_archivo=nombre_archivo,
        selected_modalidad=modalidad,
        busquedas=busquedas_paginadas.items,
        page=page,
        total_pages=total_pages,
        start_page=start_page,
        end_page=end_page,
        params=params
    )
    
    


#  ----------------------- EDITAR BASE DE DATOS  ----------------------------------------------------
@app.route('/editar_busqueda/<int:id>', methods=['GET', 'POST'])
def editar_busqueda(id):
    """
    Maneja la edición de un registro de búsqueda en la base de datos.

    Solo accesible para usuarios con rol 'admin'. Permite modificar los campos
    de un registro de búsqueda específico.

    Args:
        id (int): El ID del registro de búsqueda a editar.

    Returns:
        redirect | str: Redirige a la página de consulta de búsquedas después de editar,
                        o renderiza la plantilla de edición si es una solicitud GET
                        o si hay un error. Retorna "No encontrada" con código 404 si el ID no existe.
    """
    idioma = session.get('idioma', 'es')
    tamano_texto = session.get('tamano_texto', 'normal')
    daltonismo = session.get('daltonismo', False)

    if session.get('rol') != 'admin':
         return redirect(url_for('pagina_informe_6_1'))

    busqueda = db.session.get(Busqueda, id)
    if not busqueda:
        return "No encontrada", 404

    if request.method == 'POST':
        busqueda.anho = request.form['anho']
        busqueda.tipo_programa = request.form['tipo_programa']
        busqueda.codigo_asignatura = request.form['codigo_asignatura']
        busqueda.nombre_archivo = request.form['nombre_archivo']
        busqueda.modalidad = request.form['modalidad']
        busqueda.sostenibilidad = request.form['sostenibilidad']
        db.session.commit()
        flash(mensajes_flash[idioma]['busqueda_editada'], "succes")

        return redirect(url_for('consultar_busquedas'))

    return render_template('editar_busqueda.html', busqueda=busqueda, textos=textos[idioma],
        tamano_texto=tamano_texto,
        daltonismo=daltonismo)
    
@app.route('/eliminar_busqueda/<int:id>', methods=['POST'])
def eliminar_busqueda(id):
    """
    Maneja la eliminación de un registro de búsqueda en la base de datos.

    Solo accesible para usuarios con rol 'admin'. Elimina un registro de búsqueda
    específico por su ID.

    Args:
        id (int): El ID del registro de búsqueda a eliminar.

    Returns:
        redirect: Redirige a la página de consulta de búsquedas después de eliminar,
                  o si hay un error o acceso denegado.
    """
    idioma = session.get('idioma', 'es')

    if session.get('rol') != 'admin':
        return redirect(url_for('pagina_informe_6_1'))

    busqueda = db.session.get(Busqueda, id)
    if not busqueda:
        flash(mensajes_flash[idioma]['busqueda_no_encontrada'], "error")
        return redirect(url_for('consultar_busquedas'))

    db.session.delete(busqueda)
    db.session.commit()
    flash(mensajes_flash[idioma]['busqueda_eliminada'], "success")
    return redirect(url_for('consultar_busquedas'))


@app.route('/confirmar_eliminacion/<int:id>')
def confirmar_eliminacion(id):
    """
    Renderiza la página de confirmación antes de eliminar un registro de búsqueda.

    Solo accesible para usuarios con rol 'admin'. Muestra los detalles del registro
    a eliminar y pide confirmación al usuario.

    Args:
        id (int): El ID del registro de búsqueda a confirmar eliminación.

    Returns:
        str: El HTML renderizado de la página de confirmación, o redirige si no es admin
             o si el registro no existe.
    """

    if session.get('rol') != 'admin':
        return "Acceso denegado", 403

    busqueda = db.session.get(Busqueda, id)
    if not busqueda:
        flash(mensajes_flash[idioma]['busqueda_no_encontrada'], "error")
        return redirect(url_for('consultar_busquedas'))

    idioma = session.get('idioma', 'es')
    tamano_texto = session.get('tamano_texto', 'normal')
    daltonismo = session.get('daltonismo', False)

    return render_template("confirmar_eliminacion.html",
                           busqueda=busqueda,
                           textos=textos[idioma],
                           tamano_texto=tamano_texto,
                           daltonismo=daltonismo)




#  ----------------------- BARRA DE PROGRESO  ----------------------------------------------------
# Función para actualizar el estado del proceso
def actualizar_estado(mensaje, porcentaje, en_proceso=False, completado=False):
    """
    Actualiza el estado global del proceso en segundo plano.

    Esta función se utiliza para comunicar el progreso de una tarea de larga duración
    (como la descarga y procesamiento de guías) al hilo principal de la aplicación web.
    Utiliza un bloqueo (lock) para asegurar que solo un hilo pueda modificar
    la variable global `estado_proceso` a la vez, evitando condiciones de carrera.

    Args:
        mensaje (str): Un mensaje descriptivo del estado actual (ej. "Descargando guías...").
        porcentaje (int): El porcentaje de progreso de la tarea (0-100).
        en_proceso (bool, optional): Indica si la tarea está actualmente en ejecución. Por defecto es False.
        completado (bool, optional): Indica si la tarea ha finalizado con éxito. Por defecto es False.
    """
    global estado_proceso
    with lock:
        estado_proceso["mensaje"] = mensaje
        estado_proceso["porcentaje"] = porcentaje
        estado_proceso["en_proceso"] = en_proceso
        estado_proceso["completado"] = completado


@app.route('/estado_proceso')
def estado_proceso_api():
    """
    Endpoint API que devuelve el estado actual del proceso en formato JSON.

    Esta ruta es consultada periódicamente por el frontend (JavaScript) para
    obtener las actualizaciones del estado del proceso en segundo plano y
    actualizar la barra de progreso en la interfaz de usuario.
    Utiliza un bloqueo (lock) para asegurar un acceso seguro a la variable global.

    Returns:
        json: Un objeto JSON que contiene el diccionario `estado_proceso` actual.
    """
    with lock:
        return jsonify(estado_proceso)

@app.route('/progreso')
def progreso():
    """
    Renderiza la página HTML que muestra la barra de progreso.

    Obtiene las preferencias de usuario (idioma, tamaño de texto, modo daltonismo)
    de la sesión y las pasa a la plantilla `progreso.html` para asegurar que la
    interfaz se muestre según las preferencias del usuario.

    Returns:
        str: El HTML renderizado de la plantilla `progreso.html`.
    """
    idioma = session.get('idioma', 'es')
    tamano_texto = session.get('tamano_texto', 'normal')
    daltonismo = session.get('daltonismo', False)
    
    return render_template('progreso.html', 
                           textos=textos[idioma], 
                           tamano_texto=tamano_texto, 
                           daltonismo=daltonismo)


#  ----------------------- GENERAR INFORMES ----------------------------------------------------
@app.route('/generar_informe', methods=['POST'])
def generar_informe():
    """
    Maneja la solicitud POST para generar un informe específico.

    Determina el tipo de informe a generar basándose en la sesión,
    obtiene los parámetros necesarios (año, archivo Excel) del formulario
    si son requeridos por el informe, e inicia un hilo separado para
    ejecutar el script de generación del informe. Redirige a la página
    principal después de iniciar el proceso.

    Returns:
        redirect | tuple: Redirige a la página principal si el hilo se inicia correctamente,
                          o retorna un mensaje de error y código HTTP si faltan campos
                          o si ocurre una excepción.
    """
    try:
        
        informe_seleccionado = determinar_tipo_informe()
        anho_seleccionado = ''
        excel = ''
        if informe_seleccionado == "6_1" or informe_seleccionado == "6_2" or informe_seleccionado=='6_3' :
            # Obtener el año seleccionado desde el formulario
            anho_seleccionado = request.form.get('anho')
            if not anho_seleccionado:
                return "Error: No se seleccionaron todos los campos", 400
        elif informe_seleccionado == "6_7":
            # Obtener el año seleccionado desde el formulario
            anho_seleccionado = request.form.get('anho')
            if not anho_seleccionado:
                return "Error: No se seleccionaron todos los campos", 400
        # Iniciar un hilo para ejecutar el informe con el año como argumento
        hilo = threading.Thread(target=ejecutar_informe, args=(anho_seleccionado,informe_seleccionado,excel))
        hilo.start()

        # Redirigir a la página principal después de iniciar el proceso
        return redirect(url_for('pagina_principal'))

    except Exception as e:
        return f"Error al generar el informe: {str(e)}", 500

def ejecutar_informe(anho,informe,excel):
    """
    Ejecuta el script de generación de informe general en un hilo separado.

    Construye la ruta al script `general.py` y lo ejecuta como un subproceso
    de Python, pasando el año, el tipo de informe y la ruta del archivo Excel
    como argumentos de línea de comandos. Imprime mensajes de éxito o error
    en la consola.

    Args:
        anho (str): El año seleccionado para el informe (puede ser una cadena vacía si no aplica).
        informe (str): El código del informe a generar (ej. "6_1", "6_4").
        excel (str): La ruta al archivo Excel (puede ser una cadena vacía si no aplica).
    """
    try:
        ruta_informe = os.path.join(os.getcwd(), 'generar_informe', 'general.py')
        if not os.path.exists(ruta_informe):
            raise FileNotFoundError(f"El archivo {ruta_informe} no existe.")
        
        # Ejecutar el script con el año seleccionado como argumento
        subprocess.run(['python3', ruta_informe, anho, informe,excel], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error ejecutando el script: {str(e)}")
    except Exception as e:
        print(f"Error en el hilo de ejecución: {str(e)}")
        
def determinar_tipo_informe():
    """
    Determina el código del informe a generar basándose en el valor de la sesión 'origen'.

    El valor de 'origen' se establece en las rutas de las páginas de informe
    para indicar qué informe se seleccionó. Esta función mapea ese valor a
    un código de informe específico.

    Returns:
        str: El código del informe seleccionado (ej. "1_19", "6_1", "6_4").
             Retorna una cadena vacía si el valor de sesión 'origen' no coincide
             con ningún informe conocido.
    """
    origen = session.get('origen', '')  # Obtiene el valor de sesión
    if origen == "pagina_informe_1_19":
        return "1_19"
    # No se puede usar referrer ya que como ambos informes usan la misma página, el referrer de ambos es el mismo.
    elif origen == "pagina_informe_6_1":
        return "6_1"
    elif origen == "pagina_informe_6_2":
        return "6_2"
    elif origen == "pagina_informe_6_3":
        return "6_3"
    elif origen == "pagina_informe_6_4":
        return "6_4"
    elif origen == "pagina_informe_6_7":
        return "6_7"
    elif origen == "pagina_informe_6_8":
        return "6_8"
    
#  ----------------------- INFORME 1_19 --------------------------------------

# Ruta para la página donde se realiza la descarga del informe
@app.route('/pagina_informe_1_19')
def pagina_informe_1_19():
    """
    Renderiza la página para generar el informe 1.19 (Policy on sustainability).

    Establece el origen de la solicitud en la sesión como "1_19" y renderiza
    la plantilla `pagina_informe_1_19.html` pasando las preferencias del usuario.

    Returns:
        str: El HTML renderizado de la plantilla `pagina_informe_1_19.html`.
    """
    session['origen'] = 'pagina_informe_1_19'

    idioma = session.get('idioma', 'es')
    tamano_texto = session.get('tamano_texto', 'normal')
    daltonismo = session.get('daltonismo', False)

    if 'user_id' not in session:
        return render_template('pagina_informe_1_19.html', 
                               rol='visitante', 
                               textos=textos[idioma], 
                               tamano_texto=tamano_texto, 
                               daltonismo=daltonismo)
    else:
        rol = session['rol']
        return render_template('pagina_informe_1_19.html', 
                               rol=rol, 
                               textos=textos[idioma], 
                               tamano_texto=tamano_texto, 
                               daltonismo=daltonismo)

#  ----------------------- INFORME 6_1 --------------------------------------
@app.route('/pagina_informe_6_1')
def pagina_informe_6_1():
    """
    Renderiza la página para generar el informe 6.1 (Sustainability courses).

    Establece el origen de la solicitud en la sesión como "6_1" y renderiza
    la plantilla `pagina_informe_6_1.html` pasando las preferencias del usuario.

    Returns:
        str: El HTML renderizado de la plantilla `pagina_informe_6_1.html`.
    """
    session['origen'] = 'pagina_informe_6_1'

    idioma = session.get('idioma', 'es')
    tamano_texto = session.get('tamano_texto', 'normal')
    daltonismo = session.get('daltonismo', False)

    # Obtener años únicos desde la base de datos
    anhos_disponibles = db.session.query(Busqueda.anho).distinct().order_by(Busqueda.anho.desc()).all()
    # Crear una nueva lista para almacenar los años disponibles
    nuevos_anhos_disponibles = []

    # Iterar sobre cada fila de anhos_disponibles
    for row in anhos_disponibles:
        # Asegúrate de extraer el primer valor de cada tupla
        nuevos_anhos_disponibles.append(row[0])

    if 'user_id' not in session:
        return render_template('pagina_informe_6_1.html', 
                               rol='visitante', 
                               textos=textos[idioma], 
                               tamano_texto=tamano_texto, 
                               daltonismo=daltonismo,
                               nuevos_anhos_disponibles=nuevos_anhos_disponibles)
    else:
        rol = session['rol']
        return render_template('pagina_informe_6_1.html', 
                               rol=rol, 
                               textos=textos[idioma], 
                               tamano_texto=tamano_texto, 
                               daltonismo=daltonismo,
                               nuevos_anhos_disponibles=nuevos_anhos_disponibles)
   
   
         
@app.route('/selecciona_anho_informe', methods=['GET', 'POST'])
def selecciona_anho_informe():
    """
    Renderiza la página para seleccionar el año del informe.

    Obtiene los años disponibles desde la base de datos y renderiza la plantilla
    `selecciona_anho_informe.html`, incluyendo las preferencias del usuario.

    Returns:
        str: HTML renderizado de la plantilla `selecciona_anho_informe.html`.
    """
    origen = session.get('origen', '')  # Obtiene el valor de sesión
    idioma = session.get('idioma', 'es')
    tamano_texto = session.get('tamano_texto', 'normal')
    daltonismo = session.get('daltonismo', False)
          
    # Obtener años únicos desde la base de datos
    anhos_disponibles = db.session.query(Busqueda.anho).distinct().order_by(Busqueda.anho.desc()).all()
    # Crear una nueva lista para almacenar los años disponibles
    nuevos_anhos_disponibles = []

    # Iterar sobre cada fila de anhos_disponibles
    for row in anhos_disponibles:
        # Asegúrate de extraer el primer valor de cada tupla
        nuevos_anhos_disponibles.append(row[0])


    return render_template('selecciona_anho_informe.html',   origen=origen,
                               textos=textos[idioma], 
                               tamano_texto=tamano_texto, 
                               daltonismo=daltonismo,
                               nuevos_anhos_disponibles=nuevos_anhos_disponibles)  
 
 
 #  ----------------------- INFORME 6_2 -------------------------------------- 

@app.route('/pagina_informe_6_2')
def pagina_informe_6_2():
    """
    Renderiza la página para generar el informe 6.2 (Total Number of Courses/Subjects Offered).

    Establece el origen de la solicitud en la sesión como "6_2" y renderiza
    la plantilla `pagina_informe_6_2.html` pasando las preferencias del usuario.

    Returns:
        str: El HTML renderizado de la plantilla `pagina_informe_6_2.html`.
    """
    session['origen'] = 'pagina_informe_6_2'

    idioma = session.get('idioma', 'es')
    tamano_texto = session.get('tamano_texto', 'normal')
    daltonismo = session.get('daltonismo', False)

    # Obtener años únicos desde la base de datos
    anhos_disponibles = db.session.query(Busqueda.anho).distinct().order_by(Busqueda.anho.desc()).all()
    # Crear una nueva lista para almacenar los años disponibles
    nuevos_anhos_disponibles = []

    # Iterar sobre cada fila de anhos_disponibles
    for row in anhos_disponibles:
        # Asegúrate de extraer el primer valor de cada tupla
        nuevos_anhos_disponibles.append(row[0])

    if 'user_id' not in session:
        return render_template('pagina_informe_6_2.html', 
                               rol='visitante', 
                               textos=textos[idioma], 
                               tamano_texto=tamano_texto, 
                               daltonismo=daltonismo,
                               nuevos_anhos_disponibles=nuevos_anhos_disponibles)
    else:
        rol = session['rol']
        return render_template('pagina_informe_6_2.html', 
                               rol=rol, 
                               textos=textos[idioma], 
                               tamano_texto=tamano_texto, 
                               daltonismo=daltonismo,
                               nuevos_anhos_disponibles=nuevos_anhos_disponibles)
        
         
 #  ----------------------- INFORME 6_3 -------------------------------------- 

@app.route('/pagina_informe_6_3')
def pagina_informe_6_3():
    """
    Renderiza la página para generar el informe 6.3 (Ratio of sustainability courses to total courses/subjects).

    Establece el origen de la solicitud en la sesión como "6_3" y renderiza
    la plantilla `pagina_informe_6_3.html` pasando las preferencias del usuario.

    Returns:
        str: El HTML renderizado de la plantilla `pagina_informe_6_3.html`.
    """
    session['origen'] = 'pagina_informe_6_3'

    idioma = session.get('idioma', 'es')
    tamano_texto = session.get('tamano_texto', 'normal')
    daltonismo = session.get('daltonismo', False)

    # Obtener años únicos desde la base de datos
    anhos_disponibles = db.session.query(Busqueda.anho).distinct().order_by(Busqueda.anho.desc()).all()
    # Crear una nueva lista para almacenar los años disponibles
    nuevos_anhos_disponibles = []

    # Iterar sobre cada fila de anhos_disponibles
    for row in anhos_disponibles:
        # Asegúrate de extraer el primer valor de cada tupla
        nuevos_anhos_disponibles.append(row[0])

    if 'user_id' not in session:
        return render_template('pagina_informe_6_3.html', 
                               rol='visitante', 
                               textos=textos[idioma], 
                               tamano_texto=tamano_texto, 
                               daltonismo=daltonismo,
                               nuevos_anhos_disponibles=nuevos_anhos_disponibles)
    else:
        rol = session['rol']
        return render_template('pagina_informe_6_3.html', 
                               rol=rol, 
                               textos=textos[idioma], 
                               tamano_texto=tamano_texto, 
                               daltonismo=daltonismo,
                               nuevos_anhos_disponibles=nuevos_anhos_disponibles)
        
#  ----------------------- INFORME 6_4 -------------------------------------- 
# Ruta para la página donde se realiza la descarga del informe
@app.route('/pagina_informe_6_4')
def pagina_informe_6_4():
    """
    Renderiza la página para generar el informe 6.4 (Total Research Funds Dedicated to Sustainability Research (in US Dollars)).

    Establece el origen de la solicitud en la sesión como "6_4" y renderiza
    la plantilla `pagina_informe_6_4.html` pasando las preferencias del usuario.

    Returns:
        str: El HTML renderizado de la plantilla `pagina_informe_6_4.html`.
    """
    session['origen'] = 'pagina_informe_6_4'

    idioma = session.get('idioma', 'es')
    tamano_texto = session.get('tamano_texto', 'normal')
    daltonismo = session.get('daltonismo', False)

    # Obtener años únicos desde la base de datos
    anhos_disponibles = db.session.query(Busqueda.anho).distinct().order_by(Busqueda.anho.desc()).all()
    # Crear una nueva lista para almacenar los años disponibles
    nuevos_anhos_disponibles = []

    # Iterar sobre cada fila de anhos_disponibles
    for row in anhos_disponibles:
        # Asegúrate de extraer el primer valor de cada tupla
        nuevos_anhos_disponibles.append(row[0])

    if 'user_id' not in session:
        return render_template('pagina_informe_6_4.html', 
                               rol='visitante', 
                               textos=textos[idioma], 
                               tamano_texto=tamano_texto, 
                               daltonismo=daltonismo,
                               nuevos_anhos_disponibles=nuevos_anhos_disponibles)
    else:
        rol = session['rol']
        return render_template('pagina_informe_6_4.html', 
                               rol=rol, 
                               textos=textos[idioma], 
                               tamano_texto=tamano_texto, 
                               daltonismo=daltonismo,
                               nuevos_anhos_disponibles=nuevos_anhos_disponibles)  

def allowed_file(filename):
    """
    Verifica si el archivo tiene una extensión permitida.

    Permite únicamente archivos Excel con extensiones '.xlsx' o '.xls'.

    Args:
        filename (str): Nombre del archivo.

    Returns:
        bool: True si la extensión es válida, False en caso contrario.
    """
    ALLOWED_EXTENSIONS = {'xlsx', 'xls'}  # Extensiones permitidas
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS



@app.route('/subir_excel', methods=['POST'])
def subir_excel():
    """
    Procesa la subida de un archivo Excel para el informe 6.4.

    Guarda el archivo en el sistema y almacena su ruta en la sesión.

    Returns:
        str: Redirección a la página del informe con mensajes de éxito o error.
    """
    idioma = session.get('idioma', 'es')  

    if 'archivo_excel' not in request.files:
        flash(mensajes_flash[idioma]['no_archivo_encontrado'], 'error')
        return redirect(url_for('pagina_informe_6_4'))

    archivo = request.files['archivo_excel']

    if archivo.filename == '':
        flash(mensajes_flash[idioma]['no_seleccion_archivo'], 'error')
        return redirect(url_for('pagina_informe_6_4'))

    if archivo and allowed_file(archivo.filename):
        filename = secure_filename(archivo.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        archivo.save(filepath)

        # Guarda la ruta del archivo en la sesión
        session['ruta_excel'] = filepath
        flash(mensajes_flash[idioma]['archivo_subido_correctamente'], 'success')
        return redirect(url_for('pagina_informe_6_4'))

    flash(mensajes_flash[idioma]['tipo_archivo_no_permitido'], 'error')
    return redirect(url_for('pagina_informe_6_4'))


@app.route('/cancelar_fichero')
def cancelar_fichero():
    """
    Elimina la ruta del archivo Excel previamente subido desde la sesión.

    Returns:
        str: Redirección a la página del informe 6.4.
    """
    # Limpiar la clave de la ruta del archivo en la sesión
    session.pop('ruta_excel', None)  # Eliminar 'ruta_excel' de la sesión si existe
    return redirect(url_for('pagina_informe_6_4'))  # Redirigir a la página de informe 6_4


#  ----------------------- INFORME 6_7 -------------------------------------- 
# Ruta para la página donde se realiza la descarga del informe
@app.route('/pagina_informe_6_7')
def pagina_informe_6_7():
    """
    Renderiza la página para generar el informe 6.7 (Number of scholarly publications on sustainability).

    Establece el origen de la solicitud en la sesión como "6_7" y renderiza
    la plantilla `pagina_informe_6_7.html` pasando las preferencias del usuario.

    Returns:
        str: El HTML renderizado de la plantilla `pagina_informe_6_7.html`.
    """
    session['origen'] = 'pagina_informe_6_7'

    idioma = session.get('idioma', 'es')
    tamano_texto = session.get('tamano_texto', 'normal')
    daltonismo = session.get('daltonismo', False)

    # Obtener años únicos desde la base de datos
    anhos_disponibles = db.session.query(Busqueda.anho).distinct().order_by(Busqueda.anho.desc()).all()
    # Crear una nueva lista para almacenar los años disponibles
    nuevos_anhos_disponibles = []

    # Iterar sobre cada fila de anhos_disponibles
    for row in anhos_disponibles:
        # Asegúrate de extraer el primer valor de cada tupla
        nuevos_anhos_disponibles.append(row[0])

    if 'user_id' not in session:
        return render_template('pagina_informe_6_7.html', 
                               rol='visitante', 
                               textos=textos[idioma], 
                               tamano_texto=tamano_texto, 
                               daltonismo=daltonismo,
                               nuevos_anhos_disponibles=nuevos_anhos_disponibles)
    else:
        rol = session['rol']
        return render_template('pagina_informe_6_7.html', 
                               rol=rol, 
                               textos=textos[idioma], 
                               tamano_texto=tamano_texto, 
                               daltonismo=daltonismo,
                               nuevos_anhos_disponibles=nuevos_anhos_disponibles) 
        
#  ----------------------- INFORME 6_8 -------------------------------------- 
# Ruta para la página donde se realiza la descarga del informe
@app.route('/pagina_informe_6_8')
def pagina_informe_6_8():
    """
    Renderiza la página para generar el informe 6.7 (Number of scholarly publications on sustainability).

    Establece el origen de la solicitud en la sesión como "6_7" y renderiza
    la plantilla `pagina_informe_6_7.html` pasando las preferencias del usuario.

    Returns:
        str: El HTML renderizado de la plantilla `pagina_informe_6_7.html`.
    """
    session['origen'] = 'pagina_informe_6_8'

    idioma = session.get('idioma', 'es')
    tamano_texto = session.get('tamano_texto', 'normal')
    daltonismo = session.get('daltonismo', False)

    # Obtener años únicos desde la base de datos
    anhos_disponibles = db.session.query(Busqueda.anho).distinct().order_by(Busqueda.anho.desc()).all()
    # Crear una nueva lista para almacenar los años disponibles
    nuevos_anhos_disponibles = []

    # Iterar sobre cada fila de anhos_disponibles
    for row in anhos_disponibles:
        # Asegúrate de extraer el primer valor de cada tupla
        nuevos_anhos_disponibles.append(row[0])

    if 'user_id' not in session:
        return render_template('pagina_informe_6_8.html', 
                               rol='visitante', 
                               textos=textos[idioma], 
                               tamano_texto=tamano_texto, 
                               daltonismo=daltonismo,
                               nuevos_anhos_disponibles=nuevos_anhos_disponibles)
    else:
        rol = session['rol']
        return render_template('pagina_informe_6_8.html', 
                               rol=rol, 
                               textos=textos[idioma], 
                               tamano_texto=tamano_texto, 
                               daltonismo=daltonismo,
                               nuevos_anhos_disponibles=nuevos_anhos_disponibles)  


#  ----------------------- CREACIÓN DEL SUPERADMIN -------------------------------------- 

def crear_admin_por_defecto():
    """
    Crea un usuario superadministrador por defecto si no existe.

    Este usuario se crea con nombre de usuario 'admin' y una contraseña obtenida
    desde una variable de entorno `ADMIN_PASSWORD`.

    """
    admin_username = "admin"
    admin_password = "scrypt:32768:8:1$dEnb6jRIMdpd4KkJ$a55bb550722ebf5ffcc8b8af5a231f7c35c08c53657776a62131a6368cefbf3ea3acbd42dd7c23aca6ee6e16c753ea44a86ea441aae84ff7a086f8583e3580bd"
    # Verifica si ya existe
    admin = User.query.filter_by(username=admin_username).first()
    if not admin:
        nuevo_admin = User(
            username=admin_username,
            password=admin_password,
            rol="admin",
            email=None  # Ya no es necesario
        )
        db.session.add(nuevo_admin)
        db.session.commit()
        print("Usuario administrador creado.")
    else:
        print("El usuario administrador ya existe.")


#  ----------------------- CAMBIO DE ROL -------------------------------------- 
#  Función que verifica el nombre de usuario y el rol, para que solo los administradores puedan designar a nuevos administradores, y solo el root, pueda degradar administradores a roles de usuario.

@app.route('/cambiar_a_admin', methods=['GET', 'POST'])
def cambiar_a_admin():
    """
    Permite a un administrador cambiar el rol de otro usuario.

    Solo los administradores pueden acceder a esta vista. Además, únicamente el usuario
    superadministrador (`admin`) puede degradar a otros administradores al rol de usuario.

    Renderiza la plantilla `cambiar_a_admin.html` y gestiona el formulario de cambio de rol.

    Returns:
        str: HTML renderizado o redirección según el resultado del proceso.
    """
    idioma = session.get('idioma', 'es')
    tamano_texto = session.get('tamano_texto', 'normal')
    daltonismo = session.get('daltonismo', False)

    if 'rol' not in session or 'username' not in session:
        flash(mensajes_flash[idioma]['debes_iniciar_sesion'], 'error')
        return redirect(url_for('login'))

    rol = session['rol']
    username = session['username']

    if rol != 'admin':
        flash(mensajes_flash[idioma]['no_tienes_permiso'], 'error')
        return redirect(url_for('pagina_principal'))

    if request.method == 'POST':
        email = request.form['email']
        nuevo_rol = request.form.get('nuevo_rol')  # 'admin' o 'usuario'
        usuario = User.query.filter_by(email=email).first()

        if not usuario:
            flash(mensajes_flash[idioma]['correo_no_encontrado'], 'error')
            return redirect(url_for('cambiar_a_admin'))

        if usuario.username == 'admin':
            flash(mensajes_flash[idioma]['no_se_puede_modificar_admin'], 'error')
            return redirect(url_for('cambiar_a_admin'))

        # Si se intenta degradar a un admin a usuario, solo el superadmin puede hacerlo
        if usuario.rol == 'admin' and nuevo_rol == 'usuario':
            if username != 'admin':
                flash(mensajes_flash[idioma]['solo_superadmin_degrada'], 'error')
                return redirect(url_for('cambiar_a_admin'))

        if usuario.rol != nuevo_rol:
            usuario.rol = nuevo_rol
            db.session.commit()
            flash(mensajes_flash[idioma]['rol_cambiado'].format(email, nuevo_rol), 'success')
        else:
            flash(mensajes_flash[idioma]['rol_ya_tiene'], 'info')

        return redirect(url_for('perfil'))

    return render_template('cambiar_a_admin.html', rol=rol, 
                           textos=textos[idioma], 
                           tamano_texto=tamano_texto, 
                           daltonismo=daltonismo)



#  ----------------------- MAIN  ----------------------------------------------------
if __name__ == '__main__':
    # Crear las tablas de la base de datos
    with app.app_context():

        db.create_all()

        crear_admin_por_defecto()  
    app.run(debug=True)