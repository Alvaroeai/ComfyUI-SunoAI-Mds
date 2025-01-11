import logging
from playwright.async_api import async_playwright, Browser, Page
from typing import Dict, Any
import time
import json
import os
import random
import asyncio

logger = logging.getLogger(__name__)

class CaptchaSolver:
    def __init__(self):
        self._playwright = None
        self._browser: Browser = None
        self._page: Page = None

    async def init(self):
        """Inicializa el navegador con configuraciones anti-detección"""
        try:
            self._playwright = await async_playwright().start()
            
            # Usar chromium instalado por playwright en modo visible
            self._browser = await self._playwright.chromium.launch(
                headless=False,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--start-maximized',
                    '--disable-infobars',
                    '--disable-notifications'
                ]
            )
            
            # Crear contexto con evasión de detección
            context = await self._browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36',
                java_script_enabled=True,
                bypass_csp=True,
                ignore_https_errors=True,
                has_touch=True,
                locale='en-US',
                timezone_id='America/New_York',
                permissions=['geolocation']
            )

            # Añadir scripts de evasión
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                Object.defineProperty(navigator, 'plugins', { 
                    get: () => [
                        { name: 'Chrome PDF Plugin' },
                        { name: 'Chrome PDF Viewer' },
                        { name: 'Native Client' }
                    ]
                });
                Object.defineProperty(navigator, 'languages', { 
                    get: () => ['en-US', 'en', 'es'] 
                });
                Object.defineProperty(navigator, 'platform', { 
                    get: () => 'Win32' 
                });
                delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
                delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
                delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
            """)

            self._page = await context.new_page()
            logger.info("Browser initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing browser: {e}")
            await self.cleanup()
            raise

    async def solve_captcha(self, url: str, cookie: str) -> Dict[str, Any]:
        """Resuelve el captcha y devuelve las cookies actualizadas"""
        try:
            if not self._browser:
                await self.init()

            # Establecer las cookies
            logger.info("Setting cookies...")
            cookies = self._parse_cookie_string(cookie)
            await self._page.goto("https://suno.com")
            
            for name, value in cookies.items():
                await self._page.context.add_cookies([{
                    'name': name,
                    'value': value,
                    'domain': '.suno.com',
                    'path': '/'
                }])

            # Navegar a la página
            logger.info(f"Navigating to {url}")
            await self._page.goto(url, wait_until='networkidle')
            
            try:
                # Esperar y buscar el iframe de hCaptcha
                logger.info("Looking for hCaptcha iframe...")
                frame = await self._page.wait_for_selector('iframe[src*="hcaptcha.com"]', timeout=10000)
                
                if frame:
                    # Obtener el frame del captcha
                    frames = self._page.frames
                    captcha_frame = next(f for f in frames if 'hcaptcha' in f.url)
                    
                    # Esperar y hacer clic en el checkbox
                    logger.info("Looking for checkbox...")
                    checkbox = await captcha_frame.wait_for_selector('#checkbox', timeout=5000)
                    
                    # Simular comportamiento humano
                    logger.info("Moving mouse...")
                    await self._page.mouse.move(random.randint(0, 100), random.randint(0, 100))
                    await asyncio.sleep(0.5)
                    
                    logger.info("Clicking checkbox...")
                    await checkbox.click()
                    
                    # Esperar a que se complete el captcha
                    await asyncio.sleep(10)
                    
                    # Esperar a que desaparezca el iframe o se complete
                    try:
                        await self._page.wait_for_selector('iframe[src*="hcaptcha.com"]', 
                                                         state='hidden', 
                                                         timeout=30000)
                        logger.info("Captcha completed successfully")
                    except:
                        logger.warning("Captcha might need manual intervention")
                    
            except Exception as e:
                logger.warning(f"No hCaptcha found or already solved: {e}")

            # Obtener las cookies actualizadas
            logger.info("Getting updated cookies...")
            cookies = await self._page.context.cookies()
            cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies}
            
            return cookie_dict

        except Exception as e:
            logger.error(f"Error solving captcha: {e}")
            raise
        finally:
            await self.cleanup()

    def _parse_cookie_string(self, cookie_string: str) -> Dict[str, str]:
        """Convierte una cadena de cookies en un diccionario"""
        cookies = {}
        for item in cookie_string.split(';'):
            if '=' in item:
                name, value = item.strip().split('=', 1)
                cookies[name] = value
        return cookies

    async def cleanup(self):
        """Limpia los recursos del navegador"""
        try:
            if self._page:
                await self._page.close()
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
        except Exception as e:
            logger.error(f"Error in cleanup: {e}") 