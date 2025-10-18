import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import joblib
from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint
from helpers import fetch_and_prepare, evaluate, MODELS # فراخوانی توابع از helpers.py

# تنظیمات اصلی [cite: 110, 161]
TICKER = 'AAPL' # نماد سهام مورد بررسی
LOOK_BACK = 60  # طول پنجره زمانی (توالی)
EPOCHS = 200    # تعداد دوره آموزش
FEATURES = ['Open', 'High', 'Low', 'Adj_Close'] # ویژگی‌های ورودی [cite: 101]

def run_single_experiment(model_name, X_train, y_train, X_test, y_test, scaler, time_step, n_features):
    """تابع آموزش و ارزیابی یک مدل خاص."""
    
    # ساخت مدل با استفاده از دیکشنری MODELS از helpers [cite: 111, 117]
    model_builder = MODELS[model_name]
    model = model_builder(time_step, n_features)

    # Callbacks: EarlyStopping و ModelCheckpoint [cite: 118]
    es = EarlyStopping(monitor='val_loss', patience=8, restore_best_weights=True)
    mc = ModelCheckpoint(f'./Models/{model_name}_best_model.h5', save_best_only=True, monitor='val_loss')
    
    print(f"\n--- شروع آموزش مدل: {model_name} ---")
    
    # آموزش مدل [cite: 117]
    model.fit(
        X_train, y_train,
        validation_split=0.1, # 10% برای اعتبارسنجی [cite: 110]
        epochs=EPOCHS, 
        batch_size=32, 
        callbacks=[es, mc], 
        verbose=0 # نمایش خلاصه نتایج آموزش
    )
    
    # پیش‌بینی روی داده تست
    y_pred_scaled = model.predict(X_test)
    
    # برگرداندن مقیاس (Inverse Transform) [cite: 152]
    # reshape(-1, 1) برای تبدیل به آرایه‌ی دو بعدی مورد نیاز scaler
    y_test_rescaled = scaler.inverse_transform(y_test.reshape(-1, 1))
    y_pred_rescaled = scaler.inverse_transform(y_pred_scaled)

    # ارزیابی نتایج
    metrics = evaluate(y_test_rescaled, y_pred_rescaled)
    
    return metrics, y_test_rescaled, y_pred_rescaled, model

def main():
    
    # ۱. جمع‌آوری، پیش‌پردازش و ایجاد توالی‌ها
    print(f"در حال پردازش داده‌ها برای نماد {TICKER} با look_back={LOOK_BACK}...")
    # فرض بر استفاده از یک بازه زمانی طولانی برای آموزش مؤثر [cite: 101]
    X, y, scaler, dates = fetch_and_prepare(
        TICKER, start='2015-01-01', end='2023-12-31', 
        features=FEATURES, look_back=LOOK_BACK
    )
    
    # تقسیم داده‌ها به آموزش و تست (80% آموزش، 20% تست) [cite: 151]
    train_size = int(len(X) * 0.8)
    X_train, X_test = X[:train_size], X[train_size:]
    y_train, y_test = y[:train_size], y[train_size:]
    
    n_features = X.shape[2] # تعداد ویژگی‌های ورودی

    all_results = []
    
    # ۲. اجرای تمام مدل‌ها و مقایسه
    for model_name in MODELS.keys():
        metrics, y_true, y_pred, model = run_single_experiment(
            model_name, X_train, y_train, X_test, y_test, scaler, LOOK_BACK, n_features
        )
        
        # ذخیره نتایج
        all_results.append({
            'Model': model_name,
            'RMSE': metrics['RMSE'],
            'MAE': metrics['MAE'],
            'MAPE': metrics['MAPE'],
            'DirAcc': metrics['DirAcc']
        })
        print(f"نتایج {model_name}: RMSE={metrics['RMSE']:.3f}, DirAcc={metrics['DirAcc']:.1f}%")

    # ۳. ذخیره نتایج و مدل برتر
    results_df = pd.DataFrame(all_results)
    results_df.to_csv('./Results/comparison_results.csv', index=False)
    print("\nنتایج مقایسه‌ای در Results/comparison_results.csv ذخیره شد.")

    # ذخیره مدل برتر (LSTM Advanced) و Scaler برای پیش‌بینی روز بعد [cite: 118, 171]
    lstm_adv_model = MODELS['LSTM Advanced'](LOOK_BACK, n_features)
    lstm_adv_model.load_weights(f'./Models/LSTM Advanced_best_model.h5')
    joblib.dump(scaler, './Models/scaler.pkl')

    # ۴. ترسیم نمودار مدل برتر برای نمایش در README
    metrics, y_true, y_pred, _ = run_single_experiment(
            'LSTM Advanced', X_train, y_train, X_test, y_test, scaler, LOOK_BACK, n_features # فقط برای گرفتن y_true و y_pred نهایی
        )

    plt.figure(figsize=(14, 7))
    plt.plot(y_true, label="قیمت واقعی", color='blue')
    plt.plot(y_pred, label="قیمت پیش‌بینی شده", color='red', linestyle='--')
    plt.title(f"مقایسه قیمت واقعی و پیش‌بینی شده - مدل LSTM Advanced برای {TICKER}") [cite: 152]
    plt.xlabel("روزها") [cite: 153]
    plt.ylabel("قیمت (دلار)") [cite: 153]
    plt.legend()
    plt.savefig('./Results/lstm_prediction_plot.png')
    # plt.show()
    print("نمودار مقایسه مدل برتر در Results/lstm_prediction_plot.png ذخیره شد.")

if __name__ == "__main__":
    main()
