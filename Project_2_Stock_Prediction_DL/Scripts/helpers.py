import numpy as np
import pandas as pd
import yfinance as yf
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Flatten, SimpleRNN, GRU, LSTM, Dropout

# تابع پیش‌پردازش داده و مهندسی ویژگی
def fetch_and_prepare(ticker, start, end, features=['Adj_Close'], look_back=60):
    """
    دریافت داده از yfinance، رفع ناسازگاری ستون‌ها (MultiIndex و نام‌گذاری)،
    محاسبه شاخص‌های تکنیکال، نرمال‌سازی و ایجاد توالی‌های زمانی.
    """
    
    # 1. دانلود داده‌ها
    df = yf.download(ticker, start=start, end=end)
    
    # --- شروع اصلاحات ضروری برای رفع خطای MultiIndex و نام ستون‌ها ---
    
    # اگر ستون‌ها MultiIndex هستند، آن‌ها را به یک ایندکس ساده (Single-level Index) تبدیل کنید.
    # این کار خطای "Can only use .str accessor with Index, not MultiIndex" را رفع می‌کند.
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel()
    
    # استانداردسازی نام ستون‌ها (حذف فاصله و تبدیل به آندرسکور)
    df.columns = df.columns.str.replace(' ', '_')
    
    # 2. تضمین نام‌گذاری صحیح ستون هدف به 'Adj_Close'
    # در نسخه‌های جدید yfinance، 'Adj Close' حذف شده و 'Close' قیمت تعدیل شده است.
    if 'Close' in df.columns and 'Adj_Close' not in df.columns:
        df.rename(columns={'Close': 'Adj_Close'}, inplace=True)
    
    # --- پایان اصلاحات ---
    
    # بررسی نهایی برای اطمینان از وجود ستون کلیدی
    if 'Adj_Close' not in df.columns:
        raise ValueError(f"Adj_Close column not found for feature engineering. Columns found: {df.columns.tolist()}")
        
    
    # فیلتر کردن ستون‌ها بر اساس FEATURES و اطمینان از وجود ستون‌های لازم برای مهندسی ویژگی
    # (مثل Adj_Close و Volume)
    required_features = list(set(features) | set(['Adj_Close', 'Volume']))
    # فقط ستون‌هایی که در دیتافریم موجود هستند را انتخاب کنید
    df = df[[col for col in required_features if col in df.columns]]
    
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
    
    # تعیین ایندکس ستون هدف (Target Column Index)
    target_index = df.columns.get_loc('Adj_Close')
    
    # ایجاد توالی‌های آموزشی (Sequence Creation)
    X, y = [], []
    for i in range(look_back, len(scaled)):
        X.append(scaled[i-look_back:i])
        y.append(scaled[i, target_index]) # استفاده از ایندکس صحیح برای ستون هدف
        
    return np.array(X), np.array(y), scaler, df.index[look_back:]

# تابع ارزیابی مدل
def evaluate(y_true, y_pred):
    """محاسبه معیارهای RMSE, MAE, MAPE و Directional Accuracy."""
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    mae = mean_absolute_error(y_true, y_pred)
    epsilon = 1e-10 
    mape = np.mean(np.abs((y_true - y_pred) / (y_true + epsilon))) * 100
    
    # Directional Accuracy
    y_true_diff = np.diff(y_true, axis=0) 
    y_pred_diff = np.diff(y_pred, axis=0)
    dir_acc = np.mean(np.sign(y_true_diff) == np.sign(y_pred_diff)) * 100

    return {'RMSE': rmse, 'MAE': mae, 'MAPE': mape, 'DirAcc': dir_acc}

# تابع ساخت مدل MLP
def build_mlp(time_step, n_features):
    model = Sequential()
    model.add(Flatten(input_shape=(time_step, n_features)))
    model.add(Dense(128, activation='relu'))
    model.add(Dense(64, activation='relu'))
    model.add(Dense(1))
    model.compile(optimizer='adam', loss='mse')
    return model

# تابع ساخت مدل Simple RNN
def build_rnn(time_step, n_features):
    model = Sequential()
    model.add(SimpleRNN(50, input_shape=(time_step, n_features)))
    model.add(Dense(1))
    model.compile(optimizer='adam', loss='mse')
    return model

# تابع ساخت مدل GRU
def build_gru(time_step, n_features):
    model = Sequential()
    model.add(GRU(50, return_sequences=True, input_shape=(time_step, n_features)))
    model.add(GRU(50))
    model.add(Dense(1))
    model.compile(optimizer='adam', loss='mse')
    return model

# تابع ساخت مدل LSTM ساده
def build_lstm_simple(time_step, n_features):
    model = Sequential()
    model.add(LSTM(50, input_shape=(time_step, n_features)))
    model.add(Dense(1))
    model.compile(optimizer='adam', loss='mse')
    return model

# تابع ساخت مدل LSTM پیشرفته (Stacked with Dropout)
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
