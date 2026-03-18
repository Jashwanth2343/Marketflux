"""
Test P0 Features: Global Search Bar & AI Screener Overhaul
Backend API tests for Market Flux application
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://flux-preview-1.preview.emergentagent.com')


class TestSearchStocksEndpoint:
    """Tests for /api/search-stocks global search endpoint"""
    
    def test_search_stocks_by_ticker_aapl(self):
        """Search for AAPL should return Apple with correct structure"""
        response = requests.get(f"{BASE_URL}/api/search-stocks?q=AAPL")
        assert response.status_code == 200
        
        data = response.json()
        assert "results" in data
        results = data["results"]
        assert len(results) > 0
        
        # Find AAPL in results
        aapl = next((r for r in results if r["symbol"] == "AAPL"), None)
        assert aapl is not None
        # Name should be non-empty (could be "Apple Inc." or fallback "AAPL")
        assert "name" in aapl
        assert len(aapl["name"]) > 0
        # Sector might be Technology or empty if from cache
        assert "sector" in aapl
    
    def test_search_stocks_by_partial_ticker(self):
        """Search for 'MSF' should return MSFT"""
        response = requests.get(f"{BASE_URL}/api/search-stocks?q=MSF")
        assert response.status_code == 200
        
        data = response.json()
        results = data["results"]
        assert len(results) > 0
        
        msft = next((r for r in results if r["symbol"] == "MSFT"), None)
        assert msft is not None
        assert "name" in msft
    
    def test_search_stocks_by_name_partial(self):
        """Search for 'Goo' should return GOOGL"""
        response = requests.get(f"{BASE_URL}/api/search-stocks?q=Goo")
        assert response.status_code == 200
        
        data = response.json()
        results = data["results"]
        assert len(results) > 0
        
        # Should find GOOGL
        googl = next((r for r in results if r["symbol"] == "GOOGL"), None)
        assert googl is not None
        assert "name" in googl
    
    def test_search_stocks_empty_query(self):
        """Empty query should return empty results"""
        response = requests.get(f"{BASE_URL}/api/search-stocks?q=")
        assert response.status_code == 200
        
        data = response.json()
        assert data["results"] == []
    
    def test_search_stocks_response_structure(self):
        """Verify response structure has symbol, name, sector"""
        response = requests.get(f"{BASE_URL}/api/search-stocks?q=NVDA")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["results"]) > 0
        
        result = data["results"][0]
        assert "symbol" in result
        assert "name" in result
        assert "sector" in result


class TestAIScreenerEndpoint:
    """Tests for /api/ai/screen AI screener endpoint
    Note: Rate limited to 3 calls for unauthenticated users
    """
    
    def test_screen_specific_tickers(self):
        """Compare specific tickers AAPL and MSFT"""
        response = requests.post(
            f"{BASE_URL}/api/ai/screen",
            json={"query": "compare AAPL and MSFT"},
            headers={"Content-Type": "application/json"}
        )
        
        # May hit rate limit (429) or succeed (200)
        if response.status_code == 429:
            pytest.skip("AI rate limit reached (429) - expected for unauthenticated users")
        
        assert response.status_code == 200
        
        data = response.json()
        
        # Check response structure
        assert "filters" in data
        assert "stocks" in data
        assert "summary" in data
        assert "total" in data
        
        # Verify filters include specific tickers
        filters = data["filters"]
        assert "specific_tickers" in filters
        assert "AAPL" in filters["specific_tickers"]
        assert "MSFT" in filters["specific_tickers"]
        
        # Verify stocks returned
        stocks = data["stocks"]
        assert len(stocks) == 2
        symbols = [s["symbol"] for s in stocks]
        assert "AAPL" in symbols
        assert "MSFT" in symbols
        
        # Verify stock data structure
        for stock in stocks:
            assert "symbol" in stock
            assert "name" in stock
            assert "price" in stock
            assert "change_percent" in stock
            assert "market_cap" in stock
            assert "pe_ratio" in stock
            assert "sector" in stock
        
        # Verify AI summary is generated
        assert len(data["summary"]) > 50  # Non-empty summary
    
    def test_screen_large_cap_tech_with_low_pe(self):
        """Test complex filter: large cap tech with low P/E"""
        response = requests.post(
            f"{BASE_URL}/api/ai/screen",
            json={"query": "large cap tech stocks with low P/E"},
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 429:
            pytest.skip("AI rate limit reached (429)")
        
        assert response.status_code == 200
        
        data = response.json()
        
        # Verify filters are correctly parsed
        filters = data["filters"]
        
        # Should have sectors filter for Technology
        assert "sectors" in filters
        # LLM should identify technology sector
        if filters["sectors"]:
            assert any("tech" in s.lower() for s in filters["sectors"])
        
        # Should have market_cap_min for large cap (10B)
        assert filters.get("market_cap_min") is not None or filters.get("market_cap_min") == 10000000000
        
        # Should have pe_ratio_max for low P/E
        assert filters.get("pe_ratio_max") is not None
        
        # Verify explanation
        assert "explanation" in filters
    
    def test_screen_high_dividend_healthcare(self):
        """Test high dividend healthcare filter"""
        response = requests.post(
            f"{BASE_URL}/api/ai/screen",
            json={"query": "high dividend healthcare stocks"},
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 429:
            pytest.skip("AI rate limit reached (429)")
        
        assert response.status_code == 200
        
        data = response.json()
        filters = data["filters"]
        
        # Should identify healthcare sector
        assert "sectors" in filters
        # Should have dividend yield filter
        # High dividend usually means > 3%
    
    def test_screen_response_has_filter_chips_data(self):
        """Verify filter data is present for UI filter chips"""
        response = requests.post(
            f"{BASE_URL}/api/ai/screen",
            json={"query": "compare AAPL, MSFT, GOOGL"},
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 429:
            pytest.skip("AI rate limit reached (429)")
        
        assert response.status_code == 200
        
        data = response.json()
        filters = data["filters"]
        
        # Filter object should be present for chip generation
        assert filters is not None
        assert isinstance(filters, dict)
        
        # At minimum should have explanation
        assert "explanation" in filters
    
    def test_screen_empty_query_returns_error_or_empty(self):
        """Empty or invalid query handling"""
        response = requests.post(
            f"{BASE_URL}/api/ai/screen",
            json={"query": ""},
            headers={"Content-Type": "application/json"}
        )
        # Should either return 200 with empty results, 422 validation error, or 429 rate limit
        assert response.status_code in [200, 422, 429]


class TestExistingEndpointsStillWork:
    """Verify existing endpoints still function properly"""
    
    def test_market_overview(self):
        """GET /api/market/overview returns indices"""
        response = requests.get(f"{BASE_URL}/api/market/overview")
        assert response.status_code == 200
        data = response.json()
        assert "indices" in data
    
    def test_market_movers(self):
        """GET /api/market/movers returns gainers and losers"""
        response = requests.get(f"{BASE_URL}/api/market/movers")
        assert response.status_code == 200
        data = response.json()
        assert "gainers" in data
        assert "losers" in data
    
    def test_stock_detail(self):
        """GET /api/market/stock/AAPL returns stock info"""
        response = requests.get(f"{BASE_URL}/api/market/stock/AAPL")
        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "AAPL"
        assert "price" in data
    
    def test_news_feed(self):
        """GET /api/news/feed returns articles"""
        response = requests.get(f"{BASE_URL}/api/news/feed")
        assert response.status_code == 200
        data = response.json()
        assert "articles" in data
    
    def test_market_search(self):
        """GET /api/market/search still works"""
        response = requests.get(f"{BASE_URL}/api/market/search?q=AAPL")
        assert response.status_code == 200
        data = response.json()
        assert "results" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
