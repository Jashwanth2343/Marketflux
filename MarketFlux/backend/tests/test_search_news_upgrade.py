"""
Test suite for P1 features: Enhanced Search Bar + News Grid with Thumbnails
- Enhanced Search: Uses yfinance Search API for natural company name lookup
- News Thumbnails: yfinance ticker news includes thumbnail_url field
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestEnhancedSearch:
    """Test enhanced search using yfinance Search API"""
    
    def test_search_corvus_returns_crvs(self):
        """Typing 'corvus' should return CRVS - Corvus Pharmaceuticals"""
        response = requests.get(f"{BASE_URL}/api/search-stocks?q=corvus")
        assert response.status_code == 200
        
        data = response.json()
        assert "results" in data
        assert len(data["results"]) > 0
        
        # First result should be CRVS
        first_result = data["results"][0]
        assert first_result["symbol"] == "CRVS"
        assert "Corvus" in first_result["name"]
        assert first_result["type"] == "Equity"
        assert first_result["exchange"] == "NASDAQ"
    
    def test_search_apple_returns_aapl_first(self):
        """Typing 'apple' should return AAPL - Apple Inc. as first result"""
        response = requests.get(f"{BASE_URL}/api/search-stocks?q=apple")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["results"]) > 0
        
        # First result should be AAPL
        first_result = data["results"][0]
        assert first_result["symbol"] == "AAPL"
        assert "Apple" in first_result["name"]
    
    def test_search_tesla_returns_tsla(self):
        """Typing 'tesla' should return TSLA with correct company name"""
        response = requests.get(f"{BASE_URL}/api/search-stocks?q=tesla")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["results"]) > 0
        
        first_result = data["results"][0]
        assert first_result["symbol"] == "TSLA"
        assert "Tesla" in first_result["name"]
    
    def test_search_micro_returns_microsoft_and_others(self):
        """Typing 'micro' should return Micron and other matches"""
        response = requests.get(f"{BASE_URL}/api/search-stocks?q=micro")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["results"]) > 0
        
        # Should have multiple results
        symbols = [r["symbol"] for r in data["results"]]
        # Should contain MU (Micron) among results
        assert "MU" in symbols or any("micro" in s.lower() for s in symbols)
    
    def test_search_results_have_required_fields(self):
        """Search results should have symbol, name, sector, exchange, type, industry fields"""
        response = requests.get(f"{BASE_URL}/api/search-stocks?q=apple")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["results"]) > 0
        
        for result in data["results"]:
            assert "symbol" in result
            assert "name" in result
            assert "exchange" in result
            assert "type" in result
            # sector and industry may be empty for some instruments
            assert "sector" in result
            assert "industry" in result
    
    def test_search_empty_query_returns_empty(self):
        """Empty query should return empty results"""
        response = requests.get(f"{BASE_URL}/api/search-stocks?q=")
        assert response.status_code == 200
        
        data = response.json()
        assert data["results"] == []


class TestNewsThumbnails:
    """Test news endpoints with thumbnail support"""
    
    def test_ticker_news_has_thumbnail_url_field(self):
        """GET /api/news/ticker/AAPL should return articles with thumbnail_url field"""
        response = requests.get(f"{BASE_URL}/api/news/ticker/AAPL")
        assert response.status_code == 200
        
        data = response.json()
        assert "articles" in data
        assert len(data["articles"]) > 0
        
        # All articles should have thumbnail_url field (may be empty string)
        for article in data["articles"]:
            assert "thumbnail_url" in article
            assert "title" in article
            assert "source_url" in article
    
    def test_ticker_news_some_have_thumbnails(self):
        """At least some yfinance articles should have actual thumbnail URLs"""
        response = requests.get(f"{BASE_URL}/api/news/ticker/AAPL")
        assert response.status_code == 200
        
        data = response.json()
        articles = data["articles"]
        
        # Check if at least one article has a non-empty thumbnail URL
        thumbnails = [a.get("thumbnail_url", "") for a in articles if a.get("thumbnail_url")]
        assert len(thumbnails) > 0, "Expected at least one article with thumbnail"
        
        # Verify thumbnail URL format
        for thumb in thumbnails[:3]:
            assert thumb.startswith("http"), f"Thumbnail URL should be HTTP: {thumb}"
    
    def test_news_feed_has_thumbnail_field(self):
        """GET /api/news/feed should return articles with thumbnail_url field"""
        response = requests.get(f"{BASE_URL}/api/news/feed?limit=10")
        assert response.status_code == 200
        
        data = response.json()
        assert "articles" in data
        
        # All articles should have thumbnail_url field
        for article in data["articles"]:
            assert "thumbnail_url" in article
    
    def test_ticker_news_article_structure(self):
        """Verify the full structure of ticker news articles"""
        response = requests.get(f"{BASE_URL}/api/news/ticker/TSLA")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["articles"]) > 0
        
        article = data["articles"][0]
        expected_fields = ["article_id", "title", "source", "source_url", "published_at", "thumbnail_url"]
        for field in expected_fields:
            assert field in article, f"Missing field: {field}"


class TestSearchEdgeCases:
    """Edge cases for the search functionality"""
    
    def test_search_by_partial_ticker(self):
        """Search by partial ticker symbol"""
        response = requests.get(f"{BASE_URL}/api/search-stocks?q=AAP")
        assert response.status_code == 200
        
        data = response.json()
        # Should return AAPL among results
        symbols = [r["symbol"] for r in data["results"]]
        assert "AAPL" in symbols
    
    def test_search_case_insensitive(self):
        """Search should work regardless of case"""
        response_lower = requests.get(f"{BASE_URL}/api/search-stocks?q=apple")
        response_upper = requests.get(f"{BASE_URL}/api/search-stocks?q=APPLE")
        
        assert response_lower.status_code == 200
        assert response_upper.status_code == 200
        
        # Both should return AAPL
        lower_symbols = [r["symbol"] for r in response_lower.json()["results"]]
        upper_symbols = [r["symbol"] for r in response_upper.json()["results"]]
        
        assert "AAPL" in lower_symbols
        assert "AAPL" in upper_symbols
    
    def test_search_returns_type_field(self):
        """Search results should show type (Equity, ETF, Fund, Futures)"""
        response = requests.get(f"{BASE_URL}/api/search-stocks?q=spy")
        assert response.status_code == 200
        
        data = response.json()
        # SPY is an ETF
        if data["results"]:
            # Check that type field exists
            assert all("type" in r for r in data["results"])


class TestSearchNavigation:
    """Test that search results can be used to navigate to stock pages"""
    
    def test_search_result_symbol_valid_for_stock_detail(self):
        """Search result symbols should work with the stock detail endpoint"""
        # First search
        search_response = requests.get(f"{BASE_URL}/api/search-stocks?q=apple")
        assert search_response.status_code == 200
        
        results = search_response.json()["results"]
        assert len(results) > 0
        
        symbol = results[0]["symbol"]
        
        # Then verify the symbol works with stock detail endpoint
        stock_response = requests.get(f"{BASE_URL}/api/market/stock/{symbol}/rich")
        assert stock_response.status_code == 200
        
        stock_data = stock_response.json()
        assert stock_data["symbol"] == symbol


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
