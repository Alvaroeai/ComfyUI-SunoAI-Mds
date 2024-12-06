import os
import datetime
import folder_paths
import time

from .suno.suno_client import *

class SunoAIGenerator:
    def __init__(self):
        self.output_dir = os.path.join(folder_paths.get_output_directory(), 'output/suno_ai_songs')
        os.makedirs(self.output_dir, exist_ok=True)

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt": ("STRING", {"default": "Enter your song idea here", "multiline": True}),  # Campo de entrada para prompt
                "custom": ("BOOLEAN", {"default": False}),  # Campo de entrada para custom
            },
            "optional": {
                # Solo se agregan los demás campos si "custom" es True
                "tags": ("STRING", {"default": ""}),
                "negative_tags": ("STRING", {"default": ""}),
                "title": ("STRING", {"default": "Song Title"}),
                "instrumental": ("BOOLEAN", {"default": False}),
                "model": (list(SunoConfig.AVAILABLE_MODELS.keys()), {
                    "default": "chirp-v3-5",
                    "display_name": "Generation Model",
                    "description": "Select the Suno AI model for song generation"
                }),
                "suno_cookie": ("STRING", {"multiline": True, "default": ""}),
            }
        }

    RETURN_TYPES = ("STRING", "STRING", "JSON")
    RETURN_NAMES = ("clip_id_01", "clip_id_02", "response")
    FUNCTION = "generate_songs"
    OUTPUT_NODE = True
    CATEGORY = "Mideas_SunoAI"

    def generate_songs(
            self, 
            prompt, 
            custom, 
            tags, 
            negative_tags, 
            instrumental, 
            title, 
            model, 
            suno_cookie
        ):
        try:
            # Inicializar cliente Suno con cookie proporcionada
            suno_client = Suno(cookie=suno_cookie)
            
            # Generar canciones solo si custom es True, de lo contrario solo se usan los campos principales
            if custom:
                # Generar canciones personalizadas (con tags, negative_tags, etc.)
                generated_songs = suno_client.songs.generate(
                    prompt=prompt,
                    custom=custom,
                    tags=tags,
                    negative_tags=negative_tags,
                    instrumental=instrumental,
                    title=title,
                    model=model
                )
            else:
                # Generar canciones sin campos personalizados
                generated_songs = suno_client.songs.generate(
                    prompt=prompt,
                    custom=custom,
                    instrumental=instrumental,
                    model=model
                )
            
            # Validar que se hayan generado canciones
            if not generated_songs or len(generated_songs) < 2:
                raise ValueError("Not enough songs generated")
            
            # Obtener los IDs de los clips generados
            clip_ids = [song.id for song in generated_songs]

            # Convertir la respuesta completa a una cadena JSON
            full_json_response = json.dumps(generated_songs, default=lambda o: o.__dict__, indent=4)

            # Retornar los IDs de los dos primeros clips
            return clip_ids[0], clip_ids[1], full_json_response
        
        except Exception as e:
            print(f"Song generation error: {e}")
            return "", ""

class SunoAudioManager:
    def __init__(self):
        self.output_dir = os.path.join(folder_paths.get_output_directory(), 'suno_audio_files')
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "audio_id": ("STRING", {"default": ""}),
                "suno_cookie": ("STRING", {"multiline": True, "default": ""}),
            },
            "optional": {
                "wait_audio": ("BOOLEAN", {"default": True}),
                "max_wait_time": ("INT", {"default": 300, "min": 1, "step": 1}),
                "download_audio": ("BOOLEAN", {"default": True}),
                "download_video": ("BOOLEAN", {"default": False}),
                "download_image": ("BOOLEAN", {"default": False}),
            },
        }

    RETURN_TYPES = (
        "STRING",  # Para el path de audio
        "STRING",  # Para el path de video
        "STRING",  # Para el path de imagen
        "STRING",  # Para la URL de audio
        "STRING",  # Para la URL de video
        "STRING",  # Para la URL de imagen
    )
    RETURN_NAMES = (
        "audio_url", "video_url", "image_url",
        "audio_path", "video_path", "image_path",
    )
    FUNCTION = "manage_audio"
    OUTPUT_NODE = True
    CATEGORY = "Media_SunoAudio"

    def manage_audio(
        self,
        audio_id,
        suno_cookie,
        wait_audio=True,
        max_wait_time=300,
        download_audio=True,
        download_video=False,
        download_image=False,
        check_interval=5
    ):
        try:
            if not audio_id:
                raise ValueError("Audio ID is required")
            
            if not suno_cookie:
                raise ValueError("Authorization token is required")

            # Inicializar cliente Suno con el token proporcionado
            suno_client = Suno(cookie=suno_cookie)
            self._client = suno_client  # Almacenar cliente para usar en `wait_for_file`
            downloader = Downloader()

            # Variables para almacenar resultados
            urls = {"audio": None, "video": None, "image": None}
            paths = {"audio": "", "video": "", "image": ""}
            types_to_download = []

            # Determinar qué tipos descargar
            if download_audio:
                types_to_download.append("audio")
            if download_video:
                types_to_download.append("video")
            if download_image:
                types_to_download.append("image")

            # Procesar cada tipo seleccionado
            for file_type in types_to_download:
                try:
                    print(f"Waiting for {file_type} to be ready...")
                    song = suno_client.songs.wait_for_file(audio_id, file_type, max_wait_time, check_interval)

                    # Obtener la URL correspondiente
                    if file_type == "audio":
                        urls[file_type] = song.audio_url
                    elif file_type == "video":
                        urls[file_type] = song.video_url
                    elif file_type == "image":
                        urls[file_type] = song.cover_image_url

                    # Descargar el archivo
                    print(f"Downloading {file_type} file...")
                    extension = {"audio": "mp3", "video": "mp4", "image": "jpg"}[file_type]
                    file_path = os.path.join(self.output_dir, f"{audio_id}.{extension}")
                    file_path = downloader.download(song, file_type, root=self.output_dir, name=f"{audio_id}.{extension}")

                    # Verificar la descarga
                    if not os.path.exists(file_path):
                        raise FileNotFoundError(f"Downloaded file not found: {file_path}")

                    paths[file_type] = file_path
                    print(f"{file_type.capitalize()} downloaded to: {paths[file_type]}")

                except Exception as e:
                    print(f"Error processing {file_type}: {e}")
                    import traceback
                    traceback.print_exc()

            # Retornar los resultados en el orden esperado
            return (
                urls["audio"], urls["video"], urls["image"],
                paths["audio"], paths["video"], paths["image"]
            )

        except Exception as e:
            print(f"Comprehensive error in manage_audio: {e}")
            import traceback
            traceback.print_exc()
            
            # Return a tuple of None values matching your RETURN_TYPES
            return (None, None, None, None, None, None)

# Node class mappings
NODE_CLASS_MAPPINGS = {
    "Mideas_SunoAI_Generator": SunoAIGenerator,
    "Mideas_SunoAI_AudioManager": SunoAudioManager
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "Mideas_SunoAI_Generator": "SunoAI Generator",
    "Mideas_SunoAI_AudioManager": "SunoAI Audio Manager"
}