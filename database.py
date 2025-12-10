from pymongo import MongoClient
from dotenv import load_dotenv
import os

# Cargar las variables del archivo .env
load_dotenv()

# Obtener la URI
MONGO_URI = os.getenv("MONGODB_URI")

# Crear el cliente de conexión
client = MongoClient(MONGO_URI)

# Seleccionar la base de datos (se creará automáticamente si no existe)
db = client["mimapa_db"]

# Definir las colecciones que usaremos
users_collection = db["users"]

# Función para probar la conexión
def check_db_connection():
    try:
        client.admin.command('ping')
        print("✅ Conexión a MongoDB exitosa")
    except Exception as e:
        print(f"❌ Error conectando a MongoDB: {e}")