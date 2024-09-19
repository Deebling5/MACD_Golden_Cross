import datetime as dt
import os
import pandas as pd
import streamlit as st
import yfinance as yf

# Load stock list
csvfilename = "nifty500_1.csv"
stocklist = pd.read_csv(csvfilename, engine="python", encoding="ISO-8859-1")

# Date range for stock data
start = dt.datetime.now() - dt.timedelta(days=150)
now = dt.datetime.now()

# Define utility functions
def find_amount(data, i):
    """Calculate turnover (Volume * Close price) for the i-th index from the end."""
    return data['Volume'].iloc[-i] * data['Close'].iloc[-i]

def cross(parameter1, parameter2, i):
    """Check if parameter1 crosses above parameter2 at index i."""
    return (parameter1.iloc[-i - 1] < parameter2.iloc[-i - 1]) and (parameter1.iloc[-i] > parameter2.iloc[-i])

def increasing(parameter, period):
    """Check if a parameter is increasing over a specified period."""
    for i in range(-period, 0):
        if parameter.iloc[i] >= parameter.iloc[i + 1]:
            return False
    return True

def cross_within_period(parameter1, parameter2, begin, period, dates):
    """Check if parameter1 crosses above parameter2 within a specified period and return the date of the cross."""
    for i in range(begin, begin + period + 1):
        if cross(parameter1, parameter2, i):
            return dates.iloc[-i]  # Return date of the cross
    return None

# Download latest data using yfinance
def snapshot(data_dir='data'):
    """Fetch the latest stock data and save it to the specified directory."""
    with open('nifty500.csv') as f:
        for line in f:
            if "," not in line:
                continue
            symbol = line.split(",")[1].strip()
            name = line.split(",")[0].strip()
            st.write(f"Fetching data for {name} ({symbol})...")
            data = yf.download(symbol, period="1y", threads=True)
            data.to_csv(f'{data_dir}/{name}.csv')
    st.success("Data download completed!")
    return {"code": "success"}

# Main function to process stocks and find patterns
def process_stocks(data_dir='data', search_period=0):
    ema821_gc = []

    for stock in os.listdir(data_dir):
        try:
            df = pd.read_csv(f'{data_dir}/{stock}')
        except Exception as e:
            st.write(f"Error retrieving data for {stock}: {e}")
            continue

        # Ensure sufficient data points
        if len(df) < 80:
            st.write(f"Not enough data points for {stock}, skipping.")
            continue

        # Check turnover
        if find_amount(df, 2) < 2e7:
            st.write(f"Turnover of {stock} is too low, skipping.")
            continue

        # EMA 60 Slope check (trend direction)
        ema60 = df["Close"].ewm(span=60).mean()
        if (ema60.iloc[-1] - ema60.iloc[-3]) / 2 < 0:
            continue

        # EMA 8-21 Golden Cross
        ema8 = df['Close'].ewm(span=8).mean()
        ema21 = df['Close'].ewm(span=21).mean()
        slope_ema21 = (ema21.iloc[-1] - ema21.iloc[-3]) / 2
        golden_cross_date = cross_within_period(ema8, ema21, 1, search_period, df['Date'])

        if golden_cross_date is None and slope_ema21 >= 0:
            continue

        # Volume EMA 8-21 Golden Cross
        vea8 = df['Volume'].ewm(span=8).mean()
        vea21 = df['Volume'].ewm(span=21).mean()
        if cross_within_period(vea8, vea21, 1, search_period, df['Date']) is None:
            continue

        # MACD (5,34,5) check
        ema5 = df['Close'].ewm(span=5).mean()
        ema34 = df['Close'].ewm(span=34).mean()
        macd_line = ema5 - ema34
        signal_line = macd_line.ewm(span=5).mean()

        macd_index = cross_within_period(macd_line, signal_line, 1, search_period, df['Date'])
        if macd_index is not None and df['Close'].iloc[-1] > ema60.iloc[-1] and signal_line.iloc[-1] > signal_line.iloc[-2] and \
                signal_line.iloc[-1] >= 0:
            ema821_gc.append([stock.strip('.csv'), df['Date'].iloc[-1], round(ema60.iloc[-1], 2), golden_cross_date])

    return ema821_gc

# Streamlit UI
st.title("Stock Pattern Analysis")

# Get the search period from the user
search_period = st.number_input("Enter search period (in days)", min_value=0, value=0, step=1)

# Directory where stock data is stored (ensure this path exists)
data_dir = "data"

# Button to fetch the latest data
if st.button("Fetch Latest Data"):
    st.write("Fetching latest data...")
    snapshot(data_dir=data_dir)

# Button to run stock analysis
if st.button("Run Analysis"):
    result = process_stocks(data_dir=data_dir, search_period=search_period)

    # Display results
    if result:
        df_result = pd.DataFrame(result, columns=['Stock', 'Last Date', 'MACD GC at', 'Golden Cross Date'])
        st.write(df_result)
    else:
        st.write("No stocks found with the specified criteria.")
