import os
import requests
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field
from langchain.tools import tool
from langchain_community.utilities import SerpAPIWrapper

# --- Tool Definitions ---
print("🛠️  Initializing tools...")

# 1. Tavily Search (Primary General Search)
try:
    from langchain_community.tools import TavilySearchResults
    tavily_tool = TavilySearchResults(max_results=5)
    print("✅ Tavily search tool initialized.")
except Exception as e:
    print(f"⚠️  Warning: Tavily search tool failed to initialize: {e}")
    tavily_tool = None

# 2. DuckDuckGo Search (Fallback)
try:
    from langchain_community.tools import DuckDuckGoSearchRun
    duckduckgo_tool = DuckDuckGoSearchRun()
    print("✅ DuckDuckGo search tool initialized.")
except Exception as e:
    print(f"⚠️  Warning: DuckDuckGo search tool failed to initialize: {e}")
    duckduckgo_tool = None

# 3. SerpApi (Specialized for Market Prices)
try:
    serpapi_search = SerpAPIWrapper(serpapi_api_key=os.getenv("SERPAPI_API_KEY"))
    print("✅ SerpAPI wrapper initialized.")
except Exception as e:
    print(f"⚠️  Warning: SerpAPI could not be initialized: {e}")
    serpapi_search = None

class MarketPriceToolInput(BaseModel):
    crop_name: str = Field(description="The name of the agricultural crop, e.g., 'potato', 'tomato'.")
    location: str = Field(description="The city or mandi name for the price query, e.g., 'Lucknow'.")

@tool("serpapi_market_price_tool", args_schema=MarketPriceToolInput)
def serpapi_market_price_tool(crop_name: str, location: str) -> str:
    """Uses SerpApi to get accurate, real-time market prices (mandi rates) for a specific crop in a given location."""
    if not serpapi_search:
        return "Error: SerpAPI is not configured. Please set the SERPAPI_API_KEY."
    query = f"today's {crop_name} price in {location} mandi"
    return serpapi_search.run(query)

@tool("soil_data_retriever")
def soil_data_retriever(query: str) -> str:
    """Placeholder for soil data retrieval. The RAG system is not implemented in this version."""
    return "Soil data information is currently unavailable. I can help with market prices, weather, and government schemes."

class WeatherToolInput(BaseModel):
    location: str = Field(description="The city and state for which to get the weather forecast, e.g., 'Bhubaneswar, Odisha'.")

@tool("weather_alert_tool", args_schema=WeatherToolInput)
def weather_alert_tool(location: str) -> str:
    """Fetches the current weather forecast for a specified location."""
    api_key = os.getenv("OPENWEATHERMAP_API_KEY")
    if not api_key:
        return "Error: Weather forecast is unavailable. OPENWEATHERMAP_API_KEY is not set."
    base_url = "http://api.openweathermap.org/data/2.5/weather"
    params = {"q": location, "appid": api_key, "units": "metric"}
    try:
        response = requests.get(base_url, params=params, timeout=5)
        response.raise_for_status()
        weather_data = response.json()
        forecast = (
            f"Weather forecast for {weather_data['name']}:\n"
            f"- Condition: {weather_data['weather'][0]['description']}\n"
            f"- Temperature: {weather_data['main']['temp']}°C (feels like {weather_data['main']['feels_like']}°C)\n"
            f"- Humidity: {weather_data['main']['humidity']}%\n"
            f"- Wind Speed: {weather_data['wind']['speed']} m/s\n"
        )
        return forecast
    except requests.exceptions.RequestException as e:
        return f"Error fetching weather data for {location}: {e}"

class DisasterAlertToolInput(BaseModel):
    location: str = Field(description="The location for which to fetch disaster alerts, e.g., 'Prayagraj, Uttar Pradesh'.")

@tool("disaster_alert_tool", args_schema=DisasterAlertToolInput)
def disaster_alert_tool(location: str) -> str:
    """Fetches natural disaster alerts (floods, cyclones, etc.) for a specific location from NDMA."""
    url = "https://sachet.ndma.gov.in/cap_public_website/FetchAddressWiseAlerts"
    headers = {'Accept': 'application/json', 'Content-Type': 'application/x-www-form-urlencoded'}
    data = {'address': location, 'radius': 50}
    try:
        response = requests.post(url, data=data, headers=headers, timeout=15)
        response.raise_for_status()
        alert_data = response.json()
        if isinstance(alert_data, list) and len(alert_data) > 0:
            alerts_summary = f"🚨 DISASTER ALERTS FOR {location.upper()}:\n\n"
            for alert in alert_data[:3]: # Limit to 3
                alerts_summary += f"• Event: {alert.get('event', 'N/A')}\n"
                alerts_summary += f"• Severity: {alert.get('severity', 'N/A')}\n"
                alerts_summary += f"• Headline: {alert.get('headline', 'N/A')}\n\n"
            return alerts_summary
        else:
            return f"✅ No active disaster alerts found for {location}."
    except Exception as e:
        return f"❌ Unable to fetch disaster alerts for {location}: {e}."

class ScraperToolInput(BaseModel):
    url: str = Field(description="The URL of the webpage to scrape.")

@tool("web_scraper_tool", args_schema=ScraperToolInput)
def web_scraper_tool(url: str) -> str:
    """Scrapes the text content of a given URL."""
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'lxml')
        return ' '.join(p.get_text() for p in soup.find_all('p'))[:4000]
    except Exception as e:
        return f"Error scraping URL {url}: {e}"

# --- Compile All Tools ---
all_tools = [serpapi_market_price_tool, soil_data_retriever, weather_alert_tool, disaster_alert_tool, web_scraper_tool]
if tavily_tool: all_tools.append(tavily_tool)
if duckduckgo_tool: all_tools.append(duckduckgo_tool)

print("✅ All tools compiled.")