"""
Invictus API service for external WordPress API calls.
"""
import requests
from typing import Dict, Any, Optional
from logger_config import get_logger

logger = get_logger(__name__)


class InvictusAPIService:
    """Service for Invictus WordPress API operations."""
    
    # Browser-like headers to bypass Mod_Security
    DEFAULT_HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/html, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    }
    
    def __init__(self, api_url: str, headers: Optional[Dict[str, str]] = None) -> None:
        """
        Initialize Invictus API service.
        
        Args:
            api_url: Base WordPress API URL
            headers: Optional custom headers (defaults to DEFAULT_HEADERS)
        """
        self.api_url: str = api_url
        self.headers: Dict[str, str] = headers or self.DEFAULT_HEADERS
    
    def get_posts(
        self,
        posts_per_page: int = 1,
        page: int = 1
    ) -> list[Dict[str, Any]]:
        """
        Get posts from Invictus WordPress API.
        
        Args:
            posts_per_page: Number of posts per page
            page: Page number to retrieve
            
        Returns:
            List of post dictionaries
            
        Raises:
            requests.RequestException: If API request fails
            ValueError: If API returns non-200 status code
        """
        url = f"{self.api_url}&per_page={posts_per_page}&page={page}"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            posts = response.json()
            logger.info(f'Successfully retrieved {len(posts)} posts from Invictus API')
            return posts
        except requests.RequestException as e:
            logger.error(f'Failed to get invictus posts: {str(e)}')
            raise ValueError(f"Failed to get invictus post: {response.status_code if 'response' in locals() else 'N/A'} {str(e)}") from e

