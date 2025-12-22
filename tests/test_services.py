"""
Unit tests for service layer.

This module provides tests for S3, DynamoDB, Idempotency, and API services.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from services.s3_service import S3Service
from services.dynamodb_service import DynamoDBService
from services.idempotency_service import IdempotencyService
from services.invictus_api_service import InvictusAPIService


class TestS3Service:
    """Tests for S3Service."""
    
    def test_init(self):
        """Test S3Service initialization."""
        service = S3Service("test-bucket")
        assert service.bucket_name == "test-bucket"
        assert service._s3_resource is None
        assert service._s3_client is None
    
    @patch('services.s3_service.boto3')
    def test_s3_resource_lazy_init(self, mock_boto3):
        """Test lazy initialization of S3 resource."""
        mock_resource = Mock()
        mock_boto3.resource.return_value = mock_resource
        
        service = S3Service("test-bucket")
        resource = service.s3_resource
        
        assert resource == mock_resource
        mock_boto3.resource.assert_called_once_with('s3')
    
    @patch('services.s3_service.boto3')
    def test_s3_client_lazy_init(self, mock_boto3):
        """Test lazy initialization of S3 client."""
        mock_client = Mock()
        mock_boto3.client.return_value = mock_client
        
        service = S3Service("test-bucket")
        client = service.s3_client
        
        assert client == mock_client
        mock_boto3.client.assert_called_once_with('s3')
    
    @patch('services.s3_service.boto3')
    def test_object_exists_true(self, mock_boto3):
        """Test object_exists returns True when object exists."""
        mock_client = Mock()
        mock_client.head_object.return_value = {}
        mock_boto3.client.return_value = mock_client
        
        service = S3Service("test-bucket")
        result = service.object_exists("test-key")
        
        assert result is True
        mock_client.head_object.assert_called_once_with(
            Bucket="test-bucket",
            Key="test-key"
        )
    
    @patch('services.s3_service.boto3')
    def test_object_exists_false_404(self, mock_boto3):
        """Test object_exists returns False for 404 errors."""
        from botocore.exceptions import ClientError
        
        mock_client = Mock()
        error_response = {'Error': {'Code': '404'}}
        mock_client.head_object.side_effect = ClientError(
            error_response, 'HeadObject'
        )
        mock_boto3.client.return_value = mock_client
        
        service = S3Service("test-bucket")
        result = service.object_exists("test-key")
        
        assert result is False


class TestDynamoDBService:
    """Tests for DynamoDBService."""
    
    def test_init(self):
        """Test DynamoDBService initialization."""
        service = DynamoDBService()
        assert service._client is None
    
    @patch('services.dynamodb_service.boto3')
    def test_client_lazy_init(self, mock_boto3):
        """Test lazy initialization of DynamoDB client."""
        mock_client = Mock()
        mock_boto3.client.return_value = mock_client
        
        service = DynamoDBService()
        client = service.client
        
        assert client == mock_client
        mock_boto3.client.assert_called_once_with('dynamodb')


class TestIdempotencyService:
    """Tests for IdempotencyService."""
    
    def test_init(self):
        """Test IdempotencyService initialization."""
        service = IdempotencyService("test-table")
        assert service.table_name == "test-table"
        assert isinstance(service.dynamodb_service, DynamoDBService)
    
    def test_generate_key(self):
        """Test idempotency key generation."""
        key = IdempotencyService.generate_key("test-op", "test-id")
        assert isinstance(key, str)
        assert len(key) == 64  # SHA256 hex digest length
        
        # Same input should produce same key
        key2 = IdempotencyService.generate_key("test-op", "test-id")
        assert key == key2
        
        # Different input should produce different key
        key3 = IdempotencyService.generate_key("test-op", "test-id2")
        assert key != key3
    
    def test_check_no_table(self):
        """Test check returns False when table name not set."""
        service = IdempotencyService(None)
        result = service.check("test-key")
        assert result is False
    
    @patch('services.idempotency_service.DynamoDBService')
    def test_check_item_exists(self, mock_dynamodb_service_class):
        """Test check returns True when item exists."""
        mock_service = Mock()
        mock_service.get_item.return_value = {"idempotency_key": {"S": "test-key"}}
        mock_dynamodb_service_class.return_value = mock_service
        
        service = IdempotencyService("test-table")
        result = service.check("test-key")
        
        assert result is True
        mock_service.get_item.assert_called_once()
    
    @patch('services.idempotency_service.DynamoDBService')
    def test_check_item_not_exists(self, mock_dynamodb_service_class):
        """Test check returns False when item doesn't exist."""
        mock_service = Mock()
        mock_service.get_item.return_value = None
        mock_dynamodb_service_class.return_value = mock_service
        
        service = IdempotencyService("test-table")
        result = service.check("test-key")
        
        assert result is False


class TestInvictusAPIService:
    """Tests for InvictusAPIService."""
    
    def test_init_default_headers(self):
        """Test InvictusAPIService initialization with default headers."""
        service = InvictusAPIService("https://api.example.com")
        assert service.api_url == "https://api.example.com"
        assert service.headers == InvictusAPIService.DEFAULT_HEADERS
    
    def test_init_custom_headers(self):
        """Test InvictusAPIService initialization with custom headers."""
        custom_headers = {"Custom-Header": "value"}
        service = InvictusAPIService("https://api.example.com", custom_headers)
        assert service.headers == custom_headers
    
    @patch('services.invictus_api_service.requests.get')
    def test_get_posts_success(self, mock_get):
        """Test successful get_posts call."""
        mock_response = Mock()
        mock_response.json.return_value = [{"id": 1, "title": "Test Post"}]
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        service = InvictusAPIService("https://api.example.com")
        posts = service.get_posts(posts_per_page=1, page=1)
        
        assert len(posts) == 1
        assert posts[0]["id"] == 1
        mock_get.assert_called_once()
    
    @patch('services.invictus_api_service.requests.get')
    def test_get_posts_error(self, mock_get):
        """Test get_posts raises error on API failure."""
        import requests
        mock_get.side_effect = requests.RequestException("Connection error")
        
        service = InvictusAPIService("https://api.example.com")
        
        with pytest.raises(ValueError):
            service.get_posts()

