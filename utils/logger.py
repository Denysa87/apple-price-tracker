"""
Sistema de logging para o Apple Price Tracker.
Fornece logging estruturado para console e arquivo.
"""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


def setup_logger(
    name: str = "apple_price_tracker",
    log_dir: Optional[Path] = None,
    level: int = logging.INFO,
    console: bool = True,
    file: bool = True
) -> logging.Logger:
    """
    Configura e retorna um logger com handlers para console e arquivo.
    
    Args:
        name: Nome do logger
        log_dir: Diretório para guardar logs (default: logs/)
        level: Nível de logging (DEBUG, INFO, WARNING, ERROR)
        console: Se True, adiciona handler para console
        file: Se True, adiciona handler para arquivo
    
    Returns:
        Logger configurado
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Evitar duplicação de handlers
    if logger.handlers:
        return logger
    
    # Formato de log
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Handler para console
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    # Handler para arquivo
    if file:
        if log_dir is None:
            log_dir = Path(__file__).parent.parent / "logs"
        
        log_dir.mkdir(exist_ok=True)
        
        # Nome do arquivo com data
        log_file = log_dir / f"scraper_{datetime.now():%Y%m%d}.log"
        
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


def log_scraping_attempt(logger: logging.Logger, site: str, product: str, url: str) -> None:
    """Log de tentativa de scraping."""
    logger.info(f"Scraping {site} | {product} | {url[:60]}...")


def log_scraping_success(logger: logging.Logger, site: str, product: str, price: float, url: str) -> None:
    """Log de scraping bem-sucedido."""
    logger.info(f"✅ {site} | {product} | {price:.2f}€ | {url[:60]}")


def log_scraping_failure(logger: logging.Logger, site: str, product: str, reason: str) -> None:
    """Log de falha no scraping."""
    logger.warning(f"❌ {site} | {product} | {reason}")


def log_price_validation_failed(logger: logging.Logger, site: str, product: str, price: float, reason: str) -> None:
    """Log de validação de preço falhada."""
    logger.warning(f"⚠️  {site} | {product} | Preço {price:.2f}€ rejeitado: {reason}")


def log_cloudflare_block(logger: logging.Logger, site: str) -> None:
    """Log de bloqueio Cloudflare."""
    logger.warning(f"⛔ {site} | Cloudflare detectado")


def log_override_removed(logger: logging.Logger, product: str, site: str, failures: int) -> None:
    """Log de remoção de override."""
    logger.warning(f"🗑️  Override removido: {product} | {site} | {failures} falhas consecutivas")


def log_debug_saved(logger: logging.Logger, site: str, product: str, debug_dir: Path) -> None:
    """Log de debug info guardada."""
    logger.info(f"🔍 Debug guardado: {site} | {product} | {debug_dir}")


def log_summary(logger: logging.Logger, total: int, successful: int, failed: int, duration: float) -> None:
    """Log de resumo da execução."""
    success_rate = (successful / total * 100) if total > 0 else 0
    logger.info(f"📊 Resumo: {successful}/{total} sucessos ({success_rate:.1f}%) | {failed} falhas | {duration:.1f}s")
