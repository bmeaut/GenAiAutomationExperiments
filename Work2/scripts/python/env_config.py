#!/usr/bin/env python3
"""
Environment Configuration Loader
Loads settings from .env file and environment variables
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional, Union
import logging

logger = logging.getLogger(__name__)


class EnvironmentConfig:
    """
    Environment configuration manager
    Loads settings from .env file and environment variables
    """
    
    def __init__(self, env_file: str = ".env"):
        self.env_file = env_file
        self.config = {}
        self.load_environment()
    
    def load_environment(self):
        """Load environment variables from .env file and system environment"""
        try:
            # First load from .env file if it exists
            env_path = Path(self.env_file)
            if env_path.exists():
                self._load_env_file(env_path)
                logger.info(f"✅ Loaded environment from {self.env_file}")
            else:
                logger.warning(f"⚠️ .env file not found: {env_path}")
                logger.info("Copy .env.example to .env and update with your values")
            
            # Then load from system environment (overrides .env)
            self._load_system_environment()
            
        except Exception as e:
            logger.error(f"❌ Error loading environment: {e}")
    
    def _load_env_file(self, env_path: Path):
        """Load variables from .env file"""
        try:
            with open(env_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    
                    # Skip empty lines and comments
                    if not line or line.startswith('#') or line.startswith('='):
                        continue
                    
                    # Parse KEY=VALUE format
                    if '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        
                        # Remove quotes if present
                        if value.startswith('"') and value.endswith('"'):
                            value = value[1:-1]
                        elif value.startswith("'") and value.endswith("'"):
                            value = value[1:-1]
                        
                        # Convert boolean strings
                        if value.lower() in ('true', 'false'):
                            value = value.lower() == 'true'
                        
                        # Convert numeric strings
                        elif value.isdigit():
                            value = int(value)
                        
                        # Try to convert float
                        elif '.' in value and value.replace('.', '').isdigit():
                            try:
                                value = float(value)
                            except ValueError:
                                pass
                        
                        self.config[key] = value
                    
        except Exception as e:
            logger.error(f"❌ Error parsing .env file: {e}")
    
    def _load_system_environment(self):
        """Load from system environment variables"""
        # Load all environment variables that start with common prefixes
        env_prefixes = [
            'GOOGLE_', 'EMAIL_', 'OFFICE_', 'INPUT_', 'OUTPUT_', 
            'TEMPLATES_', 'LOGS_', 'DEFAULT_', 'AUTO_', 'MAX_',
            'REPORT_', 'NOTIFICATION_', 'LOG_', 'DEBUG_', 'TEST_',
            'MOCK_', 'API_', 'ALLOW_', 'REQUIRE_', 'USE_', 'SKIP_',
            'DRY_', 'VERBOSE_', 'SAVE_'
        ]
        
        for key, value in os.environ.items():
            if any(key.startswith(prefix) for prefix in env_prefixes):
                self.config[key] = value
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        return self.config.get(key, default)
    
    def get_bool(self, key: str, default: bool = False) -> bool:
        """Get boolean configuration value"""
        value = self.get(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ('true', '1', 'yes', 'on')
        return bool(value)
    
    def get_int(self, key: str, default: int = 0) -> int:
        """Get integer configuration value"""
        value = self.get(key, default)
        try:
            return int(value)
        except (ValueError, TypeError):
            return default
    
    def get_float(self, key: str, default: float = 0.0) -> float:
        """Get float configuration value"""
        value = self.get(key, default)
        try:
            return float(value)
        except (ValueError, TypeError):
            return default
    
    def get_list(self, key: str, separator: str = ',', default: list = None) -> list:
        """Get list configuration value (comma-separated by default)"""
        if default is None:
            default = []
        
        value = self.get(key, '')
        if not value:
            return default
        
        if isinstance(value, str):
            return [item.strip() for item in value.split(separator) if item.strip()]
        
        return default
    
    def is_configured(self, key: str) -> bool:
        """Check if a configuration key is set and not empty"""
        value = self.get(key)
        if value is None:
            return False
        if isinstance(value, str):
            return value.strip() != '' and value != f'your_{key.lower()}_here'
        return True
    
    def validate_required_keys(self, required_keys: list) -> Dict[str, bool]:
        """Validate that required configuration keys are set"""
        results = {}
        for key in required_keys:
            results[key] = self.is_configured(key)
        return results
    
    def get_google_config(self) -> Dict[str, Any]:
        """Get Google API configuration"""
        return {
            'enabled': self.is_configured('GOOGLE_API_KEY'),
            'api_key': self.get('GOOGLE_API_KEY'),
            'default_sheet_name': self.get('DEFAULT_SHEET_NAME', 'Sheet1'),
            'default_range': self.get('DEFAULT_RANGE', 'A:Z'),
            'example_spreadsheet_id': self.get('EXAMPLE_SPREADSHEET_ID'),
            'request_delay': self.get_float('API_REQUEST_DELAY_SECONDS', 0.5),
            'timeout': self.get_int('API_TIMEOUT_SECONDS', 30)
        }
    
    def get_email_config(self) -> Dict[str, Any]:
        """Get email configuration"""
        return {
            'enabled': self.is_configured('EMAIL_USERNAME') and self.is_configured('EMAIL_PASSWORD'),
            'smtp_server': self.get('EMAIL_SMTP_SERVER', 'smtp.gmail.com'),
            'smtp_port': self.get_int('EMAIL_SMTP_PORT', 587),
            'username': self.get('EMAIL_USERNAME'),
            'password': self.get('EMAIL_PASSWORD'),
            'from_name': self.get('EMAIL_FROM_NAME', 'Office Automation System'),
            'subject_prefix': self.get('EMAIL_SUBJECT_PREFIX', '[Automated]'),
            'report_recipients': self.get_list('REPORT_RECIPIENTS'),
            'notification_recipients': self.get_list('NOTIFICATION_RECIPIENTS'),
            'send_delay': self.get_float('EMAIL_SEND_DELAY_SECONDS', 1.0),
            'auto_send': self.get_bool('AUTO_SEND_EMAIL', False)
        }
    
    def get_office_config(self) -> Dict[str, Any]:
        """Get Microsoft Office configuration"""
        return {
            'excel_visible': self.get_bool('OFFICE_EXCEL_VISIBLE', False),
            'word_visible': self.get_bool('OFFICE_WORD_VISIBLE', False),
            'powerpoint_visible': self.get_bool('OFFICE_POWERPOINT_VISIBLE', False)
        }
    
    def get_paths_config(self) -> Dict[str, Any]:
        """Get file paths configuration"""
        return {
            'input_dir': self.get('INPUT_DIR', 'data'),
            'output_dir': self.get('OUTPUT_DIR', 'outputs'),
            'templates_dir': self.get('TEMPLATES_DIR', 'templates'),
            'logs_dir': self.get('LOGS_DIR', 'logs'),
            'default_excel_file': self.get('DEFAULT_EXCEL_FILE', 'data/sample_data.xlsx'),
            'default_word_template': self.get('DEFAULT_WORD_TEMPLATE', 'templates/document_template.docx'),
            'default_csv_file': self.get('DEFAULT_CSV_FILE', 'data/sample_data.csv')
        }
    
    def get_automation_config(self) -> Dict[str, Any]:
        """Get automation settings"""
        return {
            'auto_convert_to_pdf': self.get_bool('AUTO_CONVERT_TO_PDF', True),
            'auto_send_email': self.get_bool('AUTO_SEND_EMAIL', False),
            'auto_cleanup_temp_files': self.get_bool('AUTO_CLEANUP_TEMP_FILES', True),
            'max_records_per_batch': self.get_int('MAX_RECORDS_PER_BATCH', 1000),
            'allow_file_overwrite': self.get_bool('ALLOW_FILE_OVERWRITE', False),
            'require_confirmation': self.get_bool('REQUIRE_CONFIRMATION_FOR_BATCH_OPERATIONS', True),
            'max_file_size_mb': self.get_int('MAX_FILE_SIZE_MB', 50)
        }
    
    def get_logging_config(self) -> Dict[str, Any]:
        """Get logging configuration"""
        return {
            'level': self.get('LOG_LEVEL', 'INFO'),
            'file': self.get('LOG_FILE', 'automation_pipeline.log'),
            'max_size_mb': self.get_int('LOG_MAX_SIZE_MB', 10),
            'backup_count': self.get_int('LOG_BACKUP_COUNT', 5),
            'debug_mode': self.get_bool('DEBUG_MODE', False),
            'verbose_output': self.get_bool('VERBOSE_OUTPUT', False)
        }
    
    def print_configuration_status(self):
        """Print current configuration status"""
        print("📋 Configuration Status")
        print("=" * 50)
        
        # Check Google API
        google_config = self.get_google_config()
        status = "✅ Configured" if google_config['enabled'] else "❌ Not configured"
        print(f"Google API: {status}")
        
        # Check Email
        email_config = self.get_email_config()
        status = "✅ Configured" if email_config['enabled'] else "❌ Not configured"
        print(f"Email: {status}")
        
        # Check file paths
        paths_config = self.get_paths_config()
        input_exists = os.path.exists(paths_config['input_dir'])
        output_exists = os.path.exists(paths_config['output_dir'])
        print(f"Input directory: {'✅' if input_exists else '❌'} {paths_config['input_dir']}")
        print(f"Output directory: {'✅' if output_exists else '❌'} {paths_config['output_dir']}")
        
        # Missing configuration
        missing = []
        if not google_config['enabled']:
            missing.append("GOOGLE_API_KEY")
        if not email_config['enabled']:
            missing.extend(["EMAIL_USERNAME", "EMAIL_PASSWORD"])
        
        if missing:
            print(f"\n⚠️ Missing configuration: {', '.join(missing)}")
            print("Copy .env.example to .env and update with your values")
        else:
            print("\n🎉 All major components configured!")


def load_environment(env_file: str = ".env") -> EnvironmentConfig:
    """Load environment configuration"""
    return EnvironmentConfig(env_file)


def main():
    """Test the environment configuration"""
    print("🔧 Testing Environment Configuration")
    print("=" * 50)
    
    env_config = load_environment()
    env_config.print_configuration_status()
    
    print("\n📝 Sample configuration values:")
    print(f"Google API configured: {env_config.is_configured('GOOGLE_API_KEY')}")
    print(f"Email configured: {env_config.is_configured('EMAIL_USERNAME')}")
    print(f"Auto PDF conversion: {env_config.get_bool('AUTO_CONVERT_TO_PDF', True)}")
    print(f"Max records per batch: {env_config.get_int('MAX_RECORDS_PER_BATCH', 1000)}")
    print(f"Report recipients: {env_config.get_list('REPORT_RECIPIENTS')}")


if __name__ == "__main__":
    main()