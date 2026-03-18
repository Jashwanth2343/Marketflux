import os
import httpx
import logging
import asyncio
import yfinance as yf
import diskcache

logger = logging.getLogger(__name__)

# Caching setup
_CACHE_BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache")
os.makedirs(_CACHE_BASE, mode=0o700, exist_ok=True)
_react_cache = diskcache.Cache(os.path.join(_CACHE_BASE, "react_cache"))

def _cache_get(key: str):
    try:
        return _react_cache.get(key)
    except Exception:
        return None

def _cache_set(key: str, data, expire: int):
    try:
        _react_cache.set(key, data, expire=expire)
    except Exception:
        pass

def format_human_readable(value, is_currency=True) -> str:
    """Format numbers to human-readable strings like $394.3B."""
    if value is None or str(value).lower() in ("nan", "nat", "none"):
        return "N/A"
    try:
        val = float(value)
        prefix = "$" if is_currency else ""
        abs_val = abs(val)
        
        if abs_val >= 1e12:
            return f"{prefix}{val / 1e12:.2f}T"
        elif abs_val >= 1e9:
            return f"{prefix}{val / 1e9:.2f}B"
        elif abs_val >= 1e6:
            return f"{prefix}{val / 1e6:.2f}M"
        elif abs_val >= 1e3:
            return f"{prefix}{val / 1e3:.2f}K"
        else:
            return f"{prefix}{val:.2f}"
    except Exception:
        return "N/A"

def get_company_profile(ticker: str) -> dict:
    """
    Use this to answer questions about company leadership (CEO, CFO, board), 
    headquarters location, founding date, number of employees, business description, 
    and company website.
    """
    try:
        stock = yf.Ticker(ticker.upper())
        info = stock.info
        
        if not info:
             return {"error": f"Company profile not available for {ticker.upper()}", "ticker": ticker.upper()}
             
        result = {
             "ticker": ticker.upper(),
             "Company_Name": info.get("longName", "N/A"),
             "Sector": info.get("sector", "N/A"),
             "Industry": info.get("industry", "N/A"),
             "Number_Of_Employees": info.get("fullTimeEmployees", "N/A"),
             "Headquarters": f"{info.get('city', '')}, {info.get('state', '')}, {info.get('country', '')}".strip(" ,"),
             "Website": info.get("website", "N/A"),
             "Business_Summary": info.get("longBusinessSummary", "N/A"),
        }
        
        officers = info.get("companyOfficers", [])
        if officers:
            execs = []
            for o in officers[:5]:
                execs.append({
                     "Name": o.get("name"),
                     "Title": o.get("title")
                })
            result["Key_Executives"] = execs
            
        return result
    except Exception as e:
        logger.error(f"Error in get_company_profile: {e}")
        return {"error": f"Company profile not available for {ticker}", "ticker": ticker.upper()}

def get_stock_quote(ticker: str) -> dict:
    """Gets current price, change, day high/low, 52-week high/low, and trading volume."""
    try:
        stock = yf.Ticker(ticker.upper())
        info = stock.info
        if not info:
            return {"error": f"Quote data not available for {ticker.upper()}", "ticker": ticker.upper()}
            
        return {
            "ticker": ticker.upper(),
            "Current_Price": format_human_readable(info.get("currentPrice", info.get("regularMarketPrice"))),
            "Day_High": format_human_readable(info.get("dayHigh")),
            "Day_Low": format_human_readable(info.get("dayLow")),
            "Fifty_Two_Week_High": format_human_readable(info.get("fiftyTwoWeekHigh")),
            "Fifty_Two_Week_Low": format_human_readable(info.get("fiftyTwoWeekLow")),
            "Volume": format_human_readable(info.get("volume"), is_currency=False),
        }
    except Exception as e:
        logger.error(f"Error in get_stock_quote: {e}")
        return {"error": f"Quote data not available for {ticker}", "ticker": ticker.upper()}

def get_fundamentals(ticker: str) -> dict:
    """Gets key financial metrics: P/E, Forward P/E, EPS, Market Cap, Dividend Yield, margins, ROE."""
    try:
        stock = yf.Ticker(ticker.upper())
        info = stock.info
        if not info:
             return {"error": f"Fundamental metrics not available for {ticker.upper()}", "ticker": ticker.upper()}
             
        div_yield = info.get("dividendYield")
        div_yield_str = f"{div_yield * 100:.2f}%" if div_yield else "N/A"
        
        return {
             "ticker": ticker.upper(),
             "Market_Cap": format_human_readable(info.get("marketCap")),
             "PE_Ratio": format_human_readable(info.get("trailingPE"), is_currency=False),
             "Forward_PE": format_human_readable(info.get("forwardPE"), is_currency=False),
             "EPS": format_human_readable(info.get("trailingEps")),
             "Dividend_Yield": div_yield_str,
             "Profit_Margin": f"{info.get('profitMargins', 0) * 100:.2f}%" if info.get('profitMargins') else "N/A",
             "Operating_Margin": f"{info.get('operatingMargins', 0) * 100:.2f}%" if info.get('operatingMargins') else "N/A",
             "Return_On_Equity": f"{info.get('returnOnEquity', 0) * 100:.2f}%" if info.get('returnOnEquity') else "N/A",
             "Beta": format_human_readable(info.get("beta"), is_currency=False),
        }
    except Exception as e:
        logger.error(f"Error in get_fundamentals: {e}")
        return {"error": f"Fundamental metrics not available for {ticker}", "ticker": ticker.upper()}

def get_financial_statements(ticker: str) -> dict:
    """
    Get deep fundamentals (Income Statement, Balance Sheet, Cash Flow) for the last 4 quarters.
    """
    try:
        stock = yf.Ticker(ticker.upper())
        
        # We need the quarterly financials
        inc_stmt = stock.quarterly_income_stmt
        bal_stmt = stock.quarterly_balance_sheet
        cf_stmt = stock.quarterly_cashflow
        
        if inc_stmt is None or inc_stmt.empty:
            return {"error": f"Data not available for {ticker.upper()}", "ticker": ticker.upper()}
            
        result = {"ticker": ticker.upper()}
        
        # 1. Income Statement (last 4 quarters)
        inc_res = []
        for col in list(inc_stmt.columns)[:4]:
            date_str = col.strftime("%Y-%m-%d")
            col_data = inc_stmt[col]
            inc_res.append({
                "Quarter": date_str,
                "Total Revenue": format_human_readable(col_data.get("Total Revenue")),
                "Gross Profit": format_human_readable(col_data.get("Gross Profit")),
                "Operating Income": format_human_readable(col_data.get("Operating Income")),
                "Net Income": format_human_readable(col_data.get("Net Income")),
                "EBITDA": format_human_readable(col_data.get("EBITDA")) if "EBITDA" in col_data else "N/A"
            })
        result["Income_Statement"] = inc_res
        
        # 2. Balance Sheet (most recent)
        if not bal_stmt.empty:
            recent_col = list(bal_stmt.columns)[0]
            col_data = bal_stmt[recent_col]
            result["Balance_Sheet_Latest"] = {
                "Quarter": recent_col.strftime("%Y-%m-%d"),
                "Total Assets": format_human_readable(col_data.get("Total Assets")),
                "Total Debt": format_human_readable(col_data.get("Total Debt")),
                "Cash And Cash Equivalents": format_human_readable(col_data.get("Cash And Cash Equivalents")),
                "Stockholders Equity": format_human_readable(col_data.get("Stockholders Equity"))
            }
            
        # 3. Cash Flow (last 4 quarters)
        cf_res = []
        if not cf_stmt.empty:
            for col in list(cf_stmt.columns)[:4]:
                date_str = col.strftime("%Y-%m-%d")
                col_data = cf_stmt[col]
                
                op_cf = col_data.get("Operating Cash Flow", 0)
                cap_ex = col_data.get("Capital Expenditure", 0) # yfinance name for CapEx typically
                # handle if capex is positive or negative
                if str(cap_ex) != "nan" and str(op_cf) != "nan":
                    fcf = float(op_cf) - abs(float(cap_ex))
                else:
                    fcf = None
                    
                cf_res.append({
                    "Quarter": date_str,
                    "Operating Cash Flow": format_human_readable(col_data.get("Operating Cash Flow")),
                    "Capital Expenditures": format_human_readable(col_data.get("Capital Expenditure")),
                    "Free Cash Flow": format_human_readable(fcf)
                })
        result["Cash_Flow"] = cf_res
        
        return result
    except Exception as e:
        logger.error(f"Error in get_financial_statements: {e}")
        return {"error": f"Data not available for {ticker}", "ticker": ticker.upper()}

def get_insider_and_analyst_data(ticker: str) -> dict:
    """
    Get analyst price targets, ratings, and recent insider transactions.
    """
    try:
        stock = yf.Ticker(ticker.upper())
        info = stock.info
        
        result = {
            "ticker": ticker.upper(),
            "Analyst_Consensus": {
                "Recommendation": info.get("recommendationKey", "N/A"),
                "Target_Mean_Price": format_human_readable(info.get("targetMeanPrice")),
                "Target_High_Price": format_human_readable(info.get("targetHighPrice")),
                "Target_Low_Price": format_human_readable(info.get("targetLowPrice")),
                "Number_Of_Analysts": info.get("numberOfAnalystOpinions", "N/A")
            }
        }
        
        # Insider transactions
        insider = stock.insider_transactions
        if insider is not None and not insider.empty:
            # Get last 5
            txns = []
            for _, row in insider.head(5).iterrows():
                txns.append({
                    "Date": row.get("Start Date", row.name).strftime("%Y-%m-%d") if hasattr(row.get("Start Date", row.name), "strftime") else str(row.get("Start Date")),
                    "Insider": str(row.get("Insider Purchases", row.get("ReporterName", "Unknown"))),
                    "Shares": format_human_readable(row.get("Shares", 0), is_currency=False),
                    "Value": format_human_readable(row.get("Value", 0))
                })
            result["Insider_Transactions_Recent"] = txns
        else:
            result["Insider_Transactions_Recent"] = "No recent insider activity found."
            
        return result
    except Exception as e:
        logger.error(f"Error in get_insider_and_analyst_data: {e}")
        return {"error": f"Data not available for {ticker}", "ticker": ticker.upper()}

async def get_sec_filings(ticker: str) -> dict:
    """
    Gets latest 10-K and 10-Q links from SEC EDGAR. 
    Requires TICKER -> CIK mapping and enforces SEC fair use policy.
    """
    cache_key = f"react_edgar:{ticker.upper()}"
    cached = _cache_get(cache_key)
    if cached:
        return cached
        
    try:
        headers = {"User-Agent": "MarketFlux jashwanth2343@gmail.com"}
        
        # Map ticker to CIK
        async with httpx.AsyncClient() as client:
            cik_resp = await client.get("https://www.sec.gov/files/company_tickers.json", headers=headers)
            cik_data = cik_resp.json()
            
            cik = None
            for key, val in cik_data.items():
                if val.get("ticker", "") == ticker.upper():
                    cik = str(val.get("cik_str")).zfill(10)
                    break
                    
            if not cik:
                return {"error": f"SEC filings not found for {ticker.upper()}"}
            
            await asyncio.sleep(0.1)  # 0.1s delay to respect SEC rate limit
            
            # Fetch submissions
            sub_url = f"https://data.sec.gov/submissions/CIK{cik}.json"
            sub_resp = await client.get(sub_url, headers=headers)
            
            if sub_resp.status_code != 200:
                return {"error": f"SEC EDGAR API responded with {sub_resp.status_code} for {ticker.upper()}"}
                
            sub_json = sub_resp.json()
            recent_filings = sub_json.get("filings", {}).get("recent", {})
            
            filings_list = []
            if recent_filings:
                forms = recent_filings.get("form", [])
                acc_nums = recent_filings.get("accessionNumber", [])
                primary_docs = recent_filings.get("primaryDocument", [])
                dates = recent_filings.get("filingDate", [])
                
                # Extract up to 3 latest 10-Q / 10-K
                count = 0
                for i, form in enumerate(forms):
                    if form in ("10-K", "10-Q", "8-K"):
                        # SEC EDGAR URL format
                        a_num = acc_nums[i].replace("-", "")
                        doc = primary_docs[i]
                        link = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{a_num}/{doc}"
                        
                        filings_list.append({
                            "Form": form,
                            "Filing_Date": dates[i],
                            "Link": link
                        })
                        count += 1
                        if count >= 3:
                            break
                            
            result = {"ticker": ticker.upper(), "Recent_SEC_Filings": filings_list}
            _cache_set(cache_key, result, 3600) # 1 hour cache
            return result
            
    except Exception as e:
        logger.error(f"Error in get_sec_filings: {e}")
        return {"error": f"SEC filings not found for {ticker.upper()}"}

async def get_earnings_history(ticker: str) -> dict:
    """
    Get earnings surprise history using Alpha Vantage.
    Fallback to yfinance earnings dates if API limit is hit.
    """
    cache_key = f"react_earnings:{ticker.upper()}"
    cached = _cache_get(cache_key)
    if cached:
        return cached
        
    try:
        av_key = os.environ.get("ALPHA_VANTAGE_KEY", "")
        if av_key:
            async with httpx.AsyncClient() as client:
                url = f"https://www.alphavantage.co/query?function=EARNINGS&symbol={ticker.upper()}&apikey={av_key}"
                resp = await client.get(url)
                data = resp.json()
                
                # Check for rate limit
                if "Information" in data and "limit" in str(data["Information"]):
                    raise Exception("Alpha Vantage Rate Limit")
                    
                quarterly = data.get("quarterlyEarnings", [])
                if quarterly:
                    res_list = []
                    for q in quarterly[:4]:
                        res_list.append({
                            "Quarter_Ending": q.get("fiscalDateEnding"),
                            "Reported_Date": q.get("reportedDate"),
                            "Reported_EPS": q.get("reportedEPS"),
                            "Estimated_EPS": q.get("estimatedEPS"),
                            "Surprise": q.get("surprise"),
                            "Surprise_Percent": q.get("surprisePercentage")
                        })
                    res = {"ticker": ticker.upper(), "Earnings_Surprise_History": res_list}
                    _cache_set(cache_key, res, 86400) # 24h cache
                    return res
                    
        # Fallback to yfinance upcoming dates
        stock = yf.Ticker(ticker.upper())
        dates = stock.earnings_dates
        if dates is not None and not dates.empty:
            dates = dates.head(4).reset_index()
            fallback = []
            for _, row in dates.iterrows():
                dt = str(row.get("Earnings Date"))
                fallback.append({
                    "Earnings_Date": dt,
                    "EPS_Estimate": format_human_readable(row.get("EPS Estimate")),
                    "Reported_EPS": format_human_readable(row.get("Reported EPS"))
                })
            res = {"ticker": ticker.upper(), "Upcoming_Earnings": fallback}
            _cache_set(cache_key, res, 86400)
            return res
            
        return {"error": f"Data not available for {ticker.upper()}", "ticker": ticker.upper()}
    except Exception as e:
        logger.warning(f"Error in get_earnings_history (falling back to yfinance): {e}")
        try:
            stock = yf.Ticker(ticker.upper())
            dates = stock.earnings_dates
            if dates is not None and not dates.empty:
                dates = dates.head(4).reset_index()
                fallback = []
                for _, row in dates.iterrows():
                    dt = str(row.get("Earnings Date"))
                    fallback.append({
                        "Earnings_Date": dt,
                        "EPS_Estimate": format_human_readable(row.get("EPS Estimate")),
                        "Reported_EPS": format_human_readable(row.get("Reported EPS"))
                    })
                res = {"ticker": ticker.upper(), "Upcoming_Earnings": fallback}
                _cache_set(cache_key, res, 86400)
                return res
        except Exception:
            pass
        return {"error": f"Data not available for {ticker.upper()}", "ticker": ticker.upper()}

async def get_macro_context() -> dict:
    """Gets DFF (Fed Funds), CPIAUCSL (CPI), and UNRATE (Unemployment) from FRED."""
    cache_key = "react_macro"
    cached = _cache_get(cache_key)
    if cached:
        return cached
        
    try:
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json"
        }
        
        async with httpx.AsyncClient() as client:
            # We scrape the public FRED API for series info to avoid API key requirement
            # The undocumented search endpoint:
            # We just fetch the top latest observation via HTML parsing or alternative
            # Actually, without key, we can pull CSV.
            res = {}
            for series in ["DFF", "CPIAUCSL", "UNRATE"]:
                csv_url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}"
                resp = await client.get(csv_url, headers=headers)
                if resp.status_code == 200:
                    lines = resp.text.strip().split("\n")
                    if len(lines) > 1:
                        last_line = lines[-1].split(",")
                        res[series] = {"Date": last_line[0], "Value": last_line[1]}
            if res:
                _cache_set(cache_key, res, 86400)
                return res
            else:
                return {"error": "Macro data temporarily unavailable"}
    except Exception as e:
        logger.error(f"Error in get_macro_context: {e}")
        return {"error": "Macro data temporarily unavailable"}

async def search_web(query: str) -> dict:
    """
    DuckDuckGo search fallback.
    """
    try:
        from duckduckgo_search import DDGS
        def _search():
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=3))
            return results
        results = await asyncio.to_thread(_search)
        
        formatted = []
        for r in results:
            formatted.append({
                "Title": r.get("title", ""),
                "Snippet": r.get("body", ""),
                "Link": r.get("href", ""),
            })
        return {"Query": query, "Web_Results": formatted}
    except Exception as e:
        logger.error(f"Error in search_web: {e}")
        return {"error": f"Search failed for query '{query}'"}
