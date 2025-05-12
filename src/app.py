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
# Configuración de la base de datos PostgreSQL
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
# Modelo de Usuario
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    google_id = db.Column(db.String(50), unique=True, nullable=True)  # Campo opcional
    username = db.Column(db.String(50), nullable=False , unique=True)
    email = db.Column(db.String(100), nullable=True, unique=True)
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
    sostenibilidad = db.Column(db.String(10), nullable=True)

    
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
    idioma = session.get('idioma', 'es')
    session.clear()
    flash(textos[idioma]['flash_cerrado_sesion'], "info")
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
    idioma = session.get('idioma', 'es')
    return render_template('login.html',google_client_id=google_client_id,textos=textos[idioma])




@app.route('/cambiar_idioma', methods=['POST'])
def cambiar_idioma():
    data = request.get_json()
    idioma = data.get('idioma', 'es')  # Obtener idioma enviado por el cliente
    session['idioma'] = idioma  # Guardar el idioma en la sesión
    return '', 200  # Respuesta exitosa



# Ruta para el registro de nuevos usuarios
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
            idioma = request.form.get('idioma', 'es')
            session['idioma'] = idioma
            # Obtener datos del formulario
            username = request.form['username'] 
            email = request.form['email']  
            password = request.form['password']
            confirm_password = request.form['confirm_password']

            # Validar contraseña
            error = validar_contrasena(password)
            if error:
                flash(error, 'error')
                return render_template('register.html', textos=textos[idioma])  # Detener el proceso si hay errores
            
            # Validar datos
            if not username or not email or not password:
                flash(mensajes_flash[idioma]['campos_incompletos'], 'error')
            elif password != confirm_password:
                flash(mensajes_flash[idioma]['contrasenas_no_coinciden'], 'error')
            else:
                # Verificar si el nombre de usuario o el correo electrónico ya están en uso
                existing_user_by_username = User.query.filter_by(username=username).first()
                existing_user_by_email = User.query.filter_by(email=email).first()

                if existing_user_by_username:
                    flash(mensajes_flash[idioma]['usuario_existente'], 'error')
                elif existing_user_by_email:
                    flash(mensajes_flash[idioma]['email_existente'], 'error')
                else:
                    try:
                        # Hash de la contraseña con pbkdf2:sha256
                        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
                        new_user = User(username=username, email=email, password=hashed_password, rol ='usuario')  
                        db.session.add(new_user)
                        db.session.commit()
                        flash(mensajes_flash['cuenta_creada'], 'success')
                    except Exception as e:
                        db.session.rollback()
                        flash(f"{mensajes_flash[idioma]['error_guardar']}{str(e)}", 'error')
    idioma = session.get('idioma', 'es')
    return render_template('register.html',textos=textos[idioma] )


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
                flash(mensajes_flash[idioma]['perfil_actualizado'], 'success')
                return redirect(url_for('pagina_principal'))
            except Exception as e:
                db.session.rollback()
                flash(f"{mensajes_flash[idioma]['error_actualizar']}{str(e)}", "error")
        else:
            flash(mensajes_flash[idioma]['errores_formulario'], "error")

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



def verificar_si_existen_datos(anho, tipo_estudio):
    from sqlalchemy import or_
    count = Busqueda.query.filter_by(anho=anho, tipo_programa=tipo_estudio).count()
    return count > 0



@app.route('/verificar_datos', methods=['POST'])
def verificar_datos():
    anho = request.form.get('anho')
    tipo_estudio = request.form.get('tipo_estudio')

    datos_existentes = verificar_si_existen_datos(anho, tipo_estudio)
    return jsonify({'datos_existentes': datos_existentes})


@app.route("/", methods=["GET", "POST"])
def procesar_anho():
    global estado_proceso
    if request.method == "POST":
        anho = request.form.get("anho")
        idioma = session.get('idioma', 'es')  # Obtener el idioma actual

        # Verificar el formato del año (####-####)
        if not anho_pattern(anho):
            flash(textos[idioma]['formato_anho_invalido'], "error")
            return redirect(url_for('pagina_pedir_anho'))

       
        # Obtener los datos de tipo de estudio y grado/máster específico del formulario
        tipo_estudio = request.form.get("tipo_estudio", "ambos")

        # Validar si el tipo de estudio es correcto
        if tipo_estudio not in ["grado", "master", "ambos"]:
            flash(textos[idioma]['tipo_estudio_invalido'], "error")
            return redirect(url_for('pagina_pedir_anho'))
        if verificar_si_existen_datos(anho, tipo_estudio):
            flash(textos[idioma]['datos_ya_existen'], "info")
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
@app.route('/pagina_pedir_IA', methods=['GET','POST'])
def pagina_pedir_IA():
    origen = session.get('origen', '')  # Obtiene el valor de sesión
    anho_seleccionado = request.form.get('anho')
    session['anho'] = anho_seleccionado

    # Comprobar el idioma seleccionado en la sesión, por defecto 'en'
    idioma = session.get('idioma', 'es')
    tamano_texto = session.get('tamano_texto', 'normal')
    daltonismo = session.get('daltonismo', False)
    # Comprobar si el usuario está autenticado
    if 'user_id' not in session:
        return render_template('pagina_pedir_IA.html', origen=origen,
                               rol='visitante', 
                               textos=textos[idioma], 
                               tamano_texto=tamano_texto,daltonismo=daltonismo,anho_seleccionado=session.get('anho'))  # Contenido para visitantes
    else:
        rol = session['rol']
        return render_template('pagina_pedir_IA.html', origen=origen,
                               rol=rol, 
                               textos=textos[idioma], 
                               tamano_texto=tamano_texto,daltonismo=daltonismo,anho_seleccionado=session.get('anho'))  # Contenido según el rol
    


#Función donde se piden los paramétros para la configuración de la API.
@app.route('/actualizar_api', methods=['GET','POST'])
def actualizar_api():
    try:
        informe_seleccionado = determinar_tipo_informe()

        # Obtener la configuración actual
        config_actual = cargar_configuracion()
        # origen = session.get('origen', '')

        # Obtener los datos del formulario y usar los valores actuales si están vacíos
        base_url = request.form.get('base_url').strip() or config_actual["base_url"]
        api_key = request.form.get('api_key').strip() or config_actual["api_key"]
        model = request.form.get('model').strip() or config_actual["model"]

        # Guardar la nueva configuración en config.json
        guardar_configuracion({
            "base_url": base_url,
            "api_key": api_key,
            "model": model
        })

        if informe_seleccionado == "6_1":
            # Reiniciar la API si es necesario
            hilo = threading.Thread(target=ejecutar_api)
            hilo.start()
            return redirect(url_for('pagina_principal'))

        else:
            # Para el 1_19 y el 6_8 es necesario seleccionar la API
            try:
                anho_seleccionado = ''
                excel =''
                if informe_seleccionado == "6_8":
                    # Obtener el año seleccionado desde el formulario
                    anho_seleccionado = session.get('anho')
                    if not anho_seleccionado:
                        return "Error: No se seleccionaron todos los campos", 400
                elif informe_seleccionado == "6_4":
                    excel =  session.get('ruta_excel')
                    if not excel:
                        return "Error: No se ha subido ningún fichero.", 400
                # Iniciar un hilo para ejecutar el informe con el año como argumento
                hilo = threading.Thread(target=ejecutar_informe, args=(anho_seleccionado,informe_seleccionado, excel))
                hilo.start()

                # Redirigir a la página principal después de iniciar el proceso
                return redirect(url_for('pagina_principal'))

            except Exception as e:
                return f"Error al generar el informe: {str(e)}", 500
    
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
from flask import request, session, render_template, jsonify

@app.route('/consultar_busquedas', methods=['GET'])
def consultar_busquedas():
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
# Editar búsqueda (solo admin)
@app.route('/editar_busqueda/<int:id>', methods=['GET', 'POST'])
def editar_busqueda(id):
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
        flash("Búsqueda editada correctamente.", "succes")

        return redirect(url_for('consultar_busquedas'))

    return render_template('editar_busqueda.html', busqueda=busqueda, textos=textos[idioma],
        tamano_texto=tamano_texto,
        daltonismo=daltonismo)
    
# Eliminar búsqueda (solo admin)
@app.route('/eliminar_busqueda/<int:id>', methods=['POST'])
def eliminar_busqueda(id):
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
# No es necesario seleccionar la API para generar el informe
@app.route('/generar_informe', methods=['POST'])
def generar_informe():
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

# Función que ejecutará el script en segundo plano con el año seleccionado
def ejecutar_informe(anho,informe,excel):
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
        
# Función que devuelve el informe a descargar en función de la URL
def determinar_tipo_informe():
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

# Función para verificar si el archivo tiene una extensión permitida
def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'xlsx', 'xls'}  # Extensiones permitidas
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS



@app.route('/subir_excel', methods=['POST'])
def subir_excel():
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
    # Limpiar la clave de la ruta del archivo en la sesión
    session.pop('ruta_excel', None)  # Eliminar 'ruta_excel' de la sesión si existe
    return redirect(url_for('pagina_informe_6_4'))  # Redirigir a la página de informe 6_4


#  ----------------------- INFORME 6_7 -------------------------------------- 
# Ruta para la página donde se realiza la descarga del informe
@app.route('/pagina_informe_6_7')
def pagina_informe_6_7():
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
    admin_username = "admin"
    admin_password = os.getenv("ADMIN_PASSWORD")

    # Verifica si ya existe
    admin = User.query.filter_by(username=admin_username).first()
    if not admin:
        nuevo_admin = User(
            username=admin_username,
            password=generate_password_hash(admin_password),
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