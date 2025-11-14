# alx-project-nexus



Mercacorl
A Full-Featured E-Commerce Auction Platform
Alx Prodev Backend Nexus Project: Final Project

Project Title
Mercacorl – An eBay-Style Online Auction Marketplace with Virtual Currency (COINS)

Project Overview
Mercacorl is a robust, secure, and scalable e-commerce auction platform built using Django and Django REST Framework. It combines traditional shopping cart functionality with a real-time proxy bidding system similar to eBay, using a virtual currency called COINS for all transactions.
The system supports role-based access (Customer, Vendor, Admin), atomic bid processing, race-condition-safe transactions, and automated auction lifecycle management.


## 🌟 System Key Features

| Feature | Description |
| :--- | :--- |
| **User Roles** | Customer, Vendor, and Admin (Staff) roles with distinct permissions for data access and actions. |
| **Product & Auction Management** | Vendors can create and manage products for sale, including auctions with defined **start/end times** and **reserve prices**. |
| **Proxy Bidding** | Users set a `max_bid`, and the system automatically bids incrementally on their behalf up to that maximum. |
| **Live Current Bid** | Real-time visibility of the highest current bid on active auctions. |
| **COINS Payment System** | A virtual currency used for payments, implemented with **atomic transactions** (`select_for_update()`) to safely deduct funds and prevent race conditions. |
| **Shopping Cart & Checkout** | Standard cart management flow, allowing users to consolidate items and define a **shipping address** before placing an order. |
| **Order Management** | Comprehensive system for order creation, status tracking (e.g., PENDING, PAID, SHIPPED), and restricted modification based on status/role. |
| **Secure API** | Uses **JWT/Session authentication**, enforces **ownership checks** (users only access their own data), and protects fields using **read-only** restrictions. |
| **Atomic Bidding** | Utilizes database concurrency control (`select_for_update()`) to lock records during bidding, ensuring a fair and reliable process where race conditions are eliminated. |
| **Admin Panel** | Full **Create, Read, Update, Delete (CRUD)** capabilities for administrators via the integrated Django Admin interface. |


## 💻 Technology Stack

| Layer | Technology |
| :--- | :--- |
| **Backend** | Python, Django, Django REST Framework |
| **Database** | PostgreSQL |
| **Task Queue** | Celery + Redis |
| **Authentication** | Session-based / JWT-ready |
| **API** | RESTful JSON |
| **Deployment** | Gunicorn, Nginx |

---

## 🌟 Key Features

| Feature | Description |
| :--- | :--- |
| **User Roles** | Customer, Vendor, and Admin (Staff) roles with distinct permissions for data access and actions. |
| **Product & Auction Management** | Vendors create and manage auctions with defined **start/end times** and **reserve prices**. |
| **Proxy Bidding** | Users set a `max_bid`, and the system automatically bids incrementally on their behalf up to that maximum. |
| **Atomic Bidding** | Uses database concurrency control (`select_for_update()`) to lock records, ensuring a fair process where race conditions are eliminated. |
| **COINS Payment System** | Virtual currency implemented with atomic transactions for safe fund deduction. |
| **Shopping Cart & Checkout** | Standard cart flow with item consolidation and shipping address definition. |
| **Order Management** | Comprehensive system for creation, status tracking (PENDING, PAID, SHIPPED), and restricted modification. |
| **Secure API** | Enforces JWT/Session authentication, ownership checks, and read-only restrictions. |
| **Admin Panel** | Full Create, Read, Update, Delete (CRUD) capabilities via the Django Admin interface. |



## API Endpoints

| Method       | Endpoint                            | Description                            | Access              |
|--------------|-------------------------------------|----------------------------------------|---------------------|
| GET          | `/api/auctions/`                    | List all active auctions               | Public              |
| POST         | `/api/auctions/`                    | Create new auction                     | Vendor only         |
| GET          | `/api/auctions/{id}/`               | Retrieve auction details               | Public              |
| PUT/PATCH    | `/api/auctions/{id}/`               | Update auction (before start)          | Owner (Vendor)      |
| DELETE       | `/api/auctions/{id}/`               | Cancel auction                         | Owner (Vendor)      |
| POST         | `/api/bids/`                        | Place a proxy bid                      | Authenticated       |
| GET          | `/api/bids/`                        | View my bid history                    | Authenticated       |
| GET/POST     | `/api/products/`                    | List & create vendor products          | Vendor + Staff      |
| GET/PUT/DELETE | `/api/products/{id}/`             | Manage own product                     | Owner (Vendor)      |
| GET/POST     | `/api/cart/`                        | View & add to cart                     | Authenticated       |
| PUT/DELETE   | `/api/cart/items/{id}/`             | Update/remove cart item                | Authenticated       |
| POST         | `/api/checkout/`                    | Create order from cart                 | Authenticated       |
| GET          | `/api/orders/`                      | List my orders                         | Authenticated       |
| GET          | `/api/orders/{id}/`                 | View order details                     | Owner + Vendor + Staff |
| GET/POST     | `/api/addresses/`                   | List & add shipping addresses          | Authenticated       |
| PUT/DELETE   | `/api/addresses/{id}/`              | Update/delete address                  | Owner               |
| POST         | `/api/payments/`                    | Pay with COINS                         | Authenticated       |
































Author
Edoh Mensah Akpedzene
Institution: ALX
Program: B.Sc. Computer Science
Nexus Poroject Cohort 7 (2025)

AuctionBay – Secure, Scalable, eBay-Ready.