import gradio as gr
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
from strategy_template import SMACrossoverStrategy, CoveredCallStrategy
from backtester import Backtester
import yfinance as yf

def get_data(ticker, start, end, interval='1d'):
    df = yf.download(ticker, start=start, end=end, interval=interval)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0] if isinstance(col, tuple) else col for col in df.columns]
    return df.dropna()

def run_backtest(ticker, benchmark_ticker, start_date, end_date, initial_cash, strategy_choice):
    try:
        # Download data
        data_daily = get_data(ticker, start_date, end_date, interval='1d')
        data_weekly = get_data(ticker, start_date, end_date, interval='1wk')
        benchmark_data = get_data(benchmark_ticker, start_date, end_date, interval='1wk')
        for df in [data_daily, data_weekly, benchmark_data]:
            if isinstance(df["Close"], pd.DataFrame):
                df["Close"] = df["Close"].squeeze()
        # Clean and align
        data_weekly = data_weekly.dropna(subset=["Close"])
        benchmark_data = benchmark_data.dropna(subset=["Close"])
        common_index = data_weekly.index.intersection(benchmark_data.index)
        data_weekly = data_weekly.loc[common_index]
        benchmark_data = benchmark_data.loc[common_index]
        # Run strategy
        if strategy_choice == "SMA Crossover":
            data_daily = data_daily.loc[data_daily.index.intersection(benchmark_data.index)]
            strategy = SMACrossoverStrategy(data_daily)
            backtester = Backtester(strategy)
            portfolio = backtester.run()
            value_col = "Total"
        else:
            strategy = CoveredCallStrategy(data_weekly, initial_cash=initial_cash, ticker=ticker)
            portfolio = strategy.generate_signals(debug=False)
            value_col = "PortfolioValue"
        # Benchmark returns
        benchmark = pd.DataFrame(index=benchmark_data.index)
        benchmark["Returns"] = benchmark_data["Close"].pct_change().fillna(0)
        benchmark["Total"] = (1 + benchmark["Returns"]).cumprod()
        # Metrics
        strat_total_return = portfolio[value_col].iloc[-1] / portfolio[value_col].iloc[0] - 1
        strat_annual_return = (1 + strat_total_return) ** (52 / len(portfolio)) - 1
        strat_vol = portfolio[value_col].pct_change().std() * (52 ** 0.5)
        strat_sharpe = strat_annual_return / strat_vol if strat_vol else 0
        bench_total_return = benchmark["Total"].iloc[-1] / benchmark["Total"].iloc[0] - 1
        bench_annual_return = (1 + bench_total_return) ** (52 / len(benchmark)) - 1
        bench_vol = benchmark["Returns"].std() * (52 ** 0.5)
        bench_sharpe = bench_annual_return / bench_vol if bench_vol else 0
        # Plot cumulative returns
        strat_cum = (portfolio[value_col] / portfolio[value_col].iloc[0])
        bench_cum = (benchmark["Total"] / benchmark["Total"].iloc[0])
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=strat_cum.index, y=strat_cum, name="Strategy"))
        fig.add_trace(go.Scatter(x=bench_cum.index, y=bench_cum, name="S&P 500"))
        fig.update_layout(title="Cumulative Returns: Strategy vs S&P 500", xaxis_title="Date", yaxis_title="Cumulative Return")
        # Prepare metrics for display
        metrics = {
            "Strategy Total Return": f"{strat_total_return:.2%}",
            "Strategy Annual Return": f"{strat_annual_return:.2%}",
            "Strategy Volatility": f"{strat_vol:.2%}",
            "Strategy Sharpe Ratio": f"{strat_sharpe:.2f}",
            "S&P 500 Total Return": f"{bench_total_return:.2%}",
            "S&P 500 Annual Return": f"{bench_annual_return:.2%}",
            "S&P 500 Volatility": f"{bench_vol:.2%}",
            "S&P 500 Sharpe Ratio": f"{bench_sharpe:.2f}"
        }
        if strategy_choice == "Covered Call":
            metrics["Total Premiums Collected"] = f"${portfolio['PremiumsCollected'].iloc[-1]:.2f}"
            metrics["Contracts Sold (last week)"] = f"{portfolio['ContractsSold'].iloc[-1]}"
        # Return chart, metrics, and table
        return fig, metrics, portfolio.reset_index()
    except Exception as e:
        return go.Figure(), {"Error": str(e)}, pd.DataFrame()

with gr.Blocks() as demo:
    gr.Markdown("# 📈 Advanced Trading Strategy Backtester (Gradio)")
    with gr.Row():
        with gr.Column():
            ticker = gr.Textbox(label="Stock Ticker", value="AAPL")
            benchmark_ticker = gr.Textbox(label="Benchmark Ticker", value="^GSPC")
            start_date = gr.Textbox(label="Start Date (YYYY-MM-DD)", value="2020-01-01")
            end_date = gr.Textbox(label="End Date (YYYY-MM-DD)", value="2023-01-01")
            initial_cash = gr.Number(label="Initial Cash (for Covered Call)", value=0)
            strategy_choice = gr.Radio(["Covered Call", "SMA Crossover"], label="Strategy", value="Covered Call")
            run_btn = gr.Button("Run Backtest")
        with gr.Column():
            chart = gr.Plot(label="Cumulative Returns Chart")
            metrics = gr.JSON(label="Performance Metrics")
    table = gr.Dataframe(label="Week-by-Week Results")
    run_btn.click(run_backtest, inputs=[ticker, benchmark_ticker, start_date, end_date, initial_cash, strategy_choice], outputs=[chart, metrics, table])

demo.launch() 