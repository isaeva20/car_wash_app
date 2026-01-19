import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from datetime import datetime
import socket
import os

class CentralizedLogger:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(CentralizedLogger, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.service_name = os.getenv("SERVICE_NAME", "unknown")
        self.hostname = socket.gethostname()
        self.log_dir = Path("logs")
        self.log_dir.mkdir(exist_ok=True)
        
        # Простой формат БЕЗ service_name и hostname
        self.LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        self.DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
        
        self.root_logger = logging.getLogger()
        self.root_logger.setLevel(logging.INFO)
        self.root_logger.handlers.clear()
        
        self._setup_handlers()
        self._initialized = True
    
    def _setup_handlers(self):
        formatter = logging.Formatter(self.LOG_FORMAT, self.DATE_FORMAT)
        
        # 1. Консольный обработчик
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        self.root_logger.addHandler(console_handler)
        
        # 2. Файловый обработчик
        common_log_file = self.log_dir / f"all_services_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = RotatingFileHandler(
            common_log_file,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=10,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)
        self.root_logger.addHandler(file_handler)
        
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    
    def get_logger(self, name: str) -> logging.Logger:
        """Получить именованный логгер"""
        logger = logging.getLogger(name)
        logger.propagate = True
        return logger

# Синглтон инстанс
central_logger = CentralizedLogger()