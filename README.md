# Propel ERP

A modern, responsive ERP system built with Django and TailwindCSS, designed for small business management.

## Modules

-   **Dashboard**: Real-time overview of revenue, orders, and stock.
-   **Sales**: Manage orders, customers, and sales channels (Wholesale, MercadoLibre, TiendaNube).
-   **Inventory**: Track products, raw materials (ingredients), and recipes. Includes low-stock alerts.
-   **Finance**: Manage providers, fixed costs, monthly expenses, and assets.

## Tech Stack

-   **Backend**: Python, Django 5
-   **Database**: SQLite (Development)
-   **Frontend**: HTML, Tailwind CSS (via CDN), JavaScript
-   **Charts**: Chart.js

## Setup Instructions

1.  **Clone the repository**
    ```bash
    git clone <repository-url>
    cd ERP
    ```

2.  **Create and activate virtual environment**
    ```bash
    # Windows
    python -m venv venv
    .\venv\Scripts\activate
    
    # Mac/Linux
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install dependencies**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Run migrations**
    ```bash
    python manage.py migrate
    ```

5.  **Create superuser (optional)**
    ```bash
    python manage.py createsuperuser
    ```

6.  **Run the server**
    ```bash
    python manage.py runserver
    ```

7.  Access the app at `http://127.0.0.1:8000`

## Credentials

*   **Admin default**: `testadmin` / `admin123` (Use `python manage.py createsuperuser` if needed)
