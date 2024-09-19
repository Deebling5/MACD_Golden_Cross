import os
import numpy as np
import pandas as pd
from tabulate import tabulate


def get_suffix(stock_symbol):
    """Extracts suffix from stock symbol."""
    if '=' in stock_symbol:
        return stock_symbol.split('=')[-1]
    elif '.' in stock_symbol:
        return stock_symbol.split('.')[-1]
    return None


def get_threshold(suffix):
    """Returns threshold based on stock suffix."""
    thresholds = {
        'T': 1.4e9,
        'L': 7.8e6,
        'T0': 1.34e7,
        'SI': 1.34e7,
        'HK': 1.25e6,
        'X': 0,
        'F': 0,
    }
    return thresholds.get(suffix, 1e7)  # default threshold is 1e7


def enough_amount(data, i, stock_symbol):
    """Checks if the turnover is enough based on volume and close price."""
    amount = data['Volume'].iloc[-i] * data['Close'].iloc[-i]
    suffix = get_suffix(stock_symbol)
    threshold = get_threshold(suffix)
    return amount > threshold


def calculate_ma_slope(data, ma_window, bar_number):
    """Calculates the moving average slope."""
    ma = data.rolling(ma_window).mean()
    if len(ma) < bar_number:
        raise ValueError(f"Insufficient data: need at least {bar_number} points.")
    return ma, (ma.iloc[-1] - ma.iloc[-bar_number]) / (bar_number - 1)


def calculate_hma(data, period):
    """Calculates the Hull Moving Average (HMA)."""
    wma_half_period = data.rolling(window=int(period / 2)).mean() * 2
    wma_full_period = data.rolling(window=period).mean()
    raw_hma = wma_half_period - wma_full_period
    return raw_hma.rolling(window=int(np.sqrt(period))).mean()


def peak_trough_peak_hma(data, begin, end, peak_allowance, peak_trough_ratio):
    """Detects peak-trough-peak pattern using HMA."""
    data['HMA3'] = calculate_hma(data['Close'], 3)
    if end <= begin:
        return False, None
    right_peak = data['HMA3'].iloc[-begin]
    for i in range(begin + 3, end):
        left_peak = data['HMA3'].iloc[-i]
        for j in range(i - 1, begin + 3, -1):
            trough = data['HMA3'].iloc[-j]
            if (1 - peak_allowance) * left_peak <= right_peak <= (1 + peak_allowance) * left_peak and peak_trough_ratio <= left_peak / trough:
                return True, -i
    return False, None


def process_stocks(data_dir='data'):
    """Processes stock data and detects cup-and-handle patterns."""
    cup_and_handle = []

    for stock in os.listdir(data_dir):
        try:
            df = pd.read_csv(f'{data_dir}/{stock}')
        except Exception as e:
            print(f"Error processing {stock}: {e}")
            continue

        if len(df) < 110:
            print(f"Not enough data for {stock}, skipping.")
            continue

        if not enough_amount(df, 2, stock):
            print(f"Turnover too low for {stock}, skipping.")
            continue

        ma60, ma60_slope = calculate_ma_slope(df['Close'], 60, 3)
        if ma60_slope < 0:
            continue

        ptp1, ptp_index1 = peak_trough_peak_hma(df, begin=2, end=15, peak_allowance=0.01, peak_trough_ratio=1.05)
        if not ptp1:
            continue

        ptp1_date = df['Date'].iloc[ptp_index1]
        ptp2, ptp_index2 = peak_trough_peak_hma(df, begin=ptp_index1, end=100, peak_allowance=0.01, peak_trough_ratio=1.3)

        if ptp2:
            ptp2_date = df['Date'].iloc[ptp_index2]
            cup_and_handle.append([stock, ptp1_date, ptp2_date, ptp_index2 - ptp_index1])
        else:
            print(f"Handle found at {ptp1_date}, but no cup found for {stock}")

    return cup_and_handle


def print_cup_and_handle_table(cup_and_handle):
    """Prints the cup and handle patterns in a tabular format."""
    headers = ['Stock', 'Inner Rim Date', 'Outer Rim Date', 'Cup Width']
    print(tabulate(cup_and_handle, headers=headers, tablefmt='pretty'))


# Run the analysis and print results
cup_and_handle_data = process_stocks()
if cup_and_handle_data:
    print_cup_and_handle_table(cup_and_handle_data)
else:
    print("No cup and handle patterns found.")
