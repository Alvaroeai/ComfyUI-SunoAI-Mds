import os
import json
import pathlib
import random
import re
import time
from typing import List, Optional, Union, Dict, Any
from curl_cffi import requests
from curl_cffi.requests import Response
from pydantic import BaseModel, ConfigDict

import asyncio
#from pyppeteer import launch
from typing import Optional

# ===================== CONFIGURACIÓN ===================== #
COOKIE = os.getenv("SUNO_COOKIE", "")
CLIENT_JS_VERSION = "5.43.6"
CLERK_API_VERSION = "2024-10-01"
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
URL_VERIFY = f"{CLERK_URL}/client/verify?__clerk_api_version={CLERK_API_VERSION}&_clerk_js_version={CLIENT_JS_VERSION}"


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


# ===================== CLIENTE BASE CON CLOUDFLARE BYPASS ===================== #
class CloudflareBypassClient:
    """Cliente base con manejo de desafíos Cloudflare."""
    def __init__(self, cookie: str, proxies: Optional[Dict[str, str]] = None) -> None:
        self.headers = {
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
            "cookie": cookie
        }
        self._session = requests.Session(
            headers=self.headers,
            proxies=proxies,
            impersonate="chrome110",
            timeout=30
        )
        self._max_retries = 5
        self._retry_delay = 3
        self._sid = None
        self._jwt = None

    def _get_sid(self) -> str:
        response = self.request("GET", URL_SID)
        response.raise_for_status()
        self._sid = response.json()["response"]["last_active_session_id"]
        return self._sid

    def _get_jwt(self) -> str:
        if not self._sid:
            self._get_sid()
        url = URL_JWT.format(sid=self._sid)
        response = self.request("POST", url)
        response.raise_for_status()
        self._jwt = response.json().get("jwt")
        print(f"JWT obtenido: {self._jwt[:20]}...")
        return self._jwt

    def _renew(self) -> None:
        """Renueva el JWT y actualiza los headers de autorización."""
        try:
            jwt = self._get_jwt()
            self._session.headers["Authorization"] = f"Bearer {jwt}"
            print("Token JWT renovado y headers actualizados")
        except Exception as e:
            print(f"Error al renovar JWT: {e}")

    def _extend_session(self) -> None:
        """Extiende la sesión actual."""
        try:
            if not self._sid:
                self._get_sid()
            
            response = self.request("POST", URL_EXTEND, json={"session_id": self._sid})
            response.raise_for_status()
            
            data = response.json()
            if data.get("is_extended", False):
                print("Sesión extendida exitosamente")
                self._sid = data.get("session_id", self._sid)
            else:
                print("No se pudo extender la sesión")
        except Exception as e:
            print(f"Error al extender la sesión: {e}")

    def _touch_session(self) -> None:
        """Mantiene viva la sesión actual."""
        try:
            if not self._sid:
                self._get_sid()
            
            url = URL_TOUCH.format(sid=self._sid)
            response = self.request("POST", url)
            response.raise_for_status()
            print("Sesión actualizada (touch)")
        except Exception as e:
            print(f"Error al actualizar la sesión: {e}")

    def _handle_cloudflare(self, response: Response) -> bool:
        if response.status_code in (403, 503) and "cf-" in response.headers:
            print("Detectado desafío Cloudflare. Intentando bypass...")
            time.sleep(random.uniform(5, 8))
            return True
        return False

    async def _solve_hcaptcha(self) -> Optional[str]:
        """Resuelve el hCaptcha usando Puppeteer."""
        try:
            token = await self.hcaptcha_solver.solve_hcaptcha(
                site_key="a8befae5-34a6-44ad-a09b-5c7fcc0c6e5d",
                url="https://suno.com"
            )
            return token
        except Exception as e:
            print(f"Error resolviendo hCaptcha: {e}")
            return None
            
    # Añadir estos métodos en la clase CloudflareBypassClient

    def _verify_hcaptcha(self, token: str) -> bool:
        """Verifica el token de hCaptcha con la API de Suno."""
        try:
            response = self.request(
                "POST", 
                HCAPTCHA_VERIFY_URL,
                json={
                    "token": token,
                    "session_id": self._sid,
                    "type": "hcaptcha"
                }
            )
            
            if response.status_code == 200:
                print("Token de hCaptcha verificado correctamente")
                return True
            else:
                print(f"Error al verificar hCaptcha: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"Error durante la verificación de hCaptcha: {e}")
            return False

    def _verify_captcha(self, captcha_token: str) -> bool:
        """Verifica el token de captcha con la API de Clerk."""
        try:
            payload = {
                'captcha_token': captcha_token,
                'captcha_widget_type': 'invisible'
            }
            
            headers = {
                **self.headers,
                'content-type': 'application/x-www-form-urlencoded',
                'origin': 'https://suno.com',
                'referer': 'https://suno.com/'
            }
            
            response = self._session.request(
                "POST",
                URL_VERIFY,
                data=payload,
                headers=headers
            )
            
            if response.status_code == 200:
                print("Token de captcha verificado correctamente")
                return True
            else:
                print(f"Error al verificar captcha: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"Error durante la verificación de captcha: {e}")
            return False

    def _get_or_create_eventloop(self):
        """Obtiene el event loop actual o crea uno nuevo si es necesario."""
        try:
            return asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop

    def _run_async(self, coro):
        """Ejecuta una corutina de manera segura."""
        loop = self._get_or_create_eventloop()
        if loop.is_running():
            # Si el loop está corriendo, creamos uno nuevo en un thread separado
            return asyncio.run_coroutine_threadsafe(coro, loop).result()
        else:
            return loop.run_until_complete(coro)

    def request(self, method: str, url: str, **kwargs: Any) -> Response:
        retries = 0
        while retries < self._max_retries:
            try:
                kwargs["impersonate"] = "chrome110"
                response = self._session.request(method, url, **kwargs)
                
                if response.status_code == 200:
                    return response
                elif response.status_code == 401:
                    print(f"Error de autenticación (401). Reintentando... ({retries + 1}/{self._max_retries})")
                    self._renew()
                elif response.status_code == 422:
                    print("Error 422: Captcha requerido")
                    # Aquí podrías implementar la obtención del token de captcha
                    # Por ahora, solo manejamos el error
                    print("No se puede resolver el captcha automáticamente")
                    raise Exception("Se requiere captcha")
                elif self._handle_cloudflare(response):
                    print(f"Reintentando después del desafío Cloudflare... ({retries + 1}/{self._max_retries})")
                else:
                    response.raise_for_status()
                
            except Exception as e:
                print(f"Error en la solicitud: {e}")
                if "SSL" in str(e):
                    kwargs["verify"] = False
                
            retries += 1
            if retries < self._max_retries:
                sleep_time = self._retry_delay * (2 ** retries)
                time.sleep(sleep_time)
        
        raise Exception(f"No se pudo completar la solicitud después de {self._max_retries} intentos")

    def __del__(self):
        """Cleanup cuando se destruye el objeto."""
        try:
            if hasattr(self, 'hcaptcha_solver'):
                self._run_async(self._cleanup())
        except Exception as e:
            print(f"Error durante la limpieza: {e}")

    async def _cleanup(self):
        """Limpia los recursos de manera asíncrona."""
        if hasattr(self, 'hcaptcha_solver'):
            await self.hcaptcha_solver.close()

    def _refresh_session(self) -> None:
        try:
            user_agents = [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ]
            self.headers["User-Agent"] = random.choice(user_agents)
            self._session.headers.update(self.headers)
            self._session.cookies.clear()
            self._renew()  # Renovamos el JWT después de actualizar los headers
            print("Sesión actualizada con nuevos headers y JWT")
        except Exception as e:
            print(f"Error al actualizar la sesión: {e}")

# ===================== CLIENTE SUNO ===================== #
class Suno:
    """Cliente base para interactuar con la API de Suno."""
    def __init__(self, cookie: Optional[str] = None) -> None:
        cookie = cookie or COOKIE
        if not cookie:
            raise Exception("environment variable SUNO_COOKIE is not set")
        self._client = CloudflareBypassClient(cookie)
        self._sid = self._get_sid()
        print(f"SID: {self._sid}")
        self.songs = Songs(self)

    def _get_sid(self) -> str:
        response = self._client.request("GET", URL_SID)
        response.raise_for_status()
        return response.json()["response"]["last_active_session_id"]

    def _get_jwt(self) -> str:
        url = URL_JWT.format(sid=self._sid)
        response = self._client.request("POST", url)
        response.raise_for_status()
        jwt = response.json().get("jwt")
        print(f"jwt: {jwt}")
        return jwt

    def request(self, *args: Any, **kwargs: Any) -> Response:
        return self._client.request(*args, **kwargs)

    def get_song(self, id: str) -> Song:
        url = f"{URL_FEED}/?ids={id}"
        print(f"Fetching song with ID: {id}")
        response = self.request("GET", url)
        if not response.ok:
            raise Exception(f"Failed to get song: {response.status_code}: {response.text}")
        data = response.json()
        song = data[0]
        song["cover_image_url"] = song.get("image_large_url")
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
    def __init__(self, client: Suno) -> None:
        self._client = client

    def request(self, *args: Any, **kwargs: Any) -> Response:
        return self._client.request(*args, **kwargs)

class Songs(APIResource):
    """Gestión de canciones en Suno."""
    def generate(
        self,
        prompt: str,
        custom: bool = False,
        tags: str = "",
        negative_tags: str = "",
        instrumental: bool = False,
        title: Optional[str] = None,
        model: str = "chirp-v3-5",
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
        
        response = self.request("POST", url, json=payload)
        response.raise_for_status()
        return [Song(**clip) for clip in response.json().get("clips", [])]

    def wait_for_file(self, song_id: str, file_type: str = "audio", max_attempts: int = 30, delay: int = 2) -> Song:
        """
        Espera hasta que el archivo (audio o video) de una canción esté disponible.
        
        Args:
            song_id: ID de la canción
            file_type: Tipo de archivo ('audio' o 'video')
            max_attempts: Número máximo de intentos
            delay: Tiempo de espera entre intentos en segundos
            
        Returns:
            Song: Objeto Song con el archivo disponible
            
        Raises:
            Exception: Si el archivo no está disponible después de max_attempts
        """
        attempts = 0
        while attempts < max_attempts:
            song = self._client.get_song(song_id)
            
            if file_type == "audio" and song.audio_url:
                return song
            elif file_type == "video" and song.video_url:
                return song
            elif file_type == "image" and song.cover_image_url:
                return song
                
            print(f"Archivo {file_type} no disponible aún. Intento {attempts + 1}/{max_attempts} {song}")
            time.sleep(delay)
            attempts += 1
            
        raise Exception(f"Tiempo de espera agotado esperando el archivo {file_type} para la canción {song_id}")

# ===================== FUNCIONES AUXILIARES ===================== #
def _get_id(song: Union[str, Song]) -> str:
    if isinstance(song, Song):
        return song.id
    match = re.search(r"[a-fA-F0-9\-]{36}", song)
    if match:
        return match.group(0)
    raise ValueError("Invalid song ID or format")