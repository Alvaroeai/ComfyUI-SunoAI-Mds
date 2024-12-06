import os
import json
import pathlib
import random
import re
import time
from typing import List, Optional, Union
import threading
from dotenv import load_dotenv
from curl_cffi import requests
from pydantic import BaseModel, ConfigDict
from rich import print
import traceback

# ===================== CONFIGURACIÓN ===================== #

# Cargar variables de entorno
load_dotenv()
COOKIE = os.getenv("SUNO_COOKIE", "")

# Configuración de constantes
CLIENT_JS_VERSION = "5.35.1"
CLERK_API_VERSION = "2021-02-05"
BASE_URL = "https://studio-api.prod.suno.com/api"
CLERK_URL = "https://clerk.suno.com/v1"
AUDIO_CDN_URL = "https://cdn1.suno.ai"

# URLs utilizadas
URL_SID = f"{CLERK_URL}/client?__clerk_api_version={CLERK_API_VERSION}&_clerk_js_version={CLIENT_JS_VERSION}"
URL_JWT = f"{CLERK_URL}/client/sessions/{{sid}}/tokens?__clerk_api_version={CLERK_API_VERSION}&_clerk_js_version={CLIENT_JS_VERSION}"
URL_TOUCH = f"{CLERK_URL}/client/sessions/{{sid}}/touch?__clerk_api_version={CLERK_API_VERSION}&_clerk_js_version={CLIENT_JS_VERSION}"
URL_FEED = f"{BASE_URL}/feed"
URL_GENERATE = f"{BASE_URL}/generate/v2/"
URL_SESSION = f"{BASE_URL}/session"
URL_CREDITS = f"{BASE_URL}/billing/info"
URL_EXTEND = f"{BASE_URL}/user/extend_session_id/"

# Available models with their descriptions
AVAILABLE_MODELS = {
    "chirp-v4": "Last generation model",
    "chirp-v3-5": "Default high-quality model",
    "chirp-v3-0": "Previous generation model",
    "chirp-v2-5": "Earlier generation model",
    # Add more models as they become available
}

class SunoConfig:
    # Available models with their descriptions
    AVAILABLE_MODELS = {
        "chirp-v4": "Last generation model",
        "chirp-v3-5": "Default high-quality model",
        "chirp-v3-0": "Previous generation model",
        "chirp-v2-5": "Earlier generation model",
        # Add more models as they become available
    }

# ===================== MODELOS ===================== #

class Song(BaseModel):
    """Modelo para representar canciones generadas por Suno."""
    model_config = ConfigDict(protected_namespaces=())
    id: str
    video_url: str
    audio_url: str
    image_url: Optional[str] = None
    image_large_url: Optional[str] = None
    cover_image_url: Optional[str] = None
    major_model_version: str
    model_name: str
    metadata: dict
    is_liked: bool
    user_id: str
    is_trashed: bool
    reaction: Optional[dict] = None
    created_at: str
    status: str
    title: str
    play_count: int
    upvote_count: int
    is_public: bool


class SongGenerateParams(BaseModel):
    """Parámetros para generar canciones."""
    model_config = ConfigDict(protected_namespaces=())
    prompt: str
    custom: bool = False
    tags: str = ""
    instrumental: bool = False


# ===================== CLIENTE BASE ===================== #

class Client:
    """Cliente base para gestionar solicitudes HTTP."""
    headers = {
        "Accept": "*/*",
        "Dnt": "1",
        "Priority": "u=1, i",
        "Referer": "https://suno.com/",
        "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"macOS"',
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    }

    def __init__(self, cookie: str) -> None:
        self.headers["cookie"] = cookie
        self._session = requests.Session(headers=self.headers)
        self._sid = None

    def request(self, *args, **kwargs) -> requests.Response:
        kwargs["impersonate"] = kwargs.get("impersonate", "chrome")
        return self._session.request(*args, **kwargs)

    def sleep(self, seconds: Optional[float] = None) -> None:
        time.sleep(seconds or random.randint(1, 6))


# ===================== CLIENTE SUNO ===================== #

class Suno(Client):
    """Cliente especializado para interactuar con la API de Suno."""
    def __init__(self, cookie: Optional[str] = None) -> None:
        cookie = cookie or COOKIE
        if not cookie:
            raise Exception("environment variable SUNO_COOKIE is not set")
        super().__init__(cookie)
        self._sid = self._get_sid()
        print(f"SID: {self._sid}")
        self.songs = Songs(self)

    def _get_sid(self) -> str:
        response = self.request("GET", URL_SID)
        response.raise_for_status()
        return response.json()["response"]["last_active_session_id"]

    def _get_jwt(self) -> str:
        url = URL_JWT.format(sid=self._sid)
        self.request("POST", URL_JWT.format(sid=self._sid))
        response = self.request("POST", url)
        response.raise_for_status()
        jwt = response.json().get("jwt")
        #print(f"jwt: {jwt}")
        return jwt
    
    def _renew(self) -> None:
        jwt = self._get_jwt()
        self._session.headers["Authorization"] = f"Bearer {jwt}"

    def _extend_session(self) -> None:
        """Extiende la sesión utilizando el SID actual."""
        sid = self._get_sid()  # Obtener el SID actual
        try:
            # Realizar la solicitud POST para extender la sesión
            
            response = self.songs.request("POST", URL_EXTEND, json={"session_id": sid})
            response.raise_for_status()  # Lanza una excepción si la respuesta es un error HTTP

            # Verificamos si la respuesta indica que la sesión fue extendida correctamente
            data = response.json()
            if data.get("is_extended", False):
                print("Session extended successfully.")
                # Actualizamos el SID local con el nuevo session_id
                self._set_sid(data["session_id"])  # Asegúrate de que esta función actualice correctamente el session_id
            else:
                print("Failed to extend session. Response: ", data)

        except requests.RequestException as e:
            print(f"Error extending session: {e}")
            # Aquí podrías agregar un mecanismo para reintentar o notificar al usuario

    def request(self, *args, **kwargs) -> requests.Response:
        max_retries = 3  # Número máximo de intentos para renovar la sesión
        retries = 0
        response = super().request(*args, **kwargs)
        
        while response.status_code == 401 and retries < max_retries:  # Si la sesión ha caducado (401)
            print("Session expired (401), attempting to renew the JWT...")
            self._renew()  # Intenta renovar el JWT
            response = super().request(*args, **kwargs)  # Vuelve a intentar la solicitud
            retries += 1

        if response.status_code == 422:  # Si la sesión ha caducado (422)
            print("Error: hCaptcha expired. Please return to the Suno website, generate a new song, and try again.")
            raise Exception("hCaptcha expired. Action required.")  # Lanza una excepción para manejarlo
        
        # if response.status_code == 422 and retries < max_retries:  # Si la sesión ha caducado (422)
        #     print("Session expired (422), attempting to extend the session...")
        #     self._extend_session()  # Intenta extender la sesión
        #     response = super().request(*args, **kwargs)  # Vuelve a intentar la solicitud
        #     retries += 1
        
        if retries >= max_retries:
            print("Maximum retry limit reached. Please check session renewal logic.")
        
        return response
    
    def get_song(self, id: str) -> Song:
        url = f"{URL_FEED}/?ids={id}"
        print(f"Fetching song with ID: {id} from URL: {url}")  # Log simple
        response = self.request("GET", url)
        if not response.ok:
            raise Exception(f"Failed to get song: {response.status_code}: {response.text}")
        data = response.json()
        song = data[0]
        song["cover_image_url"] = song.get("image_large_url")
        print(f"Song fetched successfully: {song['title']} with ID: {song['id']} data: {song}")  # Log de éxito
        return Song(**song)

    
    def get_songs(self) -> List[Song]:
        response = self.request("GET", URL_FEED)
        if not response.ok:
            raise Exception(f"failed to get songs: {response.status_code}: {response.text}")
        data = response.json()
        for song in data:
            song["cover_image_url"] = song.get("image_large_url")
        return [Song(**song) for song in data]

# ===================== API SONGS ===================== #

class APIResource:
    """Clase base para recursos de la API."""
    def __init__(self, client: Client) -> None:
        self._client = client

    def request(self, *args, **kwargs) -> requests.Response:
        return self._client.request(*args, **kwargs)

    def sleep(self, seconds: Optional[float] = None) -> None:
        self._client.sleep(seconds)


class Songs(APIResource):
    """Gestión de canciones en Suno."""
    
    def generate(
        self,
        prompt: str,
        custom: bool = False,
        tags: Optional[str] = "",
        negative_tags: Optional[str] = "",
        instrumental: bool = False,
        title: Optional[str] = None,
        model: str = "chirp-v3-5-tau",
    ) -> List[Song]:
        url = URL_GENERATE
        payload = {
            "mv": model,
            "title": "" if not custom else title,
            "prompt": "" if not custom else prompt,
            "gpt_description_prompt": prompt if not custom else "",
            "tags": tags,
            "negative_tags": negative_tags,
            "make_instrumental": instrumental,
            "token": f"P1_{self._client._get_jwt()}",
        }
        
        # Debugging: Imprimir los parámetros antes de la solicitud
        print(f"Debug: Payload before sending request:")
        #print(f"Prompt: {prompt}, Custom: {custom}, Tags: {tags}, Negative Tags: {negative_tags}, Title: {title}")
        print(f"Payload: {payload}")
        
        try:
            # Enviar solicitud
            response = self.request("POST", url, json=payload)
            
            # Verificar si la respuesta fue exitosa
            response.raise_for_status()
            
            # Debugging: Imprimir respuesta del servidor
            print(f"Debug: Response status code: {response.status_code}")
            print(f"Response content: {response.json()}")
            
            # Procesar la respuesta
            return [Song(**clip) for clip in response.json().get("clips", [])]
        
        except Exception as e:
            # Imprimir más detalles en caso de error
            print(f"Error occurred during song generation: {e}")
            print("Detailed traceback:")
            traceback.print_exc()  # Imprime el stack trace para mayor detalle
            return []  # Retornar una lista vacía o lo que sea adecuado en caso de error
    
    # Método genérico para esperar archivos
    def wait_for_file(self, audio_id: str, file_type: str, max_wait_time: int = 300, check_interval: int = 5):
        """
        Espera a que un archivo específico (audio, video o imagen) esté listo en Suno.

        :param audio_id: ID del archivo a verificar.
        :param file_type: Tipo de archivo a esperar ("audio", "video", "image").
        :param max_wait_time: Tiempo máximo de espera en segundos.
        :param check_interval: Intervalo entre verificaciones en segundos.
        :return: Objeto canción con el recurso disponible.
        :raises TimeoutError: Si el recurso no está disponible después del tiempo de espera.
        """
        elapsed_time = 0
        while elapsed_time < max_wait_time:
            # Obtener la canción desde el cliente
            song = self._client.get_song(audio_id)
            
            # Comprobar si el recurso está disponible según el tipo de archivo
            if file_type == "audio" and song.audio_url:
                return song
            elif file_type == "video" and song.video_url:
                return song
            elif file_type == "image" and song.cover_image_url:
                return song
            
            # Esperar antes de la próxima verificación
            time.sleep(check_interval)
            elapsed_time += check_interval
        
        # Si no se encuentra el recurso, se lanza una excepción
        raise TimeoutError(f"{file_type.capitalize()} for audio_id {audio_id} not ready after {max_wait_time} seconds.")

# ===================== FUNCIONES AUXILIARES ===================== #

def _get_id(song: Union[str, Song]) -> str:
    """Extraer el ID de una canción."""
    if isinstance(song, Song):
        return song.id
    match = re.search(r"[a-fA-F0-9\-]{36}", song)
    if match:
        return match.group(0)
    raise ValueError("Invalid song ID or format")

class Downloader:
    MAX_RETRIES = 10  # Número máximo de reintentos
    RETRY_DELAY = 10  # Tiempo de espera entre reintentos en segundos

    @staticmethod
    def download(song: Union[str, Song], file_type: str, root: str = ".", name: Optional[str] = None) -> str:
        """
        Args:
            song: ID de la canción o instancia de Song.
            file_type: Tipo de archivo a descargar ("audio", "video", "image").
            root: Directorio raíz donde guardar el archivo.
            name: Nombre del archivo. Si no se proporciona, se genera automáticamente.

        Returns:
            La ruta al archivo descargado.
        """
        song_id = _get_id(song)
        base_url_mapping = {
            "audio": f"{AUDIO_CDN_URL}/{song_id}.mp3",
            "video": f"{AUDIO_CDN_URL}/{song_id}.mp4",
            "image": f"{AUDIO_CDN_URL}/image_large_{song_id}.jpeg",
        }
        file_url = base_url_mapping.get(file_type)
        if not file_url:
            raise ValueError(f"Invalid file type or no URL available for {file_type}.")

        retries = 0
        while retries < Downloader.MAX_RETRIES:
            try:
                # Intentar obtener el archivo
                response = requests.get(file_url, timeout=10)
                response.raise_for_status()  # Levanta un error si la respuesta no es exitosa

                # Generar el nombre del archivo si no se proporciona
                extension = file_url.split('.')[-1]
                file_name = name or f"{file_type}_{song_id}.{extension}"
                file_path = pathlib.Path(root) / file_name

                # Guardar el archivo
                with open(file_path, "wb") as file:
                    file.write(response.content)

                print(f"Downloaded {file_type}: {file_path}")
                return str(file_path)

            except requests.exceptions.RequestException as e:
                print(f"Error downloading {file_type}: {e}. Retrying {retries + 1}/{Downloader.MAX_RETRIES}...")
                retries += 1
                time.sleep(Downloader.RETRY_DELAY)

        raise Exception(f"Failed to download {file_type} after {Downloader.MAX_RETRIES} attempts.")