from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from .suno_client import Suno, SongGenerateParams, Song

app = FastAPI(
    title="Suno API Proxy",
    description="API proxy for Suno AI music generation",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Suno API is running", "docs": "/docs", "redoc": "/redoc"}

# Modelo para la solicitud de generación
class GenerateRequest(BaseModel):
    prompt: str
    custom: bool = False
    tags: str = ""
    negative_tags: str = ""
    instrumental: bool = False
    title: Optional[str] = None
    model: str = "chirp-v3-5-tau"
    cookie: str

@app.post("/generate", response_model=List[Song])
async def generate_song(request: GenerateRequest):
    try:
        client = Suno(cookie=request.cookie)
        songs = client.songs.generate(
            prompt=request.prompt,
            custom=request.custom,
            tags=request.tags,
            negative_tags=request.negative_tags,
            instrumental=request.instrumental,
            title=request.title,
            model=request.model
        )
        return songs
    except Exception as e:
        print(f"Error generating music: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/song/{song_id}")
async def get_song(song_id: str, cookie: str):
    try:
        client = Suno(cookie=cookie)
        song = client.get_song(song_id)
        return song
    except Exception as e:
        print(f"Error getting song: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/songs")
async def get_songs(cookie: str):
    try:
        client = Suno(cookie=cookie)
        songs = client.get_songs()
        return songs
    except Exception as e:
        print(f"Error getting songs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/download/{song_id}")
async def download_song(
    song_id: str,
    cookie: str,
    file_type: str = "audio"
):
    try:
        client = Suno(cookie=cookie)
        song = client.get_song(song_id)
        
        # Esperar a que el archivo esté listo
        song = client.songs.wait_for_file(song_id, file_type)
        
        # Retornar la URL del archivo según el tipo
        if file_type == "audio":
            return {"url": song.audio_url}
        elif file_type == "video":
            return {"url": song.video_url}
        elif file_type == "image":
            return {"url": song.cover_image_url}
        else:
            raise HTTPException(status_code=400, detail="Invalid file type")
            
    except Exception as e:
        print(f"Error downloading file: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 