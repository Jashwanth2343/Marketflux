import logging
import asyncio
import yfinance as yf

try:
    import akshare as ak
except Exception:
    ak = None

logger = logging.getLogger(__name__)

class ProviderRouter:
    """
    Routes financial data requests to the best available provider.
    Production-ready logic for handling yfinance, AKShare, and fallbacks.
    """
    
    @staticmethod
    def get_provider_for_ticker(ticker: str) -> str:
        ticker = ticker.upper()
        # AKShare strengths: China (SS/SZ) and Hong Kong (HK)
        if ak is not None and any(ticker.endswith(suffix) for suffix in [".SS", ".SZ", ".HK"]):
            return "akshare"
        return "yfinance"

    @classmethod
    async def get_stock_quote(cls, ticker: str) -> dict:
        provider = cls.get_provider_for_ticker(ticker)
        
        if provider == "akshare":
            return await cls._get_akshare_quote(ticker)
        
        # Default to yfinance with AKShare fallback
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            if not info or "currentPrice" not in info and "regularMarketPrice" not in info:
                raise ValueError(f"yfinance failed for {ticker}")
            
            return {
                "ticker": ticker,
                "price": info.get("currentPrice", info.get("regularMarketPrice")),
                "provider": "yfinance"
            }
        except Exception as e:
            logger.warning(f"yfinance failed for {ticker}, trying AKShare fallback: {e}")
            return await cls._get_akshare_quote(ticker)

    @staticmethod
    async def _get_akshare_quote(ticker: str) -> dict:
        if ak is None:
            return {"error": "AKShare is not installed", "ticker": ticker}
        try:
            # Simple spot fetching
            if ticker.endswith(".HK"):
                df = await asyncio.to_thread(ak.stock_hk_spot_em)
                symbol = ticker.replace(".HK", "")
            else:
                df = await asyncio.to_thread(ak.stock_zh_a_spot_em)
                symbol = ticker.split(".")[0]
            
            row = df[df["代码"] == symbol]
            if row.empty:
                return {"error": f"Ticker {ticker} not found in AKShare", "ticker": ticker}
            
            return {
                "ticker": ticker,
                "price": row.iloc[0]["最新价"],
                "provider": "akshare"
            }
        except Exception as e:
            logger.error(f"AKShare quote fetch failed for {ticker}: {e}")
            return {"error": str(e), "ticker": ticker}
