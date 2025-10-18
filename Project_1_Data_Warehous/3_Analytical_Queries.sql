-- فایل: 3_Analytical_Queries.sql
-- پرس و جوهای تحلیلی بر روی انبار داده فروش مبلمان

-- ******************************************************
-- پرس‌وجو 1: مقدار، مجموع درآمد و تخفیف را با توجه به هر شهر، نوع مبلمان و ماه پیدا کنید.
-- ******************************************************
SELECT C.City, F.Type, T.Month,
       SUM(S.Quantity) AS Total_Quantity,
       SUM(S.Income) AS Total_Income,
       SUM(S.Discount) AS Total_Discount
FROM Sales S
JOIN Customer C ON S.IdCustomer = C.IdCustomer
JOIN Time T ON S.IdTime = T.IdTime
JOIN Furniture F ON S.IdFurniture = F.IdFurniture
GROUP BY 1, 2, 3 -- استفاده از شماره ستون برای GROUP BY
ORDER BY T.Month, C.City, F.Type;

-- ******************************************************
-- پرس‌وجو 2: میانگین مقدار، درآمد و تخفیف را با توجه به هر کشور، جنس مبلمان و سال پیدا کنید.
-- ******************************************************
SELECT C.Country, F.Material, T.Year,
       AVG(S.Quantity) AS Avg_Quantity,
       AVG(S.Income) AS Avg_Income,
       AVG(S.Discount) AS Avg_Discount
FROM Sales S
JOIN Customer C ON S.IdCustomer = C.IdCustomer
JOIN Time T ON S.IdTime = T.IdTime
JOIN Furniture F ON S.IdFurniture = F.IdFurniture
GROUP BY C.Country, F.Material, T.Year
ORDER BY T.Year, C.Country, F.Material;

-- ******************************************************
-- پرس‌وجو 3: 5 مورد از پرفروش‌ترین مبلمان (بر اساس Quantity) را در طول ماه مِی (May) مشخص کنید.
-- از تابع پنجره‌ای RANK() استفاده می‌شود.
-- ******************************************************
WITH MaySalesRank AS (
    SELECT F.Type,
           SUM(S.Quantity) AS Total_Quantity,
           RANK() OVER (ORDER BY SUM(S.Quantity) DESC) AS Sales_Rank
    FROM Sales S
    JOIN Time T ON S.IdTime = T.IdTime
    JOIN Furniture F ON S.IdFurniture = F.IdFurniture
    WHERE T.Month = 'May' -- فیلتر ماه مِی
    GROUP BY F.Type -- مجموع فروش برای هر نوع مبلمان
)
SELECT Type, Total_Quantity
FROM MaySalesRank
WHERE Sales_Rank <= 5
ORDER BY Sales_Rank;
