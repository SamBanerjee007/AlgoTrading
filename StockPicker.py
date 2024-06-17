import yfinance as yf
import pandas as pd
import ta
import os
import sys
from contextlib import contextmanager
from datetime import datetime, timedelta

# URL of the Wikipedia page containing the list of S&P 500 companies
url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"

# Read the HTML tables from the Wikipedia page
tables = pd.read_html(url)

# The first table on the page is the one we want
sp500_table = tables[0]

# Extract the 'Symbol' column which contains the ticker symbols
nasdaq_stocks = sp500_table['Symbol'].tolist()

@contextmanager
def suppress_stdout_stderr():
    with open(os.devnull, 'w') as fnull:
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        try:
            sys.stdout = fnull
            sys.stderr = fnull
            yield
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

def perform_analysis(stock_data):
    stock_data['macd'] = ta.trend.macd_diff(stock_data['Adj Close'])
    stock_data['rsi'] = ta.momentum.rsi(stock_data['Adj Close'])
    indicator_bb = ta.volatility.BollingerBands(stock_data['Adj Close'])
    stock_data['bb_high'] = indicator_bb.bollinger_hband()
    stock_data['bb_low'] = indicator_bb.bollinger_lband()
    stock_data['ma_50'] = stock_data['Adj Close'].rolling(window=50).mean()
    stock_data['ma_200'] = stock_data['Adj Close'].rolling(window=200).mean()
    stock_data['stoch_oscillator'] = ta.momentum.StochasticOscillator(stock_data['High'], stock_data['Low'], stock_data['Adj Close']).stoch()
    return stock_data

def count_recent_positive_days(series, threshold=5):
    recent_data = series.tail(threshold)
    positive_days = (recent_data > 0).sum()
    return positive_days

def count_recent_negative_days(series, threshold=5):
    recent_data = series.tail(threshold)
    negative_days = (recent_data < 0).sum()
    return negative_days

def find_top_stocks(current_date):
    top_stocks = {}
    analysis_results = {}

    for stock in nasdaq_stocks:
        try:
            with suppress_stdout_stderr():
                stock_data = yf.download(stock, start="2023-01-01", end=current_date, progress=False)

            if stock_data.empty:
                print(f"No data for {stock}")
                continue

            stock_data.dropna(inplace=True)

            if stock_data.shape[0] < 200:
                print(f"Not enough data points for {stock}")
                continue

            stock_data = perform_analysis(stock_data)
            analysis_results[stock] = stock_data

            recent_macd_positive_days = count_recent_positive_days(stock_data['macd'])
            recent_macd_negative_days = count_recent_negative_days(stock_data['macd'])
            recent_rsi_below_70_days = count_recent_positive_days(stock_data['rsi'], threshold=70)
            recent_price_above_bb_low_days = count_recent_positive_days(stock_data['Adj Close'] - stock_data['bb_low'])
            recent_price_above_ma_50_days = count_recent_positive_days(stock_data['Adj Close'] - stock_data['ma_50'])
            recent_price_above_ma_200_days = count_recent_positive_days(stock_data['Adj Close'] - stock_data['ma_200'])
            recent_stoch_below_80_days = count_recent_positive_days(80 - stock_data['stoch_oscillator'])

            score = (
                recent_macd_positive_days -
                recent_macd_negative_days + 
                recent_rsi_below_70_days +
                recent_price_above_bb_low_days +
                recent_price_above_ma_50_days +
                recent_price_above_ma_200_days +
                recent_stoch_below_80_days
            )

            if score > 0:
                top_stocks[stock] = score
        except Exception as e:
            print(f"Error processing {stock}: {e}")

    top_stocks = dict(sorted(top_stocks.items(), key=lambda item: item[1], reverse=True)[:3])

    return top_stocks, analysis_results

if __name__ == "__main__":
    today = datetime.today()
    current_date = today.strftime('%Y-%m-%d')

    top_stocks, analysis_results = find_top_stocks(current_date)

    if not top_stocks:
        print("No top stocks found.")

    print("Top Stocks and their Technical Analysis:")
    for stock, score in top_stocks.items():
        print(f"\nSymbol: {stock}, Score: {score}")
        stock_data = analysis_results[stock].tail()

        formatted_data = stock_data.copy()
        for column in ['Adj Close', 'bb_high', 'bb_low', 'ma_50', 'ma_200']:
            if column in formatted_data.columns:
                formatted_data[column] = formatted_data[column].apply(lambda x: f"${x:.2f}")

        for column in ['macd', 'rsi', 'stoch_oscillator']:
            if column in formatted_data.columns:
                formatted_data[column] = formatted_data[column].apply(lambda x: f"{x:.2f}")

        print(formatted_data[['Adj Close', 'macd', 'rsi', 'bb_high', 'bb_low', 'ma_50', 'ma_200', 'stoch_oscillator']])
