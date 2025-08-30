import pandas as pd

class Backtester:
    def __init__(self, strategy, initial_capital=10000):
        self.strategy = strategy
        self.data = strategy.data
        self.initial_capital = initial_capital

    def run(self):
        signals = self.strategy.generate_signals()
        positions = pd.DataFrame(index=signals.index)
        positions["Position"] = 100 * signals["signal"]

        portfolio = pd.DataFrame(index=signals.index)
        # Ensure 'Close' is a Series, not a DataFrame
        close = self.data["Close"]
        if isinstance(close, pd.DataFrame):
            close = close.squeeze()
        portfolio["Holdings"] = positions["Position"] * close
        portfolio["Cash"] = self.initial_capital - (positions["Position"].diff() * close).cumsum().fillna(0)
        portfolio["Total"] = portfolio["Cash"] + portfolio["Holdings"]
        portfolio["Returns"] = portfolio["Total"].pct_change().fillna(0)

        return portfolio
