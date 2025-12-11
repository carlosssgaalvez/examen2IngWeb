import os
from fastapi import APIRouter, Request
from starlette.responses import RedirectResponse
from authlib.integrations.starlette_client import OAuth
from database import users_collection  # Importamos tu colección de usuarios
from datetime import datetime

# Creamos un "router" para agrupar las rutas de autenticación
router = APIRouter()

# Configuración de OAuth con Authlib
oauth = OAuth()

oauth.register(
    name='google',
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile' # Pedimos permiso para ver email y perfil
    }
)

# 1. Ruta de Login: Manda al usuario a Google
@router.get("/login")
async def login(request: Request):
    # Generamos la URL absoluta para el callback
    redirect_uri = request.url_for('auth')
    
    # --- PARCHE HTTPS PARA VERCEL ---
    # Si la URL generada es http pero estamos en vercel, la forzamos a https
    if "vercel.app" in str(redirect_uri):
        redirect_uri = str(redirect_uri).replace("http://", "https://")
    # --------------------------------
    
    return await oauth.google.authorize_redirect(request, redirect_uri)

# 2. Ruta de Auth (Callback): Google devuelve al usuario aquí
@router.get("/auth")
async def auth(request: Request):
    try:
        # Obtener el token de acceso
        token = await oauth.google.authorize_access_token(request)
        # Obtener los datos del usuario (userinfo) dentro del token
        user_info = token.get('userinfo')
        
        if user_info:
            # --- LÓGICA DE BASE DE DATOS ---
            # Buscamos si el usuario ya existe en MongoDB por su email
            existing_user = users_collection.find_one({"email": user_info['email']})
            
            if not existing_user:
                # Si es la primera vez, lo guardamos en la BD
                new_user = {
                    "email": user_info['email'],
                    "name": user_info.get('name'),
                    "picture": user_info.get('picture'),
                    "created_at": datetime.now(),
                    "markers": [], # Lista vacía para futuros marcadores
                    "visits": []   # Lista vacía para futuras visitas
                }
                users_collection.insert_one(new_user)
                print(f"🆕 Nuevo usuario registrado: {user_info['email']}")
            else:
                print(f"👋 Usuario recurrente: {user_info['email']}")

            # Guardamos al usuario en la "sesión" (cookie segura)
            request.session['user'] = dict(user_info)
        
        return RedirectResponse(url='/')
    except Exception as e:
        print(f"Error en autenticación: {e}")
        return RedirectResponse(url='/')

# 3. Ruta de Logout: Cierra la sesión
@router.get("/logout")
async def logout(request: Request):
    request.session.pop('user', None) # Borra al usuario de la sesión
    return RedirectResponse(url='/')