import numpy as np
import pandas as pd
import yfinance as yf
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Flatten, SimpleRNN, GRU, LSTM, Dropout

# تابع پیش‌پردازش داده و مهندسی ویژگی
def fetch_and_prepare(ticker, start, end, features=['Adj_Close'], look_back=60):
    """دریافت داده از yfinance، محاسبه شاخص‌های تکنیکال، نرمال‌سازی و ایجاد توالی‌های زمانی."""
    # (خط 12)
    df = yf.download(ticker, start=start, end=end)
    
    # --- شروع تغییرات ---
    # هدف: مطمئن شویم که ستون نهایی برای قیمت تعدیل شده، "Adj_Close" نام دارد.
    
    # 1. اگر ستون قدیمی 'Adj Close' وجود دارد، آن را به 'Adj_Close' تغییر نام دهید
    if 'Adj Close' in df.columns:
        df.rename(columns={'Adj Close':'Adj_Close'}, inplace=True)
    
    # 2. اگر 'Adj Close' وجود ندارد (حالت پیش‌فرض جدید yfinance)، ستون 'Close' را به 'Adj_Close' تغییر نام دهید
    elif 'Close' in df.columns:
        df.rename(columns={'Close': 'Adj_Close'}, inplace=True)
    # --- پایان تغییرات ---

    # اطمینان از وجود ستون‌های لازم
    if 'Adj_Close' not in df.columns:
        raise ValueError("Adj_Close column not found for feature engineering.")
        
    df = df[features + ['Volume']] if 'Volume' not in features else df[features]
    
    # محاسبه شاخص‌های تکنیکال (MA21, MA50, RSI)
    df['MA21'] = df['Adj_Close'].rolling(21).mean()
    df['MA50'] = df['Adj_Close'].rolling(50).mean()
    delta = df['Adj_Close'].diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    roll_up = up.rolling(14).mean()
    roll_down = down.rolling(14).mean()
    df['RSI'] = 100 - (100 / (1 + roll_up / roll_down))
    
    df.dropna(inplace=True)
    scaler = MinMaxScaler()
    scaled = scaler.fit_transform(df.values)
    
    # ایجاد توالی‌های آموزشی (Sequence Creation)
    X, y = [], []
    for i in range(look_back, len(scaled)):
        X.append(scaled[i-look_back:i])
        y.append(scaled[i, 0]) # فرض بر این است که Adj_Close اولین ستون است
        
    return np.array(X), np.array(y), scaler, df.index[look_back:]

# (بقیه توابع build_mlp، build_rnn و ...)
# ...
# ...
# ...
# MODELS = { ... }
