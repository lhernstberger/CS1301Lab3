import streamlit as st
import requests
from datetime import datetime, timedelta
import time # Import for exponential backoff (good practice for API calls)

st.set_page_config(page_title="Weather Predictor", page_icon="🌤️")
st.title("Long-Range Weather Predictor")
st.write("Predict weather up to 1 year in the future using historical data and AI!")

# --- Robust Secret Handling ---
if "GEMINI_API_KEY" not in st.secrets:
    st.error("🚨 Please add `GEMINI_API_KEY` to your Streamlit secrets file (secrets.toml)!")
    st.stop()
else:
    API_KEY = st.secrets["GEMINI_API_KEY"]

# User Inputs
city = st.text_input("Enter a city name:", "Atlanta")
days_ahead = st.slider("Days in the future:", 1, 365, 30)
units = st.radio("Temperature units:", ["Fahrenheit", "Celsius"])

if st.button("Predict Weather"):
    # 1. Geocoding
    st.info(f"1/3: Looking up coordinates for {city}...")
    try:
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={city}"
        geo_response = requests.get(geo_url, timeout=5)
        geo_response.raise_for_status() 
        geo_data = geo_response.json()
        
        if not geo_data.get("results"):
            st.error("City not found! Try a different name.")
            st.stop()
            
        lat = geo_data["results"][0]["latitude"]
        lon = geo_data["results"][0]["longitude"]
        city_name = geo_data["results"][0]["name"]
    except requests.exceptions.RequestException as e:
        st.error(f"Error connecting to geocoding service: {e}")
        st.stop()
    except Exception as e:
        st.error(f"An unexpected error occurred during geocoding: {e}")
        st.stop()

    # 2. Historical Data Retrieval
    # REDUCED WINDOW FROM 20 YEARS TO 5 YEARS FOR RELIABILITY
    HISTORICAL_YEARS = 5 
    st.info(f"2/3: Getting {HISTORICAL_YEARS} years of historical data for {city_name} (Lat: {lat:.2f}, Lon: {lon:.2f})...")
    
    end_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=HISTORICAL_YEARS*365)).strftime("%Y-%m-%d")
    unit_param = "fahrenheit" if units == "Fahrenheit" else "celsius"
    
    weather_url = (
        f"https://archive-api.open-meteo.com/v1/archive?"
        f"latitude={lat}&longitude={lon}&start_date={start_date}&end_date={end_date}"
        f"&daily=temperature_2m_mean,temperature_2m_max,temperature_2m_min"
        f"&temperature_unit={unit_param}"
    )

    try:
        weather_response = requests.get(weather_url, timeout=20) # Increased timeout for large request
        weather_response.raise_for_status()
        weather_data = weather_response.json()
        
        # Check for API-specific error flag, which often omits the 'daily' key
        if weather_data.get("error") is True:
            reason = weather_data.get("reason", "Unknown API error.")
            st.error(f"Weather API returned an error for this request. Reason: {reason}")
            st.stop()

        # THIS IS THE ORIGINAL CHECK, now much less likely to trigger
        if "daily" not in weather_data:
            st.error("Couldn't get weather data. The API returned an incomplete response. Try a different city or a shorter historical range.")
            st.stop()
            
        mean_temps = weather_data["daily"]["temperature_2m_mean"]
        max_temps = weather_data["daily"]["temperature_2m_max"]
        min_temps = weather_data["daily"]["temperature_2m_min"]
        
        # Calculate statistics across the entire 5-year period
        avg_temp = sum(mean_temps) / len(mean_temps)
        min_temp = min(min_temps)
        max_temp = max(max_temps)
        
        unit_symbol = "°F" if units == "Fahrenheit" else "°C"
        
        st.success("Historical data collected!")
        st.markdown(f"**Location:** {city_name}")
        st.markdown(f"**Average Temp ({HISTORICAL_YEARS} yrs):** `{avg_temp:.1f}{unit_symbol}`")
        st.markdown(f"**Lowest Recorded Temp:** `{min_temp:.1f}{unit_symbol}`")
        st.markdown(f"**Highest Recorded Temp:** `{max_temp:.1f}{unit_symbol}`")
    
    except requests.exceptions.RequestException as e:
        st.error(f"Error connecting to weather service: {e}")
        st.stop()
    except Exception as e:
        st.error(f"An unexpected error occurred during data processing: {e}")
        st.stop()

    # 3. AI Prediction using Gemini API
    st.info("3/3: Asking AI to predict the weather...")
    
    target_date = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
    
    # Contextual prompt for the model
    prompt = f"""You are an expert long-range weather predictor.
Based on the following {HISTORICAL_YEARS} years of historical weather data for {city_name}, predict the expected *mean daily temperature* for the specific future date: {target_date}.

Historical Data ({HISTORICAL_YEARS} years):
- Overall Average Temperature: {avg_temp:.1f}{unit_symbol}
- Coldest Recorded Temperature: {min_temp:.1f}{unit_symbol}
- Hottest Recorded Temperature: {max_temp:.1f}{unit_symbol}

Consider the month and season of the target date ({target_date}) relative to the historical averages.
IMPORTANT: Respond with ONLY a predicted temperature value or a narrow temperature range. Use the required unit symbol.
Examples of valid responses:
- "65{unit_symbol}"
- "58-72{unit_symbol}"
- "45.5{unit_symbol}"

Your prediction for {target_date} (must be just the temperature/range):"""

    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-09-2025:generateContent?key={API_KEY}"
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "tools": [{"google_search": {}}]
    }
    
    max_retries = 3
    base_delay = 1
    
    prediction = "AI couldn't generate a prediction."
    sources = []

    for attempt in range(max_retries):
        try:
            ai_response = requests.post(api_url, json=payload, timeout=10)
            ai_response.raise_for_status()
            
            ai_data = ai_response.json()
            candidate = ai_data.get("candidates", [{}])[0]
            
            if candidate and "text" in candidate.get("content", {}).get("parts", [{}])[0]:
                prediction = candidate["content"]["parts"][0]["text"].strip()
                
                if "groundingMetadata" in candidate:
                    sources = candidate["groundingMetadata"].get("groundingAttributions", [])
                break
            
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                # print(f"API request failed: {e}. Retrying in {delay}s...")
                time.sleep(delay)
            else:
                st.error(f"Failed to connect to the AI service after {max_retries} attempts.")
                st.json(ai_data if 'ai_data' in locals() else {"error": str(e), "message": "Check API Key and network connection."})
                st.stop()
        
        except Exception as e:
            st.error(f"AI response parsing failed: {e}")
            st.stop()


    # 4. Display Results
    st.markdown("---")
    st.subheader(f"🗓️ Prediction for {city_name} on {target_date}")
    
    st.markdown(f"<div style='background-color: #f0f2f6; padding: 20px; border-radius: 10px; text-align: center;'>"
                f"<h1 style='color: #FF4B4B;'>{prediction}</h1>"
                f"<p style='font-style: italic;'>Predicted Mean Daily Temperature</p>"
                f"</div>", unsafe_allow_html=True)
    
    if sources:
        st.subheader("📚 Sources Used by AI")
        for source in sources:
            if "web" in source:
                st.caption(f"- [{source['web']['title']}]({source['web']['uri']})")

    st.markdown("---")
    st.caption("*This is a long-range prediction based on historical data patterns and AI inference. Actual weather may vary.*")
