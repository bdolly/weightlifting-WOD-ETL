"""
Unit tests for configuration module.
"""
import pytest
import os
from unittest.mock import patch
from config import Config, get_config


class TestConfig:
    """Tests for Config class."""
    
    @patch.dict(os.environ, {
        'INVICTUS_BUCKET': 'test-bucket',
        'INVICTUS_WEIGHTLIFTING_API': 'https://api.example.com',
    })
    def test_from_env_minimal(self):
        """Test Config.from_env with minimal required variables."""
        config = Config.from_env()
        assert config.invictus_bucket == 'test-bucket'
        assert config.invictus_weightlifting_api == 'https://api.example.com'
        assert config.invictus_weightlifting_api_cat_id == '213'  # default
        assert config.aws_region == 'us-east-1'  # default
        assert config.log_level == 'INFO'  # default
    
    @patch.dict(os.environ, {
        'INVICTUS_BUCKET': 'test-bucket',
        'INVICTUS_WEIGHTLIFTING_API': 'https://api.example.com',
        'INVICTUS_WEIGHTLIFTING_API_CAT_ID': '456',
        'AWS_REGION': 'us-west-2',
        'LOG_LEVEL': 'DEBUG',
    })
    def test_from_env_all_variables(self):
        """Test Config.from_env with all variables set."""
        config = Config.from_env()
        assert config.invictus_bucket == 'test-bucket'
        assert config.invictus_weightlifting_api == 'https://api.example.com'
        assert config.invictus_weightlifting_api_cat_id == '456'
        assert config.aws_region == 'us-west-2'
        assert config.log_level == 'DEBUG'
    
    @patch.dict(os.environ, {}, clear=True)
    def test_from_env_missing_required(self):
        """Test Config.from_env raises error when required vars missing."""
        with pytest.raises(ValueError, match="INVICTUS_BUCKET"):
            Config.from_env()
    
    @patch.dict(os.environ, {
        'INVICTUS_BUCKET': 'test-bucket',
    }, clear=True)
    def test_from_env_missing_api(self):
        """Test Config.from_env raises error when API var missing."""
        with pytest.raises(ValueError, match="INVICTUS_WEIGHTLIFTING_API"):
            Config.from_env()
    
    @patch.dict(os.environ, {
        'INVICTUS_BUCKET': 'test-bucket',
        'INVICTUS_WEIGHTLIFTING_API': 'https://api.example.com',
        'LOG_LEVEL': 'INVALID',
    })
    def test_from_env_invalid_log_level(self):
        """Test Config.from_env raises error for invalid log level."""
        with pytest.raises(ValueError, match="LOG_LEVEL"):
            Config.from_env()
    
    @patch.dict(os.environ, {
        'INVICTUS_BUCKET': 'test-bucket',
        'INVICTUS_WEIGHTLIFTING_API': 'https://api.example.com',
    })
    def test_get_config_singleton(self):
        """Test get_config returns singleton instance."""
        # Reset global config
        import config
        config._config = None
        
        config1 = get_config()
        config2 = get_config()
        
        assert config1 is config2

