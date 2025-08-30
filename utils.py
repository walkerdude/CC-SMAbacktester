import numpy as np
import plotly.graph_objects as go

def analyze_performance(portfolio):
    total_return = portfolio["Total"].iloc[-1] / portfolio["Total"].iloc[0] - 1
    annual_return = (1 + total_return) ** (252 / len(portfolio)) - 1
    volatility = portfolio["Returns"].std() * np.sqrt(252)
    sharpe = annual_return / volatility if volatility else 0

    print(f"Total Return: {total_return:.2%}")
    print(f"Annual Return: {annual_return:.2%}")
    print(f"Annual Volatility: {volatility:.2%}")
    print(f"Sharpe Ratio: {sharpe:.2f}")

def plot_portfolio(portfolio):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=portfolio.index, y=portfolio["Total"], name="Portfolio Value"))
    fig.update_layout(title="Portfolio Value", xaxis_title="Date", yaxis_title="Value ($)")
    fig.show()
