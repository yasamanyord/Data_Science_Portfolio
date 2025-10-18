import numpy as np
import pandas as pd
import yfinance as yf
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Flatten, SimpleRNN, GRU, LSTM, Dropout

# تابع پیش‌پردازش داده و مهندسی ویژگی [cite: 107, 163]
def fetch_and_prepare(ticker, start, end, features=['Adj_Close'], look_back=60):
    """دریافت داده از yfinance، محاسبه شاخص‌های تکنیکال، نرمال‌سازی و ایجاد توالی‌های زمانی."""
    df = yf.download(ticker, start=start, end=end)
    if 'Adj Close' in df.columns:
        df.rename(columns={'Adj Close':'Adj_Close'}, inplace=True)
    
    # اطمینان از وجود ستون‌های لازم برای محاسبه شاخص‌ها
    if 'Adj_Close' not in df.columns:
        raise ValueError("Adj_Close column not found for feature engineering.")
        
    df = df[features + ['Volume']] if 'Volume' not in features else df[features]
    
    # محاسبه شاخص‌های تکنیکال (MA21, MA50, RSI) [cite: 107, 108, 163]
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
    
    # ایجاد توالی‌های آموزشی (Sequence Creation) [cite: 106]
    X, y = [], []
    for i in range(look_back, len(scaled)):
        X.append(scaled[i-look_back:i])
        y.append(scaled[i, 0]) # فرض بر این است که Adj_Close اولین ستون است [cite: 164]
        
    return np.array(X), np.array(y), scaler, df.index[look_back:]

# تابع ارزیابی مدل [cite: 110, 165]
def evaluate(y_true, y_pred):
    """محاسبه معیارهای RMSE, MAE, MAPE و Directional Accuracy."""
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    mae = mean_absolute_error(y_true, y_pred)
    mape = np.mean(np.abs((y_true - y_pred) / y_true)) * 100
    
    # Directional Accuracy [cite: 165]
    # محاسبه اختلاف قیمت روز بعد و قیمت امروز برای واقعی و پیش‌بینی
    y_true_diff = np.diff(y_true, axis=0) 
    y_pred_diff = np.diff(y_pred, axis=0)
    dir_acc = np.mean(np.sign(y_true_diff) == np.sign(y_pred_diff)) * 100

    return {'RMSE': rmse, 'MAE': mae, 'MAPE': mape, 'DirAcc': dir_acc}

# تابع ساخت مدل MLP [cite: 115, 167]
def build_mlp(time_step, n_features):
    model = Sequential()
    model.add(Flatten(input_shape=(time_step, n_features)))
    model.add(Dense(128, activation='relu'))
    model.add(Dense(64, activation='relu'))
    model.add(Dense(1))
    model.compile(optimizer='adam', loss='mse')
    return model

# تابع ساخت مدل Simple RNN [cite: 116, 167]
def build_rnn(time_step, n_features):
    model = Sequential()
    model.add(SimpleRNN(50, input_shape=(time_step, n_features)))
    model.add(Dense(1))
    model.compile(optimizer='adam', loss='mse')
    return model

# تابع ساخت مدل GRU [cite: 116, 168]
def build_gru(time_step, n_features):
    model = Sequential()
    model.add(GRU(50, return_sequences=True, input_shape=(time_step, n_features)))
    model.add(GRU(50))
    model.add(Dense(1))
    model.compile(optimizer='adam', loss='mse')
    return model

# تابع ساخت مدل LSTM ساده [cite: 117, 169]
def build_lstm_simple(time_step, n_features):
    model = Sequential()
    model.add(LSTM(50, input_shape=(time_step, n_features)))
    model.add(Dense(1))
    model.compile(optimizer='adam', loss='mse')
    return model

# تابع ساخت مدل LSTM پیشرفته (Stacked with Dropout) [cite: 117, 169]
def build_lstm_advanced(time_step, n_features):
    model = Sequential()
    model.add(LSTM(100, return_sequences=True, input_shape=(time_step, n_features)))
    model.add(Dropout(0.2))
    model.add(LSTM(100))
    model.add(Dropout(0.2))
    model.add(Dense(1))
    model.compile(optimizer='adam', loss='mse')
    return model

# دیکشنری نگه‌دارنده مدل‌ها
MODELS = {
    'MLP': build_mlp,
    'RNN': build_rnn,
    'GRU': build_gru,
    'LSTM Simple': build_lstm_simple,
    'LSTM Advanced': build_lstm_advanced
}
