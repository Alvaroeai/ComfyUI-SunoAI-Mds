from fastapi import FastAPI, HTTPException, Depends, Query, Path
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from .suno_client import Suno, SongGenerateParams, Song
import logging
from functools import lru_cache

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Suno API Proxy",
    description="API proxy for Suno AI music generation",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Response Models
class ErrorResponse(BaseModel):
    detail: str
    status_code: int
    
class SongResponse(BaseModel):
    id: str
    status: str
    audio_url: Optional[str] = None
    video_url: Optional[str] = None
    cover_image_url: Optional[str] = None
    
class GenerateRequest(BaseModel):
    prompt: str
    custom: bool = False
    tags: str = ""
    negative_tags: str = ""
    instrumental: bool = False
    title: Optional[str] = None
    model: str = "chirp-v3-5-tau"
    cookie: str

# Client management
@lru_cache()
def get_suno_client(cookie: str) -> Suno:
    return Suno(cookie=cookie)

# Exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Global error: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal error occurred", "status_code": 500}
    )

@app.get("/")
async def root():
    return {"message": "Suno API is running", "docs": "/docs", "redoc": "/redoc"}

@app.post("/generate", response_model=List[SongResponse])
async def generate_song(request: GenerateRequest):
    try:
        client = get_suno_client(request.cookie)
        songs = client.songs.generate(
            prompt=request.prompt,
            custom=request.custom,
            tags=request.tags,
            negative_tags=request.negative_tags,
            instrumental=request.instrumental,
            title=request.title,
            model=request.model
        )
        return [SongResponse(**song.dict()) for song in songs]
    except Exception as e:
        logger.error(f"Error generating music: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"message": "Failed to generate song", "error": str(e)}
        )

@app.get("/song/{song_id}", response_model=SongResponse)
async def get_song(
    song_id: str = Path(..., description="The ID of the song to retrieve"),
    cookie: str = Query(..., description="Authentication cookie")
):
    try:
        client = get_suno_client(cookie)
        song = client.get_song(song_id)
        return SongResponse(**song.dict())
    except Exception as e:
        logger.error(f"Error getting song {song_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=404 if "not found" in str(e).lower() else 500,
            detail={"message": f"Failed to get song {song_id}", "error": str(e)}
        )

@app.get("/songs", response_model=List[SongResponse])
async def get_songs(
    cookie: str = Query(..., description="Authentication cookie")
):
    try:
        client = get_suno_client(cookie)
        songs = client.get_songs()
        return [SongResponse(**song.dict()) for song in songs]
    except Exception as e:
        logger.error(f"Error getting songs: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"message": "Failed to get songs", "error": str(e)}
        )

@app.get("/download/{song_id}")
async def download_song(
    song_id: str = Path(..., description="The ID of the song to download"),
    cookie: str = Query(..., description="Authentication cookie"),
    file_type: str = Query("audio", description="Type of file to download: audio, video, or image")
):
    try:
        client = get_suno_client(cookie)
        
        # First get the song to verify it exists
        song = client.get_song(song_id)
        if not song:
            raise HTTPException(status_code=404, detail=f"Song {song_id} not found")
            
        # Wait for the file to be ready
        song = client.songs.wait_for_file(song_id, file_type)
        
        # Return the appropriate URL based on file type
        urls = {
            "audio": song.audio_url,
            "video": song.video_url,
            "image": song.cover_image_url
        }
        
        if file_type not in urls:
            raise HTTPException(status_code=400, detail="Invalid file type")
            
        url = urls[file_type]
        if not url:
            raise HTTPException(
                status_code=404,
                detail=f"{file_type} file not available for song {song_id}"
            )
            
        return {"url": url}
            
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error downloading {file_type} for song {song_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"message": f"Failed to download {file_type}", "error": str(e)}
        )