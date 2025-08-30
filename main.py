import yfinance as yf
from strategy_template import SMACrossoverStrategy, CoveredCallStrategy
from backtester import Backtester
from utils import analyze_performance
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime

def get_data(ticker, start, end, interval='1d'):
    df = yf.download(ticker, start=start, end=end, interval=interval)
    # Flatten columns if MultiIndex (sometimes happens with yfinance)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0] if isinstance(col, tuple) else col for col in df.columns]
    return df.dropna()

def plot_cumulative_returns(portfolio, benchmark, benchmark_name="S&P 500", value_col="Total"):
    # Calculate cumulative returns
    strat_cum = (portfolio[value_col] / portfolio[value_col].iloc[0])
    bench_cum = (benchmark["Total"] / benchmark["Total"].iloc[0])
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=strat_cum.index, y=strat_cum, name="Strategy"))
    fig.add_trace(go.Scatter(x=bench_cum.index, y=bench_cum, name=benchmark_name))
    fig.update_layout(title="Cumulative Returns: Strategy vs Benchmark", xaxis_title="Date", yaxis_title="Cumulative Return")
    fig.show()

def get_date_input(prompt, default):
    user_input = input(f"{prompt} [{default}]: ").strip()
    if not user_input:
        return default
    try:
        # Try to parse the date
        datetime.strptime(user_input, "%Y-%m-%d")
        return user_input
    except ValueError:
        print("Invalid date format. Please use YYYY-MM-DD.")
        return get_date_input(prompt, default)

def main():
    ticker = input("Enter stock ticker for covered call strategy [AAPL]: ").strip() or "AAPL"
    benchmark_ticker = "^GSPC"
    default_start = "2020-01-01"
    default_end = "2023-01-01"

    # Prompt user for dates
    start_date = get_date_input("Enter start date (YYYY-MM-DD)", default_start)
    end_date = get_date_input("Enter end date (YYYY-MM-DD)", default_end)

    # Download daily and weekly data
    data_daily = get_data(ticker, start_date, end_date, interval='1d')
    data_weekly = get_data(ticker, start_date, end_date, interval='1wk')
    benchmark_data = get_data(benchmark_ticker, start_date, end_date, interval='1wk')

    # Ensure 'Close' is a Series for all dataframes
    for df in [data_daily, data_weekly, benchmark_data]:
        if isinstance(df["Close"], pd.DataFrame):
            df["Close"] = df["Close"].squeeze()

    # Drop all rows with NaN Close in both data_weekly and benchmark_data
    data_weekly = data_weekly.dropna(subset=["Close"])
    benchmark_data = benchmark_data.dropna(subset=["Close"])
    # Align both to the intersection of valid dates
    common_index = data_weekly.index.intersection(benchmark_data.index)
    data_weekly = data_weekly.loc[common_index]
    benchmark_data = benchmark_data.loc[common_index]

    # Debug output
    print("Data weekly head:\n", data_weekly.head())
    print("Benchmark weekly head:\n", benchmark_data.head())
    print("Data weekly NaNs:", data_weekly["Close"].isna().sum())
    print("Benchmark weekly NaNs:", benchmark_data["Close"].isna().sum())

    # Choose strategy
    print("Select strategy:")
    print("1. Covered Call Strategy")
    print("2. SMA Crossover Strategy")
    strat_choice = input("Enter 1 or 2 [1]: ").strip() or "1"

    if strat_choice == "2":
        # SMA Crossover (uses daily data)
        data_daily = data_daily.loc[data_daily.index.intersection(benchmark_data.index)]
        strategy = SMACrossoverStrategy(data_daily)
        backtester = Backtester(strategy)
        portfolio = backtester.run()
        value_col = "Total"
        print("\nSMA Crossover Strategy Performance:")
        analyze_performance(portfolio)
    else:
        # Covered Call (uses weekly data)
        strategy = CoveredCallStrategy(data_weekly, ticker=ticker)
        portfolio = strategy.generate_signals()
        value_col = "PortfolioValue"
        print("\nCovered Call Strategy Performance:")
        # Print total premiums collected and contracts sold
        print(f"Total premiums collected: ${portfolio['PremiumsCollected'].iloc[-1]:.2f}")
        print(f"Contracts sold (last week): {portfolio['ContractsSold'].iloc[-1]}")

    # Benchmark returns (weekly)
    benchmark = pd.DataFrame(index=benchmark_data.index)
    benchmark["Returns"] = benchmark_data["Close"].pct_change().fillna(0)
    benchmark["Total"] = (1 + benchmark["Returns"]).cumprod()

    print("\nS&P 500 Performance:")
    analyze_performance(benchmark)

    plot_cumulative_returns(portfolio, benchmark, value_col=value_col)

if __name__ == "__main__":
    main()
