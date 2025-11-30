# alx-project-nexus

Mercacorl
A Full-Featured E-Commerce Auction Platform
Alx Prodev Backend Nexus Project: Final Project

---

Project Title
Mercacorl – Mercarol API – Marketplace & Auction System

---

Project Overview
Mercacorl is a robust, secure, and scalable e-commerce auction platform built using Django and Django REST Framework. It combines traditional shopping cart functionality with a real-time proxy bidding system similar to eBay, using a virtual currency called COINS for all transactions.
The system supports role-based access (Customer, Vendor, Admin), atomic bid processing, race-condition-safe transactions, and automated auction lifecycle management.



---


| Feature                          | Description                                                                                                                                                                      |
| :------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **User Roles**                   | Supports **Customer, Vendor, and Admin** roles with distinct permissions. Customers can bid and buy, Vendors can create/manage auctions, and Admins oversee the entire platform. |
| **Product & Auction Management** | Vendors can list products for sale and create auctions with **start/end times** and **reserve prices**. Admins can manage all products and auctions via the Django Admin panel.  |
| **Proxy Bidding**                | Users can set a `max_bid`, and the system automatically increases their bid incrementally up to that amount, ensuring a **real-time auction experience**.                        |
| **Live Current Bid**             | Displays the **highest current bid** on active auctions in real-time, so users can follow ongoing auctions.                                                                      |
| **COINS Virtual Currency**       | All transactions (bids and purchases) use **COINS**, a virtual currency. Funds are deducted safely using **atomic transactions** to prevent overspending or race conditions.     |
| **Shopping Cart & Checkout**     | Customers can add items to a cart, define **shipping addresses**, and complete purchases securely through the COINS payment system.                                              |
| **Order Management**             | Tracks order status (**PENDING, PAID, SHIPPED**) and restricts modifications based on role and current status for integrity.                                                     |
| **Secure API**                   | Enforces **JWT authentication**, **ownership checks** (users only access their own data), and **read-only fields** where necessary to protect sensitive data.                    |
| **Atomic Bidding**               | Ensures concurrency safety using database locks (`select_for_update()`), so simultaneous bids are processed fairly without conflicts.                                            |
| **Admin Panel**                  | Full **CRUD operations** for managing users, products, auctions, and orders through Django Admin.                                                                                |



---

## System Architecture 
- **Backend:** Django + Django REST Framework  
- **Database:** PostgreSQL (hosted on Neon)  
- **Task Queue & Caching:** Redis (via Redis Cloud)  
- **Task Scheduler:** Celery + Celery Beat  
- **Hosting:** Render (website), Fly.io (Celery worker)

---

## Key Features

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

---

## Database Models & ERD
**Main Models:**
- **User:** Customer or Vendor  
- **AuctionItem:** title, description, starting_price, reserved_price, status, vendor, is_deleted  
- **Bid:** auction_item, user, bid_amount, timestamp  
- **Comment:** auction_item, user, content, timestamp  
- **Order / ShippingAddress:** user, items, address, email  
- **Watchlist:** many-to-many relationship with auction items  

**ERD Diagram:**  
![ERD Diagram](https://gist.github.com/Acacore/f9a3401a294c7b9ea678df88d150df42)

---


## API Endpoints

Authentication & Token Management

| Endpoint              | Method  | Description                                                                  |
| --------------------- | ------- | ---------------------------------------------------------------------------- |
| `/api/token/`         | POST    | Obtain JWT access and refresh tokens                                         |
| `/api/token/refresh/` | POST    | Refresh JWT token                                                            |
| `/api/token/verify/`  | POST    | Verify JWT token validity                                                    |
| `/auth/`              | Various | Djoser endpoints for registration, login, password reset, profile management |


## API Documentation (DRF Spectacular)

The project includes **automatically generated API documentation** using DRF Spectacular. Developers can access and interact with the documentation through the following endpoints:

| Endpoint | Description |
|----------|-------------|
| `/api/schema/` | Provides the OpenAPI 3.0 schema in JSON format. |
| `/api/schema/swagger-ui/` | Interactive Swagger UI for exploring and testing API endpoints. |
| `/api/schema/redoc/` | Redoc interface offering a clean, structured view of the API documentation. |



User & Vendor Management

| Endpoint                | Method                 | Description                                   |
| ----------------------- | ---------------------- | --------------------------------------------- |
| `/api/category/`        | GET, POST, PUT, DELETE | Manage product categories                     |
| `/api/product/`         | GET, POST, PUT, DELETE | Manage products                               |
| `/api/vendor-product/`  | GET, POST, PUT, DELETE | Vendors manage their listed products          |
| `/api/product-variant/` | GET, POST, PUT, DELETE | Manage product variants (sizes, colors, etc.) |


Cart & Order Management

| Endpoint           | Method                 | Description                             |
| ------------------ | ---------------------- | --------------------------------------- |
| `/api/cart/`       | GET, POST, PUT, DELETE | Manage user carts                       |
| `/api/cart-item/`  | GET, POST, PUT, DELETE | Manage items inside a cart              |
| `/api/order-item/` | GET, POST, PUT, DELETE | Manage individual order items           |
| `/api/shipping/`   | GET, POST, PUT, DELETE | Manage shipping addresses               |
| `/api/payment/`    | GET, POST              | Manage payment processing               |
| `/api/checkout/`   | POST                   | Checkout endpoint to finalize purchases |


Auction & Bidding

| Endpoint          | Method                 | Description                           |
| ----------------- | ---------------------- | ------------------------------------- |
| `/api/auction/`   | GET, POST, PUT, DELETE | Create, view, or manage auction items |
| `/api/bid/`       | GET, POST              | Place or view bids                    |
| `/api/watchlist/` | GET, POST, DELETE      | Manage user watchlist for auctions    |
| `/api/comment/`   | GET, POST              | Add or view comments on auction items |


API Documentation (DRF Spectacular)

| Endpoint                  | Description             |
| ------------------------- | ----------------------- |
| `/api/schema/`            | OpenAPI 3.0 schema JSON |
| `/api/schema/swagger-ui/` | Interactive Swagger UI  |
| `/api/schema/redoc/`      | Redoc documentation     |



---

## Auction Business Logic
- **Status Values:** `ACTIVE`, `ENDED`, `CANCELLED`  
- **Soft delete:** `is_deleted=True` instead of deleting items  
- **Bid rules:** New bid must exceed current highest bid  
- **Reserved price:** Auction ends when bid ≥ reserved price  

---

## Deployment & Hosting

- **Backend:** Render (Django + PostgreSQL)  
- **Celery Worker:** Fly.io (connected to Redis)  
- **Email Notifications:** Optional via Celery tasks  

---

## Installation & Setup
1. Clone the repository:  
   ```bash
   git clone git@github.com:Acacore/alx-project-nexus.git



2. Create a virtual environment and install dependencies:

    python -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt


3. Apply migrations:
    python manage.py migrate


4. Create a superuser (optional):
    python manage.py createsuperuser


5. Run the server:
    python manage.py runserver

6. Visit http://localhost:8000 to view the application.


---

## Celery Worker Setup & Usage

Mercarol uses **Celery** for asynchronous tasks such as **email notifications, bid updates, and auction lifecycle management**. The Celery worker runs **online** and connects to Redis for the task queue.

### 1. Celery Configuration
```python
# settings.py
CELERY_BROKER_URL = 'redis://<your-redis-url>'
CELERY_RESULT_BACKEND = 'redis://<your-redis-url>'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'!
```


2. Running Celery Worker Locally (optional)
    celery -A core worker --loglevel=info


3. Running Celery Beat (Optional Scheduler)
    celery -A core beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler


4.  How it Works (Hosted Online)

    The Celery worker hosted on Fly.io connects to your Redis queue.

    Tasks triggered by the Django backend (e.g., new bid, comment notification) are pushed to Redis and executed asynchronously.

    No local worker is needed; tasks run automatically online.


### Deployment & Hosting
- Frontend: Render / Vercel
- Backend: Render (Django + PostgreSQL)
- Celery Worker: Fly.io (connected to Redis)
- Email Notifications: Optional via Celery tasks


## Logging
- All critical events (login, bids, orders) are logged
- Structured logs in JSON format (production-ready)
- Viewable in Render Logs panel



Author
Edoh Mensah Akpedzene
Institution: ALX
Program: B.Sc. Computer Science
Nexus Poroject Cohort 7 (2025)

AuctionBay – Secure, Scalable, eBay-Ready.