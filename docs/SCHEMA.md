# Django Database Schema

Django migrations under `django_store/store/migrations` define the store tables. Django's built-in authentication, session, and admin migrations define the framework tables.

```mermaid
erDiagram
    CATEGORY ||--o{ PRODUCT : classifies
    PRODUCT ||--o{ PRODUCT_IMAGE : has
    ORDER ||--|{ ORDER_ITEM : contains
    PRODUCT ||--o{ ORDER_ITEM : sold_as
    USER ||--o{ ORDER : places
    USER ||--o| ACCOUNT_PROFILE : has
    USER ||--o{ CONTACT_MESSAGE : sends
    USER {
        int id PK
        varchar username UK
        varchar email UK
        varchar password
    }
    ACCOUNT_PROFILE {
        int id PK
        int user_id FK
        varchar avatar
    }
    CATEGORY {
        int id PK
        varchar name UK
    }
    PRODUCT {
        int id PK
        varchar name
        decimal price
        int stock
        int category_id FK
    }
    PRODUCT_IMAGE {
        int id PK
        int product_id FK
        varchar image
    }
    DISCOUNT {
        int id PK
        date date UK
        decimal amount
    }
    ORDER {
        int id PK
        int user_id FK
        decimal total
        text address
        decimal shipping_fee
        int status
    }
    ORDER_ITEM {
        int id PK
        int order_id FK
        int product_id FK
        varchar product_name
        int quantity
        decimal unit_price
        decimal subtotal
    }
```

## Notes

- Passwords use Django's password hashers and authentication framework.
- Product/order money fields use fixed-precision `DECIMAL`.
- Django ORM relations create database foreign keys. Order items retain the product name and unit price for historical display.
- SQLite is the default local database. The existing CodeIgniter database is not automatically imported by Django migrations; back up and plan a separate data migration before using old production data.