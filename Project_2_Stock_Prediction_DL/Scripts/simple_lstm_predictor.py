import yfinance as yf
import numpy as np
import matplotlib.pyplot as plt
from sklearn.preprocessing import MinMaxScaler
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense
import warnings

warnings.filterwarnings('ignore')

# -----------------------------
# 1. دریافت داده
# -----------------------------
def get_data(ticker, period="2y"):
    """داده‌های تاریخی سهام را دریافت می‌کند و فقط ستون Close را برمی‌گرداند."""
    # استفاده از auto_adjust=True برای اطمینان از دریافت قیمت‌های تعدیل شده
    # این کار ناسازگاری‌های yfinance با Adj Close را رفع می‌کند.
    data = yf.download(ticker, period=period, auto_adjust=True)
    if 'Close' not in data.columns:
        raise ValueError("ستون 'Close' در داده‌های دانلود شده پیدا نشد.")
    return data[['Close']]

# -----------------------------
# 2. ساخت دیتاست
# -----------------------------
def create_dataset(series, time_step=60):
    """
    توالی‌های زمانی (Sliding Window) را برای آموزش مدل LSTM ایجاد می‌کند.
    """
    X, y = [], []
    # len(series) - time_step - 1 : اطمینان از اینکه آخرین عنصر برای y وجود دارد
    for i in range(len(series) - time_step - 1):
        X.append(series[i:(i + time_step), 0])
        y.append(series[i + time_step, 0])
    return np.array(X), np.array(y)

# -----------------------------
# 3. آموزش مدل و ارزیابی
# -----------------------------
def train_model(df, time_step=60, epochs=100):
    print(f"--- شروع آموزش با {epochs} دوره ---")
    
    # 1. نرمال‌سازی داده‌ها (Scaler فقط روی یک ستون Close آموزش می‌بیند)
    scaler = MinMaxScaler(feature_range=(0,1))
    scaled_data = scaler.fit_transform(df)

    # 2. تقسیم آموزش و تست: داده‌های تست باید شامل یک window کامل قبل از شروع باشند
    train_size = int(len(scaled_data)*0.8)
    train_data = scaled_data[:train_size]
    # تست از train_size-time_step شروع می‌شود تا بتوان اولین پیش‌بینی را انجام داد
    test_data = scaled_data[train_size - time_step:]

    # 3. آماده‌سازی داده‌ها
    X_train, y_train = create_dataset(train_data, time_step)
    X_test, y_test = create_dataset(test_data, time_step)

    # تبدیل شکل داده‌ها به فرمت مورد نیاز LSTM: [Samples, Timesteps, Features]
    X_train = X_train.reshape(X_train.shape[0], X_train.shape[1], 1)
    X_test = X_test.reshape(X_test.shape[0], X_test.shape[1], 1)

    # 4. ساخت مدل (Stacked LSTM)
    model = Sequential()
    # input_shape=(time_step, 1) چون فقط 1 ویژگی (Close Price) داریم
    model.add(LSTM(50, return_sequences=True, input_shape=(time_step, 1)))
    model.add(LSTM(50))
    model.add(Dense(1))
    model.compile(loss="mean_squared_error", optimizer="adam")

    # 5. آموزش
    model.fit(X_train, y_train, epochs=epochs, batch_size=32, verbose=0)
    print("--- آموزش به پایان رسید. ---")

    # 6. پیش‌بینی
    y_pred = model.predict(X_test, verbose=0)

    # 7. برگردوندن مقیاس (چون scaler فقط 1 ستون دارد، نیازی به آرایه ساختگی 8 ستونی نیست)
    # y_test.reshape(-1, 1) تضمین می‌کند که 2 بُعد دارد
    y_test_rescaled = scaler.inverse_transform(y_test.reshape(-1,1))
    y_pred_rescaled = scaler.inverse_transform(y_pred)
    
    # محاسبه RMSE برای ارزیابی
    from sklearn.metrics import mean_squared_error
    rmse = np.sqrt(mean_squared_error(y_test_rescaled, y_pred_rescaled))

    # 8. نمودار مقایسه
    plt.figure(figsize=(12,6))
    plt.plot(y_test_rescaled, label="قیمت واقعی")
    plt.plot(y_pred_rescaled, label="قیمت پیش‌بینی شده")
    plt.title(f"مقایسه پیش‌بینی و واقعیت (RMSE: {rmse:.2f})")
    plt.xlabel("روزها")
    plt.ylabel("قیمت")
    plt.legend()
    plt.grid(True)
    plt.show(block=False) 

    return model, scaler, df, time_step, rmse

# -----------------------------
# 4. پیش‌بینی روز بعد
# -----------------------------
def predict_next_day(model, scaler, df, time_step=60):
    """قیمت روز بعد را بر اساس آخرین time_step روز پیش‌بینی می‌کند."""
    # 1. گرفتن آخرین پنجره زمانی
    last_data = df[-time_step:].values 
    
    # 2. مقیاس‌بندی
    scaled_last = scaler.transform(last_data)
    
    # 3. تغییر شکل برای ورودی مدل
    X_input = scaled_last.reshape(1, time_step, 1)
    
    # 4. پیش‌بینی
    pred_scaled = model.predict(X_input, verbose=0)
    
    # 5. برگرداندن مقیاس
    pred = scaler.inverse_transform(pred_scaled)
    
    return float(pred[0][0])

# -----------------------------
# 5. اجرای کل پروژه
# -----------------------------
if __name__ == "__main__":
    tickers = ["AAPL", "TSLA", "MSFT"] 
    results = {}
    
    # 🔹 برای اینکه تمام نمودارها همزمان نمایش داده شوند، epochs را کمتر می‌کنیم (مثلاً 100)
    # 🔹 در صورتی که نیاز به آموزش عمیق‌تر دارید، می‌توانید epochs را به 200 یا بالاتر افزایش دهید.
    
    for ticker in tickers:
        try:
            print(f"\n=============================================")
            print(f"🟢 شروع پردازش برای {ticker}...")
            
            df = get_data(ticker)
            model, scaler, df, time_step, rmse = train_model(df, epochs=100)
            tomorrow_price = predict_next_day(model, scaler, df, time_step)
            
            results[ticker] = {'RMSE': rmse, 'Prediction': tomorrow_price}
            
            print(f"📈 پیش‌بینی قیمت فردا برای {ticker}: {tomorrow_price:.2f} دلار")
            print(f"✅ ارزیابی موفق: RMSE مدل {rmse:.2f}")

        except Exception as e:
            print(f"❌ خطایی در پردازش {ticker} رخ داد: {e}")

    print("\n=============================================")
    print("جمع‌بندی نتایج:")
    for ticker, res in results.items():
        print(f"- {ticker}: پیش‌بینی فردا: ${res['Prediction']:.2f} | RMSE: {res['RMSE']:.2f}")
        
    # نگه داشتن نمودارها تا زمانی که کاربر آن‌ها را ببندد
    if plt.get_fignums():
        print("\nنمودارها باز هستند. پنجره‌ها را ببندید تا برنامه خاتمه یابد.")
        plt.show()
