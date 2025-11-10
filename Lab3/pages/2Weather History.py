import streamlit as st
import datetime
import requests
import pandas as pd

st.header("Weather History Selector")
st.write("")
st.write("---")
city=st.text_input("What city do you want to look at?","Atlanta")
st.write("---")
start = st.date_input("When would you like to start?", min_value=datetime.date(1995, 1, 1), max_value=datetime.date(2024, 10, 31))
st.write("You chose:",start)
st.write("---")
end = st.date_input("When would you like to end?", min_value=datetime.date(1995, 1, 1), max_value=datetime.date(2025, 10, 31))
st.write("You chose:",end)
st.write("---")
if st.button("Let's See"):
    url=f"https://geocoding-api.open-meteo.com/v1/search?name={city}"
    endpoint=requests.get(url)
    data=endpoint.json()
    pophigh=0
    lat=0
    long=0
    for c in data["results"]:
        if "population" in c:
            if c["population"]>pophigh:
                pophigh=c["population"]
                lat=c["latitude"]
                long=c["longitude"]
    url2=f"https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={long}&start_date={start}&end_date={end}&daily=temperature_2m_max,temperature_2m_min,temperature_2m_mean&hourly=temperature_2m&temperature_unit=fahrenheit"
    endpoint2=requests.get(url2)
    data2=endpoint2.json()
    dates=data2["daily"]["time"]
    y=data2["daily"]["temperature_2m_mean"]
    st.line_chart(pd.DataFrame({'Temperature over time in fahrenheit':y},index=pd.to_datetime(dates)))
    
