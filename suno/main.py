import uvicorn
import os
import sys
from pathlib import Path

# Obtener el directorio raíz del proyecto
ROOT_DIR = Path(__file__).parent.parent
sys.path.append(str(ROOT_DIR))

if __name__ == "__main__":
    # Asegurarse de que estamos en el directorio correcto
    os.chdir(ROOT_DIR)
    print(f"Starting server from {os.getcwd()}")
    print("API docs will be available at:")
    print("  - Swagger UI: http://localhost:8000/docs")
    print("  - ReDoc: http://localhost:8000/redoc")
    
    uvicorn.run(
        "suno.api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=[str(ROOT_DIR)]
    ) 