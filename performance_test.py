"""
Performance Testing Script for ERP System

This script uses Locust to perform load testing on the ERP application.
Tests critical endpoints and measures response times under load.

Usage:
    # Web UI mode
    locust -f performance_test.py --host=http://localhost:8000
    
    # Headless mode
    locust -f performance_test.py --headless --users 100 --spawn-rate 10 \
           --run-time 5m --host=http://localhost:8000

Requirements:
    pip install locust

Author: ERP Development Team
Created: 2026-02-04
"""

from locust import HttpUser, task, between, events
from typing import Dict, Any
import json
import random


class ERPUser(HttpUser):
    """
    Simulates a user interacting with the ERP system.
    
    Includes authentication, navigation, and CRUD operations
    across different modules.
    """
    
    wait_time = between(1, 3)  # Wait 1-3 seconds between tasks
    
    def on_start(self) -> None:
        """
        Called when a simulated user starts.
        
        Performs login to obtain session.
        """
        # Login
        response = self.client.post("/accounts/login/", {
            "username": "testuser",
            "password": "testpass123"
        })
        
        if response.status_code != 200:
            print(f"Login failed: {response.status_code}")
    
    @task(5)
    def view_dashboard(self) -> None:
        """View main dashboard - most common action."""
        self.client.get("/", name="Dashboard")
    
    @task(3)
    def list_products(self) -> None:
        """List products in inventory."""
        self.client.get("/inventory/products/", name="List Products")
    
    @task(2)
    def view_product_detail(self) -> None:
        """View product detail page."""
        # Simulate viewing a random product (ID 1-100)
        product_id = random.randint(1, 100)
        self.client.get(
            f"/inventory/product/{product_id}/",
            name="View Product Detail"
        )
    
    @task(3)
    def list_sales(self) -> None:
        """List sales orders."""
        self.client.get("/sales/", name="List Sales")
    
    @task(2)
    def view_sale_detail(self) -> None:
        """View sale detail page."""
        sale_id = random.randint(1, 100)
        self.client.get(
            f"/sales/sale/{sale_id}/",
            name="View Sale Detail"
        )
    
    @task(1)
    def create_sale_form(self) -> None:
        """Load sale creation form."""
        self.client.get("/sales/create/", name="Create Sale Form")
    
    @task(2)
    def list_customers(self) -> None:
        """List customers."""
        self.client.get("/sales/customers/", name="List Customers")
    
    @task(1)
    def create_customer_form(self) -> None:
        """Load customer creation form."""
        self.client.get("/sales/customer/create/", name="Create Customer Form")
    
    @task(2)
    def list_production_orders(self) -> None:
        """List production orders."""
        self.client.get("/production/orders/", name="List Production Orders")
    
    @task(1)
    def list_boms(self) -> None:
        """List Bills of Material."""
        self.client.get("/production/boms/", name="List BOMs")
    
    @task(1)
    def view_finance_dashboard(self) -> None:
        """View finance dashboard."""
        self.client.get("/finance/", name="Finance Dashboard")
    
    @task(1)
    def list_accounts(self) -> None:
        """List financial accounts."""
        self.client.get("/finance/accounts/", name="List Accounts")
    
    @task(1)
    def list_cash_movements(self) -> None:
        """List cash movements."""
        self.client.get("/finance/cash-movements/", name="List Cash Movements")


class APIUser(HttpUser):
    """
    Simulates API client making REST API calls.
    
    Tests API endpoints for performance and reliability.
    """
    
    wait_time = between(0.5, 2)
    
    def on_start(self) -> None:
        """Authenticate and get API token."""
        response = self.client.post("/api/auth/login/", json={
            "username": "apiuser",
            "password": "apipass123"
        })
        
        if response.status_code == 200:
            data = response.json()
            self.token = data.get('token', '')
        else:
            self.token = ''
    
    def headers(self) -> Dict[str, str]:
        """Get request headers with auth token."""
        return {
            'Authorization': f'Token {self.token}',
            'Content-Type': 'application/json'
        }
    
    @task(5)
    def api_list_products(self) -> None:
        """API: List products."""
        self.client.get(
            "/api/inventory/products/",
            headers=self.headers(),
            name="API - List Products"
        )
    
    @task(3)
    def api_get_product(self) -> None:
        """API: Get product detail."""
        product_id = random.randint(1, 100)
        self.client.get(
            f"/api/inventory/products/{product_id}/",
            headers=self.headers(),
            name="API - Get Product"
        )
    
    @task(4)
    def api_list_sales(self) -> None:
        """API: List sales."""
        self.client.get(
            "/api/sales/orders/",
            headers=self.headers(),
            name="API - List Sales"
        )
    
    @task(2)
    def api_list_customers(self) -> None:
        """API: List customers."""
        self.client.get(
            "/api/sales/customers/",
            headers=self.headers(),
            name="API - List Customers"
        )
    
    @task(1)
    def api_create_customer(self) -> None:
        """API: Create customer."""
        customer_data = {
            "name": f"Test Customer {random.randint(1000, 9999)}",
            "document_type": "DNI",
            "document_number": f"{random.randint(10000000, 99999999)}",
            "email": f"test{random.randint(1, 999)}@example.com"
        }
        
        self.client.post(
            "/api/sales/customers/",
            json=customer_data,
            headers=self.headers(),
            name="API - Create Customer"
        )


# Event handlers for custom reporting
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when test starts."""
    print("\n🚀 Starting Performance Tests...")
    print(f"Target Host: {environment.host}")
    print()


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when test stops."""
    print("\n✅ Performance Tests Completed")
    
    # Print summary statistics
    stats = environment.stats
    
    print("\n" + "="*70)
    print("PERFORMANCE TEST SUMMARY")
    print("="*70)
    
    print(f"\nTotal Requests: {stats.total.num_requests}")
    print(f"Total Failures: {stats.total.num_failures}")
    print(f"Failure Rate:   {stats.total.fail_ratio * 100:.2f}%")
    
    print(f"\nResponse Times:")
    print(f"  Median:  {stats.total.median_response_time:.0f}ms")
    print(f"  Average: {stats.total.avg_response_time:.0f}ms")
    print(f"  95th percentile: {stats.total.get_response_time_percentile(0.95):.0f}ms")
    print(f"  99th percentile: {stats.total.get_response_time_percentile(0.99):.0f}ms")
    print(f"  Max:     {stats.total.max_response_time:.0f}ms")
    
    print(f"\nRequests per Second: {stats.total.total_rps:.2f}")
    
    # Performance grade
    p95 = stats.total.get_response_time_percentile(0.95)
    if p95 < 200:
        grade = "A+ (Excellent)"
    elif p95 < 500:
        grade = "A (Good)"
    elif p95 < 1000:
        grade = "B (Acceptable)"
    elif p95 < 2000:
        grade = "C (Needs Improvement)"
    else:
        grade = "F (Poor)"
    
    print(f"\nPerformance Grade: {grade}")
    
    # Top slow endpoints
    print("\n" + "-"*70)
    print("SLOWEST ENDPOINTS (95th percentile)")
    print("-"*70)
    
    sorted_stats = sorted(
        [s for s in stats.entries.values() if s.num_requests > 0],
        key=lambda x: x.get_response_time_percentile(0.95),
        reverse=True
    )[:10]
    
    for stat in sorted_stats:
        p95_time = stat.get_response_time_percentile(0.95)
        print(f"{stat.name:.<50} {p95_time:.0f}ms")
    
    print("="*70 + "\n")


if __name__ == "__main__":
    """
    Run this script directly for testing.
    
    Example:
        python performance_test.py
    """
    import os
    os.system("locust -f performance_test.py --host=http://localhost:8000")
