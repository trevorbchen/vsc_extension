"""
Configuration management for the formal verifier extension.
Handles settings, API endpoints, and user preferences.
"""

import json
import os
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path

@dataclass
class APIConfig:
    """Configuration for API endpoints."""
    annotator_url: str = "http://localhost:8000/annotate"
    verifier_url: str = "http://localhost:8001/verify"
    timeout: int = 30
    auth_token: Optional[str] = None

@dataclass
class VerificationConfig:
    """Configuration for verification behavior."""
    inline_dependencies: bool = True
    preserve_temp_files: bool = False
    max_file_size: int = 1024 * 1024  # 1MB
    supported_extensions: list = None
    
    def __post_init__(self):
        if self.supported_extensions is None:
            self.supported_extensions = ['.c', '.h']

@dataclass
class UIConfig:
    """Configuration for UI behavior."""
    show_progress: bool = True
    auto_save_before_verify: bool = True
    result_display_mode: str = "panel"  # "panel" or "diagnostics"

@dataclass
class Config:
    """Main configuration container."""
    api: APIConfig
    verification: VerificationConfig
    ui: UIConfig
    project_root: Optional[str] = None

class ConfigManager:
    """Manages configuration loading, saving, and validation."""
    
    DEFAULT_CONFIG_NAME = ".formalverifier.json"
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or self._find_config_file()
        self._config = self._load_config()
    
    def _find_config_file(self) -> str:
        """Find config file in project root or create default path."""
        # Look for config in current directory and parent directories
        current_dir = Path.cwd()
        for parent in [current_dir] + list(current_dir.parents):
            config_file = parent / self.DEFAULT_CONFIG_NAME
            if config_file.exists():
                return str(config_file)
        
        # Return default path if not found
        return str(current_dir / self.DEFAULT_CONFIG_NAME)
    
    def _load_config(self) -> Config:
        """Load configuration from file or create default."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    data = json.load(f)
                return self._dict_to_config(data)
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                print(f"Warning: Invalid config file {self.config_path}: {e}")
                return self._create_default_config()
        else:
            return self._create_default_config()
    
    def _create_default_config(self) -> Config:
        """Create default configuration."""
        return Config(
            api=APIConfig(),
            verification=VerificationConfig(),
            ui=UIConfig()
        )
    
    def _dict_to_config(self, data: Dict[str, Any]) -> Config:
        """Convert dictionary to Config object."""
        api_data = data.get('api', {})
        verification_data = data.get('verification', {})
        ui_data = data.get('ui', {})
        
        return Config(
            api=APIConfig(**{k: v for k, v in api_data.items() if hasattr(APIConfig, k)}),
            verification=VerificationConfig(**{k: v for k, v in verification_data.items() if hasattr(VerificationConfig, k)}),
            ui=UIConfig(**{k: v for k, v in ui_data.items() if hasattr(UIConfig, k)}),
            project_root=data.get('project_root')
        )
    
    def save_config(self) -> bool:
        """Save current configuration to file."""
        try:
            config_dict = asdict(self._config)
            with open(self.config_path, 'w') as f:
                json.dump(config_dict, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False
    
    def get_config(self) -> Config:
        """Get current configuration."""
        return self._config
    
    def update_config(self, **kwargs) -> None:
        """Update configuration values."""
        for key, value in kwargs.items():
            if hasattr(self._config, key):
                setattr(self._config, key, value)
    
    def validate_config(self) -> Dict[str, str]:
        """Validate configuration and return any errors."""
        errors = {}
        
        # Validate API URLs
        if not self._config.api.annotator_url.startswith(('http://', 'https://')):
            errors['api.annotator_url'] = "Must be a valid HTTP/HTTPS URL"
        
        if not self._config.api.verifier_url.startswith(('http://', 'https://')):
            errors['api.verifier_url'] = "Must be a valid HTTP/HTTPS URL"
        
        # Validate timeout
        if self._config.api.timeout <= 0:
            errors['api.timeout'] = "Timeout must be positive"
        
        # Validate file size limit
        if self._config.verification.max_file_size <= 0:
            errors['verification.max_file_size'] = "Max file size must be positive"
        
        # Validate UI display mode
        valid_modes = ['panel', 'diagnostics']
        if self._config.ui.result_display_mode not in valid_modes:
            errors['ui.result_display_mode'] = f"Must be one of: {', '.join(valid_modes)}"
        
        return errors

# Global config manager instance
_config_manager = None

def get_config_manager() -> ConfigManager:
    """Get or create global config manager instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager

def get_config() -> Config:
    """Get current configuration."""
    return get_config_manager().get_config()

# Environment variable overrides
def apply_env_overrides(config: Config) -> Config:
    """Apply environment variable overrides to config."""
    env_mappings = {
        'FORMALVERIFIER_ANNOTATOR_URL': ('api', 'annotator_url'),
        'FORMALVERIFIER_VERIFIER_URL': ('api', 'verifier_url'),
        'FORMALVERIFIER_AUTH_TOKEN': ('api', 'auth_token'),
        'FORMALVERIFIER_TIMEOUT': ('api', 'timeout', int),
        'FORMALVERIFIER_PROJECT_ROOT': ('project_root', str),
    }
    
    for env_var, mapping in env_mappings.items():
        value = os.environ.get(env_var)
        if value is not None:
            if len(mapping) == 3:  # Has type conversion
                section, key, converter = mapping
                try:
                    value = converter(value)
                except (ValueError, TypeError):
                    continue
            elif len(mapping) == 2:
                section, key = mapping
            else:
                config.project_root = value
                continue
            
            if hasattr(config, section):
                section_obj = getattr(config, section)
                if hasattr(section_obj, key):
                    setattr(section_obj, key, value)
    
    return config