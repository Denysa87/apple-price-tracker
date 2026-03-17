"""
Utilitários anti-bot para o Apple Price Tracker.
Ajuda a evitar detecção e bloqueios por sistemas anti-bot como Cloudflare.
"""

import random
import json
from pathlib import Path
from typing import Optional
from datetime import datetime


# Lista de User-Agents realistas (Chrome/Safari em macOS)
USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]


def get_random_user_agent() -> str:
    """Retorna um User-Agent aleatório da lista."""
    return random.choice(USER_AGENTS)


def get_realistic_headers(user_agent: Optional[str] = None) -> dict:
    """
    Retorna headers HTTP realistas que imitam um browser real.
    
    Args:
        user_agent: User-Agent específico (opcional, usa aleatório se None)
    
    Returns:
        Dicionário com headers HTTP completos
    """
    if user_agent is None:
        user_agent = get_random_user_agent()
    
    # Extrair versão do Chrome do User-Agent
    chrome_version = "124"
    if "Chrome/" in user_agent:
        try:
            chrome_version = user_agent.split("Chrome/")[1].split(".")[0]
        except Exception:
            pass
    
    return {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "pt-PT,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Cache-Control": "max-age=0",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "sec-ch-ua": f'"Chromium";v="{chrome_version}", "Google Chrome";v="{chrome_version}", "Not-A.Brand";v="99"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"macOS"',
        "DNT": "1",
    }


def get_random_delay(min_seconds: float = 2.0, max_seconds: float = 5.0) -> float:
    """
    Retorna um delay aleatório mais realista (não uniforme).
    Usa distribuição que favorece valores médios.
    
    Args:
        min_seconds: Delay mínimo em segundos
        max_seconds: Delay máximo em segundos
    
    Returns:
        Delay em segundos
    """
    # Usar distribuição triangular (favorece valores médios)
    mode = (min_seconds + max_seconds) / 2
    return random.triangular(min_seconds, max_seconds, mode)


def get_random_scroll_amount() -> int:
    """
    Retorna quantidade aleatória de scroll (em pixels).
    Simula comportamento humano de scroll.
    
    Returns:
        Pixels para scrollar (200-800)
    """
    return random.randint(200, 800)


async def simulate_human_behavior(page, logger=None) -> None:
    """
    Simula comportamento humano na página:
    - Scroll aleatório
    - Pequenos delays
    - Movimento do mouse (se possível)
    
    Args:
        page: Página do Playwright
        logger: Logger opcional para debug
    """
    try:
        # Scroll para baixo
        scroll_amount = get_random_scroll_amount()
        await page.evaluate(f"window.scrollBy(0, {scroll_amount})")
        await page.wait_for_timeout(random.randint(500, 1500))
        
        # Scroll para cima um pouco
        await page.evaluate(f"window.scrollBy(0, -{scroll_amount // 3})")
        await page.wait_for_timeout(random.randint(300, 800))
        
        if logger:
            logger.debug(f"Simulou scroll humano: {scroll_amount}px")
    
    except Exception as e:
        if logger:
            logger.debug(f"Erro ao simular comportamento: {e}")


class CookieManager:
    """Gerencia cookies persistentes entre execuções."""
    
    def __init__(self, cookies_file: Path):
        self.cookies_file = cookies_file
        self.cookies = self._load_cookies()
    
    def _load_cookies(self) -> dict:
        """Carrega cookies do arquivo."""
        if self.cookies_file.exists():
            try:
                with open(self.cookies_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Verificar se cookies não expiraram (7 dias)
                    saved_date = datetime.fromisoformat(data.get('saved_at', '2000-01-01'))
                    days_old = (datetime.now() - saved_date).days
                    if days_old < 7:
                        return data.get('cookies', {})
            except Exception:
                pass
        return {}
    
    def save_cookies(self, site: str, cookies: list) -> None:
        """
        Guarda cookies de um site.
        
        Args:
            site: Nome do site
            cookies: Lista de cookies do Playwright
        """
        self.cookies[site] = cookies
        try:
            with open(self.cookies_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'saved_at': datetime.now().isoformat(),
                    'cookies': self.cookies
                }, f, indent=2)
        except Exception:
            pass
    
    def get_cookies(self, site: str) -> Optional[list]:
        """
        Retorna cookies guardados para um site.
        
        Args:
            site: Nome do site
        
        Returns:
            Lista de cookies ou None
        """
        return self.cookies.get(site)
    
    async def load_cookies_to_context(self, context, site: str) -> bool:
        """
        Carrega cookies guardados para o contexto do browser.
        
        Args:
            context: Contexto do Playwright
            site: Nome do site
        
        Returns:
            True se cookies foram carregados
        """
        cookies = self.get_cookies(site)
        if cookies:
            try:
                await context.add_cookies(cookies)
                return True
            except Exception:
                pass
        return False
    
    async def save_cookies_from_context(self, context, site: str) -> None:
        """
        Guarda cookies do contexto do browser.
        
        Args:
            context: Contexto do Playwright
            site: Nome do site
        """
        try:
            cookies = await context.cookies()
            if cookies:
                self.save_cookies(site, cookies)
        except Exception:
            pass


class RetryStrategy:
    """Estratégia de retry com backoff exponencial."""
    
    def __init__(self, max_retries: int = 3, base_delay: float = 2.0, max_delay: float = 30.0):
        """
        Args:
            max_retries: Número máximo de tentativas
            base_delay: Delay base em segundos
            max_delay: Delay máximo em segundos
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
    
    def get_delay(self, attempt: int) -> float:
        """
        Calcula delay para uma tentativa específica usando backoff exponencial.
        
        Args:
            attempt: Número da tentativa (0-indexed)
        
        Returns:
            Delay em segundos
        """
        # Backoff exponencial: 2^attempt * base_delay
        delay = min(self.base_delay * (2 ** attempt), self.max_delay)
        # Adicionar jitter (±20%) para evitar thundering herd
        jitter = delay * 0.2 * (random.random() * 2 - 1)
        return max(0, delay + jitter)
    
    async def execute_with_retry(self, func, *args, logger=None, **kwargs):
        """
        Executa função com retry automático.
        
        Args:
            func: Função async para executar
            *args: Argumentos posicionais
            logger: Logger opcional
            **kwargs: Argumentos nomeados
        
        Returns:
            Resultado da função
        
        Raises:
            Exception: Se todas as tentativas falharem
        """
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                
                if attempt < self.max_retries - 1:
                    delay = self.get_delay(attempt)
                    if logger:
                        logger.warning(f"Tentativa {attempt + 1}/{self.max_retries} falhou: {str(e)[:100]}")
                        logger.info(f"Aguardando {delay:.1f}s antes de retry...")
                    
                    import asyncio
                    await asyncio.sleep(delay)
                else:
                    if logger:
                        logger.error(f"Todas as {self.max_retries} tentativas falharam")
        
        raise last_exception
