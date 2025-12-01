import streamlit as st
import requests
from datetime import datetime, timedelta
st.set_page_config(page_title="Weather Predictor", page_icon="🌤️")
st.title("Long-Range Weather Predictor")
st.write("Predict weather up to 1 year in the future using historical data!")
try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
except:
    st.error("Please add GEMINI_API_KEY to your secrets!")
    st.stop()
city = st.text_input("Enter a city name:", "Atlanta")
days_ahead = st.slider("Days in the future:", 1, 365, 30)
units = st.radio("Temperature units:", ["Fahrenheit", "Celsius"])
if st.button("Predict Weather"):
    st.info(f"Looking up {city}...")
    geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={city}"
    geo_response = requests.get(geo_url)
    geo_data = geo_response.json()
    if "results" not in geo_data:
        st.error("City not found! Try a different name.")
        st.stop()
    lat = geo_data["results"][0]["latitude"]
    lon = geo_data["results"][0]["longitude"]
    city_name = geo_data["results"][0]["name"]
    st.info(f"Getting 30 years of data for the target date in {city_name}...")
    target_date = datetime.now() + timedelta(days=days_ahead)
    target_month = target_date.month
    target_day = target_date.day
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=30*365)).strftime("%Y-%m-%d")
    unit_param = "fahrenheit" if units == "Fahrenheit" else "celsius"
    weather_url = f"https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={lon}&start_date={start_date}&end_date={end_date}&daily=temperature_2m_mean&temperature_unit={unit_param}"
    weather_response = requests.get(weather_url)
    weather_data = weather_response.json()
    if "daily" not in weather_data or "time" not in weather_data["daily"]:
        st.error("Couldn't get weather data. Try again!")
        st.stop()
    temps = weather_data["daily"]["temperature_2m_mean"]
    dates = weather_data["daily"]["time"]
    historical_temps = []
    for date_str, temp in zip(dates, temps):
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            if dt.month == target_month and dt.day == target_day:
                historical_temps.append(temp)
        except ValueError:
            pass
    if not historical_temps:
        st.error(f"Couldn't find enough historical data for the date: {target_date.strftime('%B %d')}. (May be due to leap day or missing records)")
        st.stop()
    avg_temp = sum(historical_temps) / len(historical_temps)
    min_temp = min(historical_temps)
    max_temp = max(historical_temps)
    unit_symbol = "°F" if units == "Fahrenheit" else "°C"
    st.success("Historical data collected!")
    st.write(f"**Average temperature on this date (30 years):** {avg_temp:.1f}{unit_symbol}")
    st.write(f"**Lowest recorded on this date:** {min_temp:.1f}{unit_symbol}")
    st.write(f"**Highest recorded on this date:** {max_temp:.1f}{unit_symbol}")
    st.info("Asking AI to predict the weather...")
    target_date_str = target_date.strftime("%Y-%m-%d")
    prompt = f"""Based on this historical weather data for {city_name}, predict the temperature range for {target_date_str}. The prediction must be based ONLY on the provided historical summaries for the specific date.
Historical Data (30 years on this specific date):
- Average temperature: {avg_temp:.1f}{unit_symbol}
- Coldest: {min_temp:.1f}{unit_symbol}
- Hottest: {max_temp:.1f}{unit_symbol}
IMPORTANT: Respond with ONLY a temperature value or range. No explanation, no analysis, no extra text.
Examples of valid responses:
- "65{unit_symbol}"
- "58-72{unit_symbol}"
- "45.5{unit_symbol}"
Your response:"""
    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    ai_response = requests.post(api_url, json=payload)
    ai_data = ai_response.json()
    try:
        prediction = ai_data["candidates"][0]["content"]["parts"][0]["text"]
        st.subheader(f"Weather Prediction for {target_date_str}")
        st.write(prediction)
    except Exception as e:
        st.error("AI couldn't generate a prediction. Try again!")
        st.json(ai_data)
