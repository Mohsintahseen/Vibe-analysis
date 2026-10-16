# Data quality and cleaning

Every finding below comes from inspecting the CSV files themselves. `scripts/clean_data.py` applies every treatment, and the row-level changes are logged in `data/logs/`.

## 1. Profiling summary

| File | Rows | Cols | Key | Foreign keys |
|---|---|---|---|---|
| orders_raw | 25,050 | 10 | `order_id` | `customer_id`, `product_id`, `region_id` |
| customers_raw | 2,010 | 6 | `customer_id` | none |
| products_raw | 100 | 6 | `product_id` | none |
| regions_raw | 20 | 4 | `region_id` | none |

Types as read: identifiers and names are text, `quantity` is an integer, `discount`, `sales_amount`, `cost_amount` and `profit` are decimals, and `age` is an integer. `order_date` loads as text because of the invalid values described below. Every customer, product and region appears in the orders, and no order points at a missing customer, product or region (apart from the blanks below).

## 2. Orders

| Check | Result |
|---|---|
| Exact duplicate rows | 50, all at the end of the file. The same `order_id` never appears with different content. |
| Blank `customer_id` | 60 |
| Blank `product_id` | 35 (no row is blank in both) |
| `order_date` = `not_a_date` | 10 |
| Date range of valid dates | 2024-01-01 to 2025-12-31, no future dates, midnight timestamps only |
| Discount values | 0, 0.05, 0.10, 0.15, 0.20 |
| Negative quantity | 15 (from -1 to -5) |
| Sales not equal to price x quantity x (1 - discount) | none among positive quantities |
| Cost not equal to product cost x quantity | the same 15 negative-quantity rows only |
| Sales below cost with a positive quantity | 571, every one at a 15% or 20% discount |

### Treatments

- **Duplicates:** the 50 copies are removed, keeping the first row.
- **Invalid dates:** the value is blanked and `is_invalid_date` is set. The row stays because its sales and profit are valid.
- **Blank customer or product ID:** the 95 rows are removed, since they cannot be attributed to a customer or product. They held $121,100 of sales and $26,642 of profit.
- **Returns:** `is_return` is true when quantity is negative. These rows are kept as supplied. Their profit does not equal sales minus cost, which is a known limitation.
- **Below-cost orders:** kept. They are real discounting outcomes. The thinnest list price is only about 14% above cost, so a 15% or 20% discount can push sales under cost.

### Row counts

| Step | Rows |
|---|---|
| Raw | 25,050 |
| After removing exact duplicates | 25,000 |
| After removing blank customer or product IDs | 24,905 (`fact_sales`) |

## 3. Customers

| Check | Result |
|---|---|
| Blank values, stray spaces, odd formats | none |
| Age | 18 to 65, no outliers |
| Gender | Male, Female, Other, no spelling variants |
| Segment | Consumer, Corporate, Small Business, no variants |
| Duplicate rows | 10 (same ID and identical content) |
| Orders placed before `signup_date` | 12,535 of 24,930 dated orders (50.3%), affecting 1,856 of 2,000 customers |

### Treatments

- **Duplicates:** the first row per `customer_id` is kept. The 10 removed rows are listed in `data/logs/customer_duplicates_log.csv`. 2,010 rows become 2,000.
- **Signup dates:** order dates and signup dates look independent in the source. The rule applied is that `signup_date` becomes the earlier of the recorded date and the customer's first valid order. 1,856 customers were adjusted, by 338 days on average and up to 727. The 144 others were already consistent. Every change is in `data/logs/customer_signup_adjustments_log.csv`.

Assumption: the order dates are the more reliable source, since a customer cannot buy before existing.

## 4. Products

| Check | Result |
|---|---|
| Duplicate IDs, blanks, cost at or above price | none |
| `category` with trailing space (`"Furniture "`) | 4 |
| `category` in lowercase (`electronics`) | 4 |
| `category` in uppercase (`OFFICE SUPPLIES`) | 4 |
| Category contradicts sub-category | the same 12 products |

### Treatments

1. Category names are trimmed and standardized to five values: Clothing, Electronics, Furniture, Home & Kitchen, Office Supplies.
2. Each sub-category maps to one category, taken from the category most of its products carry (for example Stationery sits under Office Supplies for 7 of its 11 products). The 12 products that disagree are corrected to it.

Assumption: the category is the corrupted field and the sub-category is right. Every product name matches its sub-category (`Stationery Product 1` is Stationery).

| Products | Was | Now |
|---|---|---|
| P0001, P0053, P0060 | Furniture | Office Supplies |
| P0011, P0002 | Electronics | Office Supplies |
| P0010 | Electronics | Home & Kitchen |
| P0022 | Electronics | Clothing |
| P0027, P0087 | Office Supplies | Clothing |
| P0037 | Office Supplies | Electronics |
| P0049 | Office Supplies | Furniture |
| P0096 | Furniture | Electronics |

These 12 products appear in about 11% of orders, so category totals from before the correction would differ.

## 5. Regions

No issues: no blanks, spaces, duplicates or case variants, a consistent `R###` ID format, and every state maps to one region (North 5, South 5, East 5, West 4, Central 1). The file is copied unchanged. The `city` column is a placeholder (the state name plus "City") and carries no real city detail.

## 6. Date dimension

`dim_date` holds one row per unique valid order date: 731 rows covering every day from 2024-01-01 to 2025-12-31 with no gaps. The 10 orders with no valid date have no match in it.

## 7. Assumptions

- Exact duplicates are load errors, not repeat orders.
- Negative quantities are returns.
- Profit equals sales minus cost, with discount reducing sales but not cost.
- All amounts are in one currency, which the source does not name.
