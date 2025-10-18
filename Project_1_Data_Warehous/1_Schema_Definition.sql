-- فایل: 1_Schema_Definition.sql
-- ایجاد شمای ستاره (Star Schema) برای انبار داده فروش مبلمان عمده فروشی

-- 1. جدول بعد: Time (زمان)
CREATE TABLE Time (
    IdTime INT PRIMARY KEY,
    Day INT NOT NULL,
    Month VARCHAR(10) NOT NULL, -- مثلاً 'January', 'May'
    Year INT NOT NULL
);

-- 2. جدول بعد: Furniture (مبلمان)
CREATE TABLE Furniture (
    IdFurniture INT PRIMARY KEY,
    Type VARCHAR(50) NOT NULL,    -- صندلی، میز، کمد
    Category VARCHAR(50) NOT NULL, -- آشپزخانه، اتاق نشیمن، اداری
    Material VARCHAR(50) NOT NULL  -- چوب، مرمر، فلز
);

-- 3. جدول بعد: Customer (مشتری)
-- ستون Country (کشور) برای اجرای کوئری 2 اضافه شده است.
CREATE TABLE Customer (
    IdCustomer INT PRIMARY KEY,
    Age INT,
    Sex CHAR(1), -- 'M' یا 'F'
    City VARCHAR(50) NOT NULL,
    Region VARCHAR(50) NOT NULL,
    State VARCHAR(50) NOT NULL, -- استان (معادل State)
    Country VARCHAR(50) NOT NULL -- کشور (جدید برای کوئری 2)
);

-- 4. جدول حقیقت: Sales (فروش)
CREATE TABLE Sales (
    IdSale INT PRIMARY KEY, -- کلید اصلی مصنوعی برای هر تراکنش
    IdFurniture INT NOT NULL,
    IdCustomer INT NOT NULL,
    IdTime INT NOT NULL,
    Quantity INT NOT NULL,  -- معیار: مقدار
    Income DECIMAL(10, 2) NOT NULL, -- معیار: درآمد
    Discount DECIMAL(10, 2) NOT NULL, -- معیار: تخفیف

    -- تعریف کلیدهای خارجی
    FOREIGN KEY (IdFurniture) REFERENCES Furniture(IdFurniture),
    FOREIGN KEY (IdCustomer) REFERENCES Customer(IdCustomer),
    FOREIGN KEY (IdTime) REFERENCES Time(IdTime)
);
