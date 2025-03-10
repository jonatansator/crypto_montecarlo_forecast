import numpy as np
import pandas as pd
import plotly.graph_objects as go
import ccxt
from datetime import datetime

# Constants
N_SIMS = 10000
FORECAST_DAYS = 30  # One-month forecast horizon
START_DATE = "2024-01-01"
END_DATE = "2024-10-12"
COLOR_BTC = '#FF9900'  # Brighter Bitcoin orange
COLOR_ETH = '#00B7EB'  # Brighter Ethereum cyan
COLOR_SOL = '#00FFAA'  # Brighter Solana teal
COLOR_BNB = '#FFD700'  # Brighter BNB gold

def fetch_crypto_data(ticker, start_date=START_DATE, end_date=END_DATE):
    """Fetch historical crypto data from Binance using ccxt and calculate mu and sigma."""
    try:
        # Initialize Binance exchange
        exchange = ccxt.binance()
        
        # Convert dates to milliseconds (ccxt uses timestamps in ms)
        start_ts = exchange.parse8601(f"{start_date}T00:00:00Z")
        end_ts = exchange.parse8601(f"{end_date}T00:00:00Z")
        
        # Fetch OHLCV data (daily timeframe)
        ohlcv = exchange.fetch_ohlcv(ticker, timeframe='1d', since=start_ts, limit=1000)
        if not ohlcv:
            raise ValueError(f"No data fetched for {ticker}")
        
        # Convert to DataFrame
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df = df[df['timestamp'] <= pd.to_datetime(end_date)]
        
        # Calculate daily returns
        daily_returns = df['close'].pct_change().dropna()
        if len(daily_returns) < 2:
            raise ValueError(f"Insufficient data points for {ticker} to calculate returns")
        
        # Debug: Check daily_returns
        print(f"{ticker} - Daily returns length: {len(daily_returns)}, First few: {daily_returns.head().tolist()}")
        
        # Annualized mean return (mu) and volatility (sigma) as scalars
        mu = (daily_returns.mean() * 365).item()
        sigma = (daily_returns.std() * np.sqrt(365)).item()
        
        # Last closing price
        initial_price = df['close'].iloc[-1].item()
        if initial_price <= 0:
            raise ValueError(f"Invalid initial price for {ticker}: {initial_price}")
        
        # Handle NaN in mu or sigma
        if np.isnan(mu) or np.isnan(sigma):
            raise ValueError(f"NaN detected in mu ({mu}) or sigma ({sigma}) for {ticker}")
        
        return initial_price, mu, sigma
    except Exception as e:
        raise Exception(f"Error in fetch_crypto_data for {ticker}: {str(e)}")

def simulate_crypto_prices(initial_price, mu, sigma, days=FORECAST_DAYS, sims=N_SIMS):
    """Simulate future crypto prices using Geometric Brownian Motion (GBM)."""
    try:
        dt = 1 / 365  # Daily time step in years
        daily_returns = np.random.normal(mu * dt, sigma * np.sqrt(dt), (sims, days))
        
        price_paths = np.zeros((sims, days))
        price_paths[:, 0] = initial_price
        for t in range(1, days):
            price_paths[:, t] = price_paths[:, t-1] * np.exp(daily_returns[:, t])
        
        final_prices = price_paths[:, -1]
        median_price = np.median(final_prices)
        ci_lower = np.percentile(final_prices, 2.5)
        ci_upper = np.percentile(final_prices, 97.5)
        
        return price_paths, median_price, ci_lower, ci_upper
    except Exception as e:
        raise Exception(f"Error in simulate_crypto_prices: {str(e)}")

def plot_crypto_forecast(price_paths, median_price, ci_lower, ci_upper, crypto_name, color):
    fig = go.Figure()
    
    dates = pd.date_range(start=datetime.strptime(END_DATE, "%Y-%m-%d"), periods=FORECAST_DAYS)
    for i in range(min(100, N_SIMS)):
        fig.add_trace(go.Scatter(
            x=dates,
            y=price_paths[i],
            mode='lines',
            line=dict(color=color, width=0.8),
            opacity=0.3,
            showlegend=False
        ))
    
    median_path = np.median(price_paths, axis=0)
    fig.add_trace(go.Scatter(
        x=dates,
        y=median_path,
        mode='lines',
        line=dict(color=color, width=2.5, dash='dash'),
        name=f'{crypto_name} Median'
    ))
    
    ci_dates = dates.tolist() + dates[::-1].tolist()
    ci_values = np.concatenate([np.percentile(price_paths, 97.5, axis=0), 
                                np.percentile(price_paths, 2.5, axis=0)[::-1]])
    fig.add_trace(go.Scatter(
        x=ci_dates,
        y=ci_values,
        fill='toself',
        fillcolor=f'rgba{(*tuple(int(color[i:i+2], 16) for i in (1, 3, 5)), 0.25)}',
        line=dict(color='rgba(255,255,255,0)'),
        name='95% CI'
    ))
    
    fig.update_layout(
        title=dict(text=f'{crypto_name} Price Forecast (Monte Carlo Simulation)', font_color='white'),
        xaxis_title=dict(text='Date', font_color='white'),
        yaxis_title=dict(text='Price (USD)', font_color='white'),
        plot_bgcolor='rgb(40, 40, 40)',
        paper_bgcolor='rgb(40, 40, 40)',
        font_color='white',
        xaxis=dict(gridcolor='rgba(255, 255, 255, 0.1)', gridwidth=0.5),
        yaxis=dict(gridcolor='rgba(255, 255, 255, 0.1)', gridwidth=0.5),
        showlegend=True,
        margin=dict(l=50, r=50, t=50, b=50)
    )
    
    fig.show()

if __name__ == "__main__":
    crypto_data = {
        'BTC': {'ticker': 'BTC/USDT', 'color': COLOR_BTC},
        'ETH': {'ticker': 'ETH/USDT', 'color': COLOR_ETH},
        'SOL': {'ticker': 'SOL/USDT', 'color': COLOR_SOL},
        'BNB': {'ticker': 'BNB/USDT', 'color': COLOR_BNB}
    }
    
    for crypto, params in crypto_data.items():
        try:
            initial_price, mu, sigma = fetch_crypto_data(params['ticker'])
            price_paths, med_price, ci_low, ci_high = simulate_crypto_prices(
                initial_price=initial_price,
                mu=mu,
                sigma=sigma
            )
            
            print(f"{crypto} Forecast (30 Days from {END_DATE}):")
            print(f"Starting Price: ${initial_price:,.2f}")
            print(f"Median Price: ${med_price:,.2f}")
            print(f"95% CI: [${ci_low:,.2f}, ${ci_high:,.2f}]")
            print(f"Annualized Return (mu): {mu:.2%}")
            print(f"Annualized Volatility (sigma): {sigma:.2%}")
            print("-" * 50)
            
            plot_crypto_forecast(price_paths, med_price, ci_low, ci_high, crypto, params['color'])
        except Exception as e:
            print(f"Error processing {crypto}: {str(e)}")