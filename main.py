from fastapi import FastAPI, Request, Form, File, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import RedirectResponse
from dotenv import load_dotenv
import os
import httpx
from datetime import datetime
import cloudinary
import cloudinary.uploader

# Importaciones propias
from database import check_db_connection, users_collection
from auth import router as auth_router 

load_dotenv()

# --- CONFIGURACIÓN CLOUDINARY ---
cloudinary.config( 
  cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME"), 
  api_key = os.getenv("CLOUDINARY_API_KEY"), 
  api_secret = os.getenv("CLOUDINARY_API_SECRET"),
  secure = True
)

app = FastAPI()

app.add_middleware(SessionMiddleware, secret_key=os.getenv("SECRET_KEY"))

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

app.include_router(auth_router)

@app.on_event("startup")
def startup_event():
    check_db_connection()

# --- RUTA PRINCIPAL (MODIFICADA) ---
@app.get("/")
async def home(request: Request):
    user_session = request.session.get('user')
    
    # Datos por defecto
    context = {
        "request": request, 
        "user": None, 
        "is_owner": True, # Bandera para saber si puedo editar
        "visits_received": []
    }

    if user_session:
        # Busco mis datos actualizados
        my_data = users_collection.find_one({"email": user_session['email']})
        context["user"] = my_data
        # Paso las visitas recibidas (ordenadas de reciente a antigua si quieres)
        if my_data and "visits" in my_data:
             context["visits_received"] = my_data["visits"][::-1] # Invertir lista
    
    return templates.TemplateResponse("index.html", context)


# --- RUTA AÑADIR MARCADOR (MODIFICADA CON IMAGEN) ---
@app.post("/add-marker")
async def add_marker(
    request: Request, 
    city: str = Form(...), 
    country: str = Form(...),
    image: UploadFile = File(None) # Nuevo parámetro opcional
):
    user_session = request.session.get('user')
    if not user_session:
        return RedirectResponse(url="/")

    # 1. Subir imagen a Cloudinary (si existe)
    image_url = ""
    if image and image.filename:
        try:
            # Subida asíncrona a Cloudinary
            upload_result = cloudinary.uploader.upload(image.file)
            image_url = upload_result.get("secure_url")
        except Exception as e:
            print(f"Error subiendo imagen: {e}")

    # 2. Geocoding
    lat, lon = None, None
    async with httpx.AsyncClient() as client:
        headers = {'User-Agent': 'MiMapaApp/1.0'}
        try:
            resp = await client.get(
                f"https://nominatim.openstreetmap.org/search?city={city}&country={country}&format=json",
                headers=headers
            )
            data = resp.json()
            if data:
                lat, lon = data[0]['lat'], data[0]['lon']
        except Exception as e:
            print(f"Error geocoding: {e}")

    if lat and lon:
        new_marker = {
            "city": city,
            "country": country,
            "lat": lat,
            "lon": lon,
            "image_url": image_url # Guardamos la URL
        }
        users_collection.update_one(
            {"email": user_session['email']},
            {"$push": {"markers": new_marker}}
        )

    return RedirectResponse(url="/", status_code=303)


# --- NUEVA RUTA: VISITAR A OTRO USUARIO ---
@app.post("/visit")
async def visit_user(request: Request, target_email: str = Form(...)):
    current_user = request.session.get('user')
    
    # 1. Buscar al usuario objetivo
    target_user = users_collection.find_one({"email": target_email})
    
    if not target_user:
        # Si no existe, volvemos a casa (podrías mostrar error, pero simplificamos)
        return RedirectResponse(url="/", status_code=303)

    # 2. Registrar la visita (si estoy logueado y no soy yo mismo)
    if current_user and current_user['email'] != target_email:
        visit_record = {
            "visitor_email": current_user['email'],
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            # Simulamos el token OAuth (en real sería el access_token)
            "oauth_token": "google_oauth_token_hidden" 
        }
        users_collection.update_one(
            {"email": target_email},
            {"$push": {"visits": visit_record}}
        )

    # 3. Renderizar el mapa del OTRO usuario
    # Marcamos is_owner = False para ocultar botones de editar
    return templates.TemplateResponse("index.html", {
        "request": request, 
        "user": target_user, 
        "is_owner": False,
        "visitor_mode": True # Para mostrar un aviso visual
    })