import yfinance as yf
import pandas as pd
import numpy as np
from scipy.stats import norm

class Strategy:
    def __init__(self, data):
        self.data = data
        self.signals = pd.DataFrame(index=data.index)
        self.signals["signal"] = 0

    def generate_signals(self):
        raise NotImplementedError("Override this method in your strategy class.")

class SMACrossoverStrategy(Strategy):
    def generate_signals(self):
        short = 40
        long = 100
        self.signals["short_ma"] = self.data["Close"].rolling(short).mean()
        self.signals["long_ma"] = self.data["Close"].rolling(long).mean()
        self.signals["signal"] = (self.signals["short_ma"] > self.signals["long_ma"]).astype(int)
        return self.signals

class CoveredCallStrategy(Strategy):
    def __init__(self, data, initial_cash=0, ticker=None):
        super().__init__(data)
        self.initial_cash = initial_cash
        self.ticker = ticker

    def get_current_iv(self, spot):
        try:
            ticker_obj = yf.Ticker(self.ticker)
            expiries = ticker_obj.options
            if not expiries:
                print("No options expiries found for ticker.")
                return None
            expiry = expiries[0]  # Nearest expiry
            opt_chain = ticker_obj.option_chain(expiry)
            calls = opt_chain.calls
            atm_idx = (calls["strike"] - spot).abs().idxmin()
            iv = calls.loc[atm_idx, "impliedVolatility"]
            print(f"Fetched current ATM IV from yfinance: {iv:.2%}")
            return iv
        except Exception as e:
            print(f"Could not fetch IV from yfinance: {e}")
            return None

    def black_scholes_call(self, S, K, T, r, sigma):
        if S <= 0 or K <= 0 or sigma <= 0 or T <= 0:
            return 0.0
        d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)
        call = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
        return max(call, 0.0)

    def generate_signals(self, debug=True):
        # Resample to weekly (Friday close)
        weekly = self.data.resample('W-FRI').last()
        # Build a list of (date, price) tuples with only valid prices
        valid_weeks = [(date, row["Close"]) for date, row in weekly.iterrows() if pd.notna(row["Close"]) and row["Close"] > 0]
        portfolio = pd.DataFrame(index=[date for date, _ in valid_weeks])
        shares = 100  # Start with 100 shares
        cash = self.initial_cash
        premiums_collected = 0.0
        contracts_sold = []
        premiums = []
        shares_list = []
        cash_list = []
        value_list = []
        price_list = []
        assignment_list = []
        leftover_shares_list = []
        debug_rows = []
        n = len(valid_weeks)
        # Fetch IV once at the start using the first week's price
        iv = self.get_current_iv(valid_weeks[0][1]) if self.ticker else None
        for idx, (date, price) in enumerate(valid_weeks):
            price_list.append(price)
            # Flexible reinvestment: buy as many shares as possible
            shares_to_buy = int(cash // price)
            if shares_to_buy > 0:
                shares += shares_to_buy
                cash -= shares_to_buy * price
            contracts = shares // 100
            leftover_shares = shares % 100
            # Use IV from yfinance if available, else fallback to historical volatility
            if iv is not None and iv > 0:
                sigma = iv
            elif idx > 0:
                prev_prices = [p for _, p in valid_weeks[:idx+1]]
                logrets = np.log(pd.Series(prev_prices)).diff().dropna()
                sigma = logrets.std() * np.sqrt(52)
            else:
                sigma = 0.2  # fallback default
            # Only sell contracts if you have at least 100 shares
            if contracts > 0:
                strike = price * 1.05
                T = 1/52
                r = 0.02
                premium = self.black_scholes_call(price, strike, T, r, sigma) * contracts
                cash += premium
                premiums_collected += premium
            else:
                premium = 0.0
            premiums.append(premiums_collected)
            contracts_sold.append(contracts)
            assignment = False
            # Option expires next week: check if price >= strike
            if contracts > 0 and idx < n - 1:
                next_price = valid_weeks[idx+1][1]
                if next_price >= strike:
                    # Option exercised: sell all shares at strike
                    cash += strike * (contracts * 100)
                    shares -= contracts * 100
                    assignment = True
            shares_list.append(shares)
            cash_list.append(cash)
            value_list.append(cash + shares * price)
            assignment_list.append(assignment)
            leftover_shares_list.append(leftover_shares)
            if debug:
                debug_rows.append({
                    'Week': date.strftime('%Y-%m-%d'),
                    'Price': price,
                    'Shares': shares,
                    'Contracts': contracts,
                    'LeftoverShares': leftover_shares,
                    'Cash': cash,
                    'Premium': premium,
                    'Sigma': sigma,
                    'Assignment': assignment
                })
        portfolio["PortfolioValue"] = value_list
        portfolio["PremiumsCollected"] = premiums
        portfolio["ContractsSold"] = contracts_sold
        portfolio["SharesHeld"] = shares_list
        portfolio["LeftoverShares"] = leftover_shares_list
        portfolio["Assignment"] = assignment_list
        portfolio["Close"] = price_list
        if debug:
            debug_df = pd.DataFrame(debug_rows)
            print("\nWEEK-BY-WEEK DEBUG OUTPUT:")
            print(debug_df.to_string(index=False))
        return portfolio
