# 08.07.25
# Logger module per VCore Monitor

import os
import json
import time
from datetime import datetime

class Logger:
    def __init__(self, log_dir=None):
        """
        Inizializza il logger
        
        Args:
            log_dir: Directory dove salvare i file di log. Se None, usa ./logs
        """
        if log_dir is None:
            # Usa la directory logs nella root del progetto
            self.log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
        else:
            self.log_dir = log_dir
        
        # Crea la directory se non esiste
        os.makedirs(self.log_dir, exist_ok=True)
        
        # Usa un nome file fisso
        self.log_file = os.path.join(
            self.log_dir, 
            "vcore_log.json"
        )
        
        # Inizializza un array vuoto per i log
        self.logs = []
        
        # Logging iniziale (solo sul file)
        self.system_log("Logger initialized")
    
    def command_log(self, command):
        """
        Logga un comando inviato al dispositivo
        
        Args:
            command: Dizionario del comando inviato
        """
        entry = {
            "type": "command",
            "data": command
        }
        self.logs.append(entry)
        self._save_logs()
    
    def response_log(self, response):
        """
        Logga una risposta ricevuta dal dispositivo
        
        Args:
            response: Dizionario della risposta ricevuta
        """
        entry = {
            "type": "response",
            "data": response
        }
        self.logs.append(entry)
        self._save_logs()
    
    def system_log(self, message, data=None):
        """
        Logga un messaggio di sistema
        
        Args:
            message: Il messaggio da loggare
            data: Dati opzionali associati al messaggio
        """
        entry = {
            "type": "system",
            "message": message,
            "data": data
        }
        self.logs.append(entry)
        self._save_logs()
    
    def error_log(self, error_message, exception=None):
        """
        Logga un errore
        
        Args:
            error_message: Il messaggio di errore
            exception: L'eccezione che ha causato l'errore (opzionale)
        """
        entry = {
            "type": "error",
            "message": error_message,
            "exception": str(exception) if exception else None
        }
        self.logs.append(entry)
        self._save_logs()
    
    def _save_logs(self):
        """Salva i log su file con un dizionario per linea"""
        try:
            with open(self.log_file, 'w') as f:
                # Salva ogni dictionary su una linea separata
                for i, log_entry in enumerate(self.logs):
                    f.write(json.dumps(log_entry, separators=(',', ':')))
                    f.write('\n')  # Aggiungi una nuova linea dopo ogni entry
        except Exception:
            # Non possiamo loggare se fallisce il salvataggio del log
            pass
    
    def get_log_file_path(self):
        """Restituisce il percorso del file di log"""
        return self.log_file
    
    def get_session_summary(self):
        """Restituisce un riepilogo della sessione corrente"""
        if not self.logs:
            return {
                "total_entries": 0,
                "commands": 0,
                "responses": 0,
                "errors": 0
            }
        
        commands = sum(1 for log in self.logs if log["type"] == "command")
        responses = sum(1 for log in self.logs if log["type"] == "response")
        errors = sum(1 for log in self.logs if log["type"] == "error")
        
        return {
            "total_entries": len(self.logs),
            "commands": commands,
            "responses": responses,
            "errors": errors
        }

_logger = None

def get_logger(log_dir=None):
    """
    Restituisce l'istanza globale del logger, creandola se non esiste.
    
    Args:
        log_dir: Directory dove salvare i file di log. Usato solo alla prima chiamata.
        
    Returns:
        L'istanza del logger
    """
    global _logger
    if _logger is None:
        _logger = Logger(log_dir)
    return _logger
