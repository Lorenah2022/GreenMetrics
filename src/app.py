# --- Flask Core Modules ---
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy

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

# Cargar variables desde .env
load_dotenv()

app = Flask(__name__)


os.environ["PYTHONUNBUFFERED"] = "1"
sys.stdout.reconfigure(line_buffering=True)


# Protege la aplicación Flask contra manipulaciones y ataques
app.secret_key = secrets.token_hex(32)
# Configuración de la base de datos PostgreSQL
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")
app.config['SQLALCHEMY_BINDS'] = {
    'busqueda': os.getenv("DATABASE_BINDS")  # Base de datos secundaria para OAuth o auditoría
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

 # Diccionario de traducciones
textos = {
    
    'en': {
        'aceptar': 'Accept',
        'actualizar_perfil': 'Update profile',
        'ajustes': 'Settings',
        'anho':'Year',
        'api_key': 'API key',
        'base_url': 'URL base',
        'busquedas_anteriores':'Previous Searches',
        'cancelar': 'Cancel',
        'cerrar_sesion': 'Logout',
        'confirmar_contrasenha': 'Confirm password',
        'contenido': 'Content visible only for visitors.',
        'codigo_Asignatura':'Subject code',
        'criterio_1': 'The password must have at least one uppercase letter, one lowercase letter, and one number.',
        'criterio_2': 'Additionally, a minimum of 8 characters.',
        'criterio_3': '* If you do not fill in the password field, it will not be updated.',
        'datos_IA': 'IA data',
        'descargar_datos_nuevos': 'Download new data',
        'descargar_informe':'Download report',
        'ejecutando_grados': 'Downloading the links to the addresses of bachelors and masters degrees.',
        'ejecutando_guias': 'Downloading guias....',
        'ejecutando_asignaturas':'The subjects are being processed..... ',
        'en': 'English',
        'error_script': 'Error running the script:',
        'espanol': 'Spanish',
        'guardar':'Save changes',
        'grande':'Big',
        'introducir_anho': 'Enter the year from which you want to extract the metrics. (Ex. 2023-2024)',
        'introducir_datos_IA': 'Enter the following data, if not the default IA will be used (Llama-8B-GGUF)',
        'IA_tit': 'IA',
        'ingles': 'English',
        'iniciar_sesion': 'Login',
        'informe_1_19':'Report 1_19',
        'informe_6_1':'Report 6_1',
        'myModel': 'Model',
        'mensaje_cargando': 'Loading... This might take a few minutes...',
        'modo_daltonismo': 'Daltonism',
        'modalidad':'modality',
        'nueva_contrasenha': 'New password. *',
        'nombre_archivo':'File name',
        'normal': 'Medium',
        'no_busquedas':'No previous searches were found.',
        'opcion_ambos':'Both',
        'opcion_grado':'Degree',
        'opcion_master':'Master',
        'pequeno': 'Small',
        'perfil': 'Profile',
        'proceso_completado': 'Process successfully completed for the year',
        'progreso_titulo': 'Process Progress',
        'realizar_busqueda_nueva': 'Search',
        'sel_idioma': 'Select language:',
        'sel_letra': 'Select Font Size:',
        'seleccionar_tipo_estudio' : 'Choose the type: ',
        'seleccionar_informe':'Select the report:',
        'texto_bienvenida': 'Welcome to Greenmetrics',
        'tit_admin': 'Administrator profile',
        'tit_user': 'User profile.',
        'titulo_visit': 'Visitor profile',
        'tipo':'Programme type',
        'todos':'All',
        'usuario': 'User name.',
        'volver_atras': '← Go Back'
        },
    'es': {
        'aceptar': 'Aceptar',
        'actualizar_perfil': 'Actualizar perfil.',
        'ajustes': 'Ajustes',
        'anho':'año',
        'api_key': 'API key',
        'base_url': 'Base URL',
        'busquedas_anteriores':'Búsquedas anteriores',
        'cancelar': 'Cancelar',
        'cerrar_sesion': 'Cerrar sesión',
        'confirmar_contrasenha': 'Confirmar contraseña',
        'contenido': 'Contenido solo visible para visitantes.',
        'codigo_Asignatura':'Código asignatura',
        'criterio_1': 'La contraseña debe tener al menos una mayúscula, una minúscula y un número.',
        'criterio_2': 'Además de un minimo de 8 caracteres.',
        'criterio_3': '* Si no rellena el campo de la contraseña, esta no se actualizará.',
        'datos_IA': 'Datos de la IA',
        'descargar_datos_nuevos': 'Descargar datos nuevos',
        'descargar_informe':'Descargar informe',
        'ejecutando_grados': 'Descargando los enlaces a las direcciones de los grados y masteres.',
        'ejecutando_guias': 'Descargando las guías docentes.....',
        'ejecutando_asignaturas':'Se están procesando las asignaturas.... ',
        'en': 'Inglés',
        'error_script': 'Error al ejecutar el script:',
        'espanol': 'Español',
        'guardar':'Guardar cambios',
        'grande':'Grande',
        'introducir_anho': 'Introduzca el año del que desea extraer las métricas.(Ej. 2023-2024)',
        'introducir_datos_IA': 'Introduce los siguientes datos, sino se usará la IA predeterminada (Llama-8B-GGUF)',
        'IA_tit': 'IA',
        'ingles': 'Inglés',
        'iniciar_sesion': 'Iniciar sesión',
        'informe_1_19':'Informe 1_19',
        'informe_6_1':'Informe 6_1',
        'myModel': 'Modelo',
        'mensaje_cargando': 'Cargando... Esto puede tardar algunos minutos...',
        'modo_daltonismo': 'Modo Daltonismo',
        'modalidad':'modalidad',
        'nueva_contrasenha': 'Nueva contraseña. *',
        'nombre_archivo':'Nombre del archivo:',
        'normal': 'Medio',
        'no_busquedas':'No se encontraron búsquedas anteriores.',
        'opcion_ambos':'Ambos',
        'opcion_grado':'Grado',
        'opcion_master':'Master',
        'pequeno': 'Pequeño',
        'perfil': 'Perfil',
        'proceso_completado': 'Proceso completado exitosamente para el año',
        'progreso_titulo': 'Progreso del Proceso',
        'realizar_busqueda_nueva': 'Realizar una búsqueda',
        'sel_idioma': 'Seleccionar Idioma:',
        'sel_letra': 'Seleccionar Tamaño de Letra:',
        'seleccionar_tipo_estudio' : 'Selecciona el tipo de estudio',
        'seleccionar_informe':'Selecciona el informe a generar:',
        'texto_bienvenida': 'Bienvenido a Greenmetrics',
        'tit_admin': 'Perfil de administrador',
        'tit_user': 'Perfil de usuario',
        'titulo_visit': 'Perfil de Visitante',
        'tipo':'Tipo de programa',
        'todos':'Todos',
        'usuario': 'Nombre de usuario',
        'volver_atras': '← Volver atrás'
        }
    }


# ----------------------- BASES DE DATOS -----------------------------------------------------
# Modelo de Usuario
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    google_id = db.Column(db.String(50), unique=True, nullable=True)  # Campo opcional
    username = db.Column(db.String(50), nullable=False , unique=True)
    email = db.Column(db.String(100), nullable=False , unique=True)
    password = db.Column(db.String(200), nullable=False)
    rol = db.Column(db.String(50), nullable=False, default='visitante')  # Default es 'usuario'

# Modelo de Búsqueda
class Busqueda(db.Model):
    __bind_key__ = 'busqueda'
    id = db.Column(db.Integer, primary_key=True)
    anho = db.Column(db.String(20), nullable=False)
    codigo_asignatura = db.Column(db.String(100), nullable=True)
    tipo_programa = db.Column(db.String(100), nullable=True)
    nombre_archivo=db.Column(db.String(100), nullable=True)
    modalidad=db.Column(db.String(100), nullable=True)
    
    __table_args__ = (
        db.UniqueConstraint('anho','codigo_asignatura','modalidad', name='unique_modalidad_anho_codigo'),
    )


# ----------------------- FORMULARIOS -----------------------------------------------------
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
    

#  ----------------------- PÁGINAS PRINCIPALES ----------------------------------------------------
# Ruta principal
@app.route('/')
def index():
    return redirect(url_for('login'))

# Cerrar sesión
@app.route('/logout')
def logout():
    session.clear()
    flash("Has cerrado sesión.", "info")
    return redirect(url_for('login'))

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

# Ruta principal: Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    google_client_id = app.config["GOOGLE_OAUTH_CLIENT_ID"]

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
    
    return render_template('login.html',google_client_id=google_client_id)

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


#  ----------------------- PÁGINAS DE MODIFICACIÓN DE PARÁMETROS ----------------------------------------------------
# Ruta para cambiar los ajustes (idioma, tamaño de la letra y habilitar la opción de daltonismo)
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


#  ----------------------- CONFIGURACIÓN DE INICION SESIÓN CON GOOGLE ----------------------------------------------------
# Login con google
def get_google_user_info():
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
# Ruta para la página para pedir el año
@app.route('/pagina_pedir_anho')
def pagina_pedir_anho():
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

@app.route("/", methods=["GET", "POST"])
def procesar_anho():
    global estado_proceso
    if request.method == "POST":
        anho = request.form.get("anho")
        idioma = session.get('idioma', 'es')  # Obtener el idioma actual

        # Verificar el formato del año (####-####)
        if not anho_pattern(anho):
            flash("El año debe tener el formato 2022-2023", "error")
            return redirect(url_for('pagina_pedir_anho'))

       
        # Obtener los datos de tipo de estudio y grado/máster específico del formulario
        tipo_estudio = request.form.get("tipo_estudio", "ambos")

        # Validar si el tipo de estudio es correcto
        if tipo_estudio not in ["grado", "master", "ambos"]:
            flash("Opción de tipo de estudio no válida", "error")
            return redirect(url_for('pagina_pedir_anho'))

        with lock:
            estado_proceso["en_proceso"] = True
            estado_proceso["mensaje"] = textos[idioma]['mensaje_cargando']
            estado_proceso["porcentaje"] = 0
            estado_proceso["completado"] = False

        
        # Crear y lanzar un hilo para ejecutar ambos scripts con los parámetros
        hilo = threading.Thread(target=ejecutar_procesos, args=(anho, tipo_estudio, idioma))
        hilo.start()
        
        return redirect(url_for('pagina_pedir_IA'))

    return redirect(url_for('pagina_pedir_IA'))

def anho_pattern(anho):
    """ Verifica si el año tiene el formato correcto (####-####). """
    return bool(re.match(r"\d{4}-\d{4}", anho))

# Función que ejecuta los scripts en el orden correcto.
def ejecutar_procesos(anho, tipo_estudio="ambos", idioma='es'):
    """ Función que ejecuta los scripts en orden y actualiza el estado. """
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
# Ruta para la página donde se solicitan los datos de la IA
@app.route('/pagina_pedir_IA')
def pagina_pedir_IA():
    # Comprobar el idioma seleccionado en la sesión, por defecto 'en'
    idioma = session.get('idioma', 'es')
    tamano_texto = session.get('tamano_texto', 'normal')
    daltonismo = session.get('daltonismo', False)
    # Comprobar si el usuario está autenticado
    if 'user_id' not in session:
        return render_template('pagina_pedir_IA.html', 
                               rol='visitante', 
                               textos=textos[idioma], 
                               tamano_texto=tamano_texto,daltonismo=daltonismo)  # Contenido para visitantes
    else:
        rol = session['rol']
        return render_template('pagina_pedir_IA.html', 
                               rol=rol, 
                               textos=textos[idioma], 
                               tamano_texto=tamano_texto,daltonismo=daltonismo)  # Contenido según el rol

#Función donde se piden los paramétros para la configuración de la API.
@app.route('/actualizar_api', methods=['POST'])
def actualizar_api():
    try:
        # Ruta donde se encuentra el archivo API.py
        ruta_api = os.path.join(os.getcwd(), 'sostenibilidad', 'API.py')

        # Obtener los datos del formulario (si están disponibles)
        base_url = request.form['base_url'] or None
        api_key = request.form['api_key'] or None
        model = request.form['model'] or None
        
        # Leer el contenido actual de API.py
        with open(ruta_api, 'r') as file:
            contenido = file.read()
        
        # Obtener los valores actuales de las variables (si no se introducen nuevos valores)
        base_url_actual = re.search(r'base_url = "(.*?)"', contenido)
        api_key_actual = re.search(r'api_key = "(.*?)"', contenido)
        model_actual = re.search(r'myModel = "(.*?)"', contenido)
        
        # Si no se ha introducido un valor, se mantiene el valor actual del archivo
        if base_url is None:
            base_url = base_url_actual.group(1) if base_url_actual else ''
        if api_key is None:
            api_key = api_key_actual.group(1) if api_key_actual else ''
        if model is None:
            model = model_actual.group(1) if model_actual else ''
        
        # Actualizar las variables en el archivo, solo si se ha proporcionado un valor
        contenido_actualizado = re.sub(r'base_url = ".*?"', f'base_url = "{base_url}"', contenido)
        contenido_actualizado = re.sub(r'api_key = ".*?"', f'api_key = "{api_key}"', contenido_actualizado)
        contenido_actualizado = re.sub(r'myModel = ".*?"', f'myModel = "{model}"', contenido_actualizado)
        
        # Guardar los cambios en API.py
        with open(ruta_api, 'w') as file:
            file.write(contenido_actualizado)

        # Crear y lanzar un hilo para ejecutar la función
        hilo = threading.Thread(target=ejecutar_api)
        hilo.start()

        # Redirigir a la página de IA después de iniciar el proceso
        return redirect(url_for('pagina_informe_6_1'))
    
    except Exception as e:
        # En caso de error, devolver un mensaje
        return f"Error al actualizar la API: {str(e)}"

# Función que ejecutará el script en segundo plano
def ejecutar_api():
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
#  Ruta para la página donde se muestra la base de datos
@app.route('/consultar_busquedas', methods=['GET'])
def consultar_busquedas():
    idioma = session.get('idioma', 'es')  # Obtener el idioma actual
    tamano_texto = session.get('tamano_texto', 'normal')
    daltonismo = session.get('daltonismo', False)
    
    # Obtener los filtros seleccionados desde los parámetros de la URL
    anho_seleccionado = request.args.get('anho')  
    tipo_programa = request.args.get('tipo_programa')
    codigo_asignatura = request.args.get('codigo_asignatura')
    nombre_archivo = request.args.get('nombre_archivo')
    modalidad = request.args.get('modalidad')

    # Consultar los valores únicos para los filtros desde la base de datos secundaria
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
    
    # Construir la consulta con los filtros aplicados
    query = db.session.query(Busqueda).execution_options(bind_key='busqueda')

    if anho_seleccionado and anho_seleccionado != "Todos":
        query = query.filter(Busqueda.anho == anho_seleccionado)
    if tipo_programa and tipo_programa != "Todos":
        query = query.filter(Busqueda.tipo_programa == tipo_programa)
    if codigo_asignatura and codigo_asignatura != "Todos":
        query = query.filter(Busqueda.codigo_asignatura == codigo_asignatura)
    if nombre_archivo and nombre_archivo != "Todos":
        query = query.filter(Busqueda.nombre_archivo == nombre_archivo)
    if modalidad and modalidad != "Todos":
        query = query.filter(Busqueda.modalidad == modalidad)

    busquedas = query.all()

    # Pasar los datos al template
    return render_template(
        'consultar_busquedas.html',  
        textos=textos[idioma], tamano_texto=tamano_texto, daltonismo=daltonismo,
        busquedas=busquedas,
        anhos=anhos_disponibles,
        tipos_programa=tipos_programa,
        codigo_asignaturas=codigo_asignaturas,
        nombre_archivos=nombre_archivos,
        modalidad=modalidad_disponibles,
        selected_anho=anho_seleccionado,
        selected_tipo_programa=tipo_programa,
        selected_codigo_asignatura=codigo_asignatura,
        selected_nombre_archivo=nombre_archivo,
        selected_modalidad=modalidad  
    )


#  ----------------------- BARRA DE PROGRESO  ----------------------------------------------------
# Función para actualizar el estado del proceso
def actualizar_estado(mensaje, porcentaje, en_proceso=False, completado=False):
    """ Actualiza el estado del proceso con un mensaje, porcentaje de progreso y otros indicadores. """
    global estado_proceso
    with lock:
        estado_proceso["mensaje"] = mensaje
        estado_proceso["porcentaje"] = porcentaje
        estado_proceso["en_proceso"] = en_proceso
        estado_proceso["completado"] = completado


@app.route('/estado_proceso')
def estado_proceso_api():
    """ Devuelve el estado actual del proceso en formato JSON. """
    with lock:
        return jsonify(estado_proceso)

@app.route('/progreso')
def progreso():
    idioma = session.get('idioma', 'es')
    tamano_texto = session.get('tamano_texto', 'normal')
    daltonismo = session.get('daltonismo', False)
    
    return render_template('progreso.html', 
                           textos=textos[idioma], 
                           tamano_texto=tamano_texto, 
                           daltonismo=daltonismo)

#  ----------------------- GENERAR INFORMES ----------------------------------------------------
# Ruta para la página donde se realiza la descarga del informe
@app.route('/pagina_informe_1_19')
def pagina_informe_1_19():
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
        return render_template('pagina_informe_1_19.html', 
                               rol='visitante', 
                               textos=textos[idioma], 
                               tamano_texto=tamano_texto, 
                               daltonismo=daltonismo,
                               nuevos_anhos_disponibles=nuevos_anhos_disponibles)
    else:
        rol = session['rol']
        return render_template('pagina_informe_1_19.html', 
                               rol=rol, 
                               textos=textos[idioma], 
                               tamano_texto=tamano_texto, 
                               daltonismo=daltonismo,
                               nuevos_anhos_disponibles=nuevos_anhos_disponibles)
      
@app.route('/pagina_informe_6_1')
def pagina_informe_6_1():
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
   
   
         
@app.route('/selecciona_anho_informe')
def selecciona_anho_informe():
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


    return render_template('selecciona_anho_informe.html',  
                               textos=textos[idioma], 
                               tamano_texto=tamano_texto, 
                               daltonismo=daltonismo,
                               nuevos_anhos_disponibles=nuevos_anhos_disponibles)  
         
@app.route('/generar_informe', methods=['POST'])
def generar_informe():
    try:
        informe_seleccionado = determinar_tipo_informe()
        anho_seleccionado = ''
        if informe_seleccionado == "6_1":
            # Obtener el año seleccionado desde el formulario
            anho_seleccionado = request.form.get('anho')
            

            if not anho_seleccionado:
                return "Error: No se seleccionaron todos los campos", 400

        
        # Iniciar un hilo para ejecutar el informe con el año como argumento
        hilo = threading.Thread(target=ejecutar_informe, args=(anho_seleccionado,informe_seleccionado))
        hilo.start()

        # Redirigir a la página principal después de iniciar el proceso
        return redirect(url_for('pagina_principal'))

    except Exception as e:
        return f"Error al generar el informe: {str(e)}", 500

# Función que ejecutará el script en segundo plano con el año seleccionado
def ejecutar_informe(anho,informe):
    try:
        ruta_informe = os.path.join(os.getcwd(), 'generar_informe', 'general.py')
        if not os.path.exists(ruta_informe):
            raise FileNotFoundError(f"El archivo {ruta_informe} no existe.")
        # Ejecutar el script con el año seleccionado como argumento
        subprocess.run(['python3', ruta_informe, anho, informe], check=True)

        print(f"Proceso completado correctamente para el año {anho}.")
    except subprocess.CalledProcessError as e:
        print(f"Error ejecutando el script: {str(e)}")
    except Exception as e:
        print(f"Error en el hilo de ejecución: {str(e)}")
        
# Función que devuelve el informe a descargar en función de la URL
def determinar_tipo_informe():
    referrer = request.headers.get("Referer", "")
    if "pagina_informe_1_19" in referrer:
        return "1_19"
    if "selecciona_anho_informe" in referrer:
        return "6_1"

     
#  ----------------------- MAIN  ----------------------------------------------------
if __name__ == '__main__':
    # Crear las tablas de la base de datos
    with app.app_context():
        db.create_all()
    app.run(debug=True)