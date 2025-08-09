# WhatsApp AgriBot powered by LangGraph & Groq

This project implements a WhatsApp multi-agent assistant focused on Indian agriculture. It can handle text and voice messages, auto-detect language, translate as needed, call specialist tools (market prices, weather, disaster alerts, web scraping, search), and reply in text or synthesized speech over WhatsApp via WPPConnect.

---

## Key Features

- Text and voice support
  - Voice notes are transcribed with Groq Whisper
  - Replies can be sent as voice (TTS) or text
- Multi-language
  - Detects the user’s language and auto-translates to English for reasoning
  - Translates the final answer back to the original language
- Message aggregation
  - Buffers messages for a short period (WAIT_TIME) to combine bursts
- Multi-agent workflow (LangGraph)
  - Supervisor routes to specialists:
    - SoilCropAdvisor
    - MarketAnalyst
    - FinancialAdvisor
    - FinalAnswerAgent (synthesizes final reply)
- Tooling
  - Market prices via SerpAPI
  - Weather via OpenWeatherMap
  - Disaster alerts via NDMA Sachet
  - Web scraping (requests + BeautifulSoup)
  - Optional search: Tavily and DuckDuckGo
- WhatsApp integration via WPPConnect
- Simple health check endpoint

---

## Built With

- LangGraph (agent workflow)
- FastAPI (webhook/API)
- Groq (LLM + Whisper transcription)
- WPPConnect (WhatsApp transport)
- Requests, BeautifulSoup (tools)
- Optional: SerpAPI, OpenWeatherMap, Tavily
- TTS backend used in app/sarvam.py

---

## Project Structure

```text
.
├── app/
│   ├── agent.py                # Multi-agent graph (Supervisor, specialists, final answer)
│   ├── sarvam.py               # Language detection, translation, TTS helpers
│   ├── config/
│   │   ├── config.py           # Groq client and config helpers
│   │   └── logging.py          # Logging setup
│   ├── src/
│   │   └── wppconnect/
│   │       └── api.py          # WhatsApp send_message/send_voice wrappers
│   └── utils/
│       └── graph_utils.py      # Graph utilities
├── tools.py                    # Tool definitions (SerpAPI, weather, alerts, scraper, search)
├── main.py                     # FastAPI app + webhook handler and orchestration
├── assets/                     # Images/media
└── readme.md
```

---

## How It Works

- WPPConnect posts events to /webhook
- Only new user messages of type chat or ptt are processed
- For ptt (voice), audio base64 is transcribed using Groq Whisper
- Messages are aggregated for WAIT_TIME seconds per sender
- The text is language-detected and translated to English for the agent
- agentic_workflow runs (Supervisor -> Specialists -> FinalAnswerAgent)
- Final answer is translated back to the user’s original language
- Reply is sent over WhatsApp as text or TTS voice

---

## Get Started

### Prerequisites

- Python 3.11+
- Node.js (for WPPConnect server)

### Install Dependencies

- Create and activate a virtual environment
- `pip install -r requirements.txt`

### Set Up WPPConnect Server

1. Clone and install

   ```bash
   git clone https://github.com/wppconnect-team/wppconnect-server.git
   cd wppconnect-server
   npm install
   ```

2. Configure webhook in `src/config.ts`

   ```ts
   // src/config.ts
   export default {
     // ...other config
     webhook: {
       url: "http://localhost:8000/webhook",
     },
   };
   ```

3. Start server

   ```bash
   npm run dev
   ```

4. Generate token and start a session (via [Swagger UI](http://localhost:21465/api-docs))

   - Generate token and set in your `.env` (WPPCONNECT_TOKEN)
   - Start a session and scan the QR code with WhatsApp

### Environment Variables (.env)

```env
WPPCONNECT_BASE_URL=http://localhost:21465
WPPCONNECT_SESSION_NAME=YOUR_SESSION
WPPCONNECT_TOKEN=your_generated_token
WPPCONNECT_SECRET_KEY=optional_if_required
GROQ_API_KEY=your_groq_api_key
SERPAPI_API_KEY=optional_for_market_prices
OPENWEATHERMAP_API_KEY=optional_for_weather
TAVILY_API_KEY=optional_for_search
WAIT_TIME=2
```

### Run the API

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Health check: GET /health at <http://localhost:8000/health>

---

## Agents and Tools

- Supervisor: routes to the right specialist or directly to FinalAnswerAgent
- Specialists (share the same tool-execution node)
  - SoilCropAdvisor
  - MarketAnalyst
  - FinancialAdvisor
- FinalAnswerAgent: synthesizes the final user-facing message

Tools (tools.py)

- serpapi_market_price_tool: crop market prices (SerpAPI)
- weather_alert_tool: current weather (OpenWeatherMap)
- disaster_alert_tool: NDMA Sachet alerts
- web_scraper_tool: scrape site text content
- Optional: Tavily search, DuckDuckGo search

---

## Customization

- Routing and behavior: edit `app/agent.py`
- Add or modify tools: edit `tools.py`
- Language, translation, and TTS: edit `app/sarvam.py`
- Message aggregation window: WAIT_TIME in `.env`

---

## Troubleshooting

- No replies or 401 from WPPConnect
  - Check WPPCONNECT_BASE_URL, WPPCONNECT_SESSION_NAME, WPPCONNECT_TOKEN
- Voice transcription fails
  - Verify GROQ_API_KEY and network access
- Weather or market prices return errors
  - Ensure OPENWEATHERMAP_API_KEY or SERPAPI_API_KEY are set
- TTS not working
  - `app/sarvam.py` will fall back to text if TTS fails
- Webhook not called
  - Confirm WPPConnect `webhook.url` matches your API address

---

## License

MIT License