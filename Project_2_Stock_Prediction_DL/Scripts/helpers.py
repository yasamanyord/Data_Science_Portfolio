import yfinance as yf
import numpy as np
import matplotlib.pyplot as plt
from sklearn.preprocessing import MinMaxScaler
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense

# -----------------------------
# 1. دریافت داده
# -----------------------------
def get_data(ticker, period="2y"):
    data = yf.download(ticker, period=period)
    return data[['Close']]

# -----------------------------
# 2. ساخت دیتاست
# -----------------------------
def create_dataset(series, time_step=60):
    X, y = [], []
    for i in range(len(series)-time_step-1):
        X.append(series[i:(i+time_step), 0])
        y.append(series[i+time_step, 0])
    return np.array(X), np.array(y)

# -----------------------------
# 3. آموزش مدل
# -----------------------------
def train_model(df, time_step=60, epochs=10):
    scaler = MinMaxScaler(feature_range=(0,1))
    scaled_data = scaler.fit_transform(df)

    # تقسیم آموزش و تست
    train_size = int(len(scaled_data)*0.8)
    train_data, test_data = scaled_data[:train_size], scaled_data[train_size-time_step:]

    # آماده‌سازی داده‌ها
    X_train, y_train = create_dataset(train_data, time_step)
    X_test, y_test = create_dataset(test_data, time_step)

    X_train = X_train.reshape(X_train.shape[0], X_train.shape[1], 1)
    X_test = X_test.reshape(X_test.shape[0], X_test.shape[1], 1)

    # ساخت مدل
    model = Sequential()
    model.add(LSTM(50, return_sequences=True, input_shape=(time_step, 1)))
    model.add(LSTM(50))
    model.add(Dense(1))
    model.compile(loss="mean_squared_error", optimizer="adam")

    # آموزش
    model.fit(X_train, y_train, epochs=epochs, batch_size=32, verbose=1)

    # پیش‌بینی روی داده تست
    y_pred = model.predict(X_test)

    # برگردوندن مقیاس
    y_test_rescaled = scaler.inverse_transform(y_test.reshape(-1,1))
    y_pred_rescaled = scaler.inverse_transform(y_pred)

    # نمودار مقایسه
    plt.figure(figsize=(12,6))
    plt.plot(y_test_rescaled, label="قیمت واقعی")
    plt.plot(y_pred_rescaled, label="قیمت پیش‌بینی شده")
    plt.title(f"مقایسه پیش‌بینی و واقعیت")
    plt.xlabel("روزها")
    plt.ylabel("قیمت")
    plt.legend()
    plt.show(block=False)   # 🔹 ادامه کد بعد از نمایش نمودار اجرا میشه

    return model, scaler, df, time_step

# -----------------------------
# 4. پیش‌بینی روز بعد
# -----------------------------
def predict_next_day(model, scaler, df, time_step=60):
    last_data = df[-time_step:].values
    scaled_last = scaler.transform(last_data)
    X_input = scaled_last.reshape(1, time_step, 1)
    pred_scaled = model.predict(X_input)
    pred = scaler.inverse_transform(pred_scaled)
    return float(pred[0][0])

# -----------------------------
# 5. اجرای کل پروژه برای چند نماد
# -----------------------------
if __name__ == "__main__":
    tickers = ["AAPL", "TSLA", "MSFT"]  # می‌تونی هر تعداد نماد اضافه کنی

    for ticker in tickers:
        print(f"\n🟢 شروع پردازش برای {ticker} ...")
        df = get_data(ticker)
        model, scaler, df, time_step = train_model(df, epochs=200)
        tomorrow_price = predict_next_day(model, scaler, df, time_step)
        print(f"📈 پیش‌بینی قیمت فردا برای {ticker}: {tomorrow_price:.2f} دلار")
    # نمایش نمودار تا وقتی کاربر ببنده
    plt.show()  
