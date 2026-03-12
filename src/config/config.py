import yaml
from pathlib import Path
from typing import Any, Dict


class Config:
    """Configuration manager for loading and accessing config.yaml"""
    
    def __init__(self):
        self._config: Dict[str, Any] = {}
        self._load_config()
    
    def _load_config(self):
        """Load configuration from YAML file"""
        # Get the project root directory (operator360-api)
        config_path = Path(__file__).parent.parent.parent / "resources" / "config.yaml"
        
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found at: {config_path}")
        
        with open(config_path, 'r') as file:
            self._config = yaml.safe_load(file)
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value by key.
        Supports nested keys using dot notation (e.g., 'database.host')
        """
        keys = key.split('.')
        value = self._config
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default
        
        return value
    
    @property
    def database(self) -> Dict[str, Any]:
        """Get database configuration"""
        return self._config.get('database', {})
    
    @property
    def all(self) -> Dict[str, Any]:
        """Get all configuration"""
        return self._config


# Singleton instance
config = Config()
