# Data model

A star schema with `fact_sales` at the centre. All four relationships are one-to-many, with the dimension on the "one" side.

```mermaid
erDiagram
  dim_customer ||--o{ fact_sales : "customer_id"
  dim_product ||--o{ fact_sales : "product_id"
  dim_region ||--o{ fact_sales : "region_id"
  dim_date ||--o{ fact_sales : "order_date = date"
  fact_sales {
    string order_id PK
    string order_date FK
    string customer_id FK
    string product_id FK
    string region_id FK
    int quantity
    float discount
    float sales_amount
    float cost_amount
    float profit
    bool is_return
    bool is_invalid_date
  }
  dim_customer {
    string customer_id PK
    string customer_name
    string gender
    int age
    string customer_segment
    date signup_date
  }
  dim_product {
    string product_id PK
    string product_name
    string category
    string sub_category
    float cost
    float selling_price
  }
  dim_region {
    string region_id PK
    string state
    string city
    string region
  }
  dim_date {
    int date_key PK
    date date
    int day
    int month
    string month_name
    int quarter
    int year
  }
```

## fact_sales (24,905 rows)

Grain: one row per order, and each order has one product.

| Column | Meaning |
|---|---|
| order_id | Primary key |
| order_date | `YYYY-MM-DD`, joins to `dim_date.date`. Blank for the 10 invalid dates |
| customer_id, product_id, region_id | Keys to the dimensions, never blank in this table |
| quantity | Units ordered. Negative for returns |
| discount | Fraction of list price, 0 to 0.20 |
| sales_amount | Revenue after discount. Negative for returns |
| cost_amount | Cost of goods sold |
| profit | Profit as supplied by the source |
| is_return | True when quantity is negative (15 rows) |
| is_invalid_date | True when the source date was not a valid date (10 rows) |

## dim_customer (2,000 rows)

| Column | Meaning |
|---|---|
| customer_id | Primary key |
| customer_name | Generic name, no analytical value |
| gender | Male, Female or Other |
| age | 18 to 65 |
| customer_segment | Consumer, Corporate or Small Business |
| signup_date | Corrected so it never falls after the customer's first order |

## dim_product (100 rows)

| Column | Meaning |
|---|---|
| product_id | Primary key |
| product_name | Product name |
| category | One of five standardized categories |
| sub_category | 15 sub-categories, each under exactly one category |
| cost, selling_price | List cost and list price per unit |

## dim_region (20 rows)

| Column | Meaning |
|---|---|
| region_id | Primary key |
| state | State name |
| city | Placeholder (state name plus "City") |
| region | North, South, East, West or Central |

## dim_date (731 rows)

| Column | Meaning |
|---|---|
| date_key | Primary key, integer `YYYYMMDD` |
| date | `YYYY-MM-DD` |
| day, month, quarter, year | Calendar parts |
| month_name | January to December |
