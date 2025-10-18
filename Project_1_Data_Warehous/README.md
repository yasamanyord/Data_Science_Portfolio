# 📦 Project 1: Wholesale Furniture Sales Data Warehouse

## 🎯 Project Objective
The primary goal of this project was to design and implement a robust Data Warehouse (DWH) leveraging the **Star Schema** dimensional model. This DWH is purpose-built to facilitate high-performance analytical reporting and deep Business Intelligence (BI) insights across key areas: product sales performance, customer demographics, and temporal trends.

## 📐 Data Warehouse Structure (Star Schema)
The architecture consists of a central Fact Table linked to several supporting Dimension Tables, ensuring denormalized, query-optimized data storage.

* **Fact Table: `Sales`**
    * **Metrics (Facts):** `Quantity`, `Income`, `Discount`.
    * **Foreign Keys:** `IdFurniture`, `IdCustomer`, `IdTime`. (Linking to Dimensions)
* **Dimension Tables (Dims):**
    1.  **`Furniture`:** Detailed product attributes (`Type`, `Category`, `Material`).
    2.  **`Customer`:** Customer attributes (`Age`, `Gender`, `City`, `Region`).
    3.  **`Time`:** Temporal attributes (`Day`, `Month`, `Year`, `Quarter`).

## 📄 Project Artifacts
* **`1_Schema_Definition.sql`**: Contains the Data Definition Language (DDL) scripts (`CREATE TABLE` commands) necessary to instantiate the four main tables of the DWH.
* **`2_Sample_Data_Inserts.sql`**: Provides Data Manipulation Language (DML) scripts (`INSERT` commands) to populate the warehouse with simulated sample data for testing and demonstration.
* **`3_Analytical_Queries.sql`**: Includes complex sample **SQL queries** to showcase analytical capability (e.g., calculating total revenue per customer segment, identifying the highest-margin product category by quarter).
