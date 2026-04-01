from typing import Any

import httpx

BASE_URL = "https://backend.kronan.is"

# AWS Cognito config
COGNITO_REGION = "eu-west-1"
COGNITO_USER_POOL_ID = "eu-west-1_vMf5qEeZT"
COGNITO_CLIENT_ID = "1cfe83fp2l6bk7oc6or2oit32o"
COGNITO_DOMAIN = "auth.kronan.is"


class KronanClient:
    def __init__(self, token: str | None = None) -> None:
        self.token = token
        self._client = httpx.Client(timeout=30.0)

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"CognitoJWT {self.token}"
        return headers

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        response = self._client.get(f"{BASE_URL}{path}", headers=self._headers(), params=params)
        response.raise_for_status()
        return response.json()

    def _post(self, path: str, data: dict[str, Any] | None = None) -> Any:
        response = self._client.post(f"{BASE_URL}{path}", json=data or {}, headers=self._headers())
        response.raise_for_status()
        return response.json()

    def _patch(self, path: str, data: dict[str, Any]) -> Any:
        response = self._client.patch(f"{BASE_URL}{path}", json=data, headers=self._headers())
        response.raise_for_status()
        return response.json()

    def _delete(self, path: str) -> None:
        response = self._client.delete(f"{BASE_URL}{path}", headers=self._headers())
        response.raise_for_status()

    # === Products ===

    def search_products(self, query: str, limit: int = 20, page: int = 1) -> dict[str, Any]:
        """Search for products."""
        return self._post("/api/products/raw-search/", {"query": query, "limit": limit, "page": page})  # type: ignore[no-any-return]

    def get_products_by_sku(self, skus: list[str]) -> Any:
        """Get products by SKU list."""
        return self._get("/api/products/sku-list/", {"skus": ",".join(skus)})

    def get_sale_products(self) -> Any:
        """Get products on sale."""
        return self._get("/api/sales/products/")

    def get_product_tags(self) -> Any:
        """Get all product tags."""
        return self._get("/api/products/tags/")

    # === Categories ===

    def get_categories(self) -> Any:
        """Get all product categories."""
        return self._get("/api/categories/")

    def get_specialized_categories(self) -> Any:
        """Get specialized categories (vegan, etc.)."""
        return self._get("/api/specialized-categories/")

    # === Stores ===

    def get_stores(self) -> Any:
        """Get all store locations."""
        return self._get("/api/stores/info/")

    # === Slots ===

    def get_pickup_slots(self) -> Any:
        """Get available pickup time slots."""
        return self._get("/api/slots/pickup/")

    def get_delivery_slots(self, address: str) -> Any:
        """Get delivery time slots for an address."""
        return self._get("/api/slots/delivery/", {"address": address})

    # === User (auth required) ===

    def get_me(self) -> dict[str, Any]:
        """Get current user profile."""
        return self._get("/api/users/me/")  # type: ignore[no-any-return]

    # === Orders (auth required) ===

    def get_active_order(self) -> Any:
        """Get current active order."""
        return self._get("/api/orders/active/")

    def get_orders(self) -> Any:
        """Get order history."""
        return self._get("/api/orders/list/")

    # === Favorites (auth required) ===

    def get_favorites(self) -> Any:
        """Get favorite products."""
        return self._get("/api/products/favorites/")

    def toggle_favorite(self, sku: str) -> Any:
        """Toggle a product as favorite."""
        return self._post("/api/specialized-products/toggle-favorite/", {"sku": sku})

    # === Shopping Lists (auth required) ===

    def get_product_lists(self) -> Any:
        """Get shopping lists."""
        return self._get("/api/product_list/")

    def get_all_list_items(self) -> Any:
        """Get all items across shopping lists."""
        return self._get("/api/product_list/all-items/")

    def get_shared_lists(self) -> Any:
        """Get shared shopping lists."""
        return self._get("/api/product_list/shared/")

    # === Recipes ===

    def search_recipes(self, query: str, limit: int = 20) -> Any:
        """Search for recipes."""
        return self._post("/api/recipes/search/", {"query": query, "limit": limit})

    def get_recipe_favorites(self) -> Any:
        """Get favorite recipes."""
        return self._get("/api/recipes/favorites/")

    def get_recipe_collections(self) -> Any:
        """Get recipe collections."""
        return self._get("/api/recipe-collections/")

    # === Coupons (auth required) ===

    def get_coupons(self) -> Any:
        """Get available coupons."""
        return self._get("/api/coupons/")

    # === Marketing ===

    def get_marketing_collections(self) -> Any:
        """Get marketing/promotional collections."""
        return self._get("/api/marketing_collections/")

    # === Receipts (auth required) ===

    def search_receipts(self, **params: Any) -> Any:
        """Search ERP receipts."""
        return self._get("/api/erp-receipts/search/", params)

    # === Health Cart (auth required) ===

    def get_health_goal(self) -> Any:
        """Get health cart goal."""
        return self._get("/api/health-carts/goal/")

    def get_health_points_summary(self) -> Any:
        """Get health points summary."""
        return self._get("/api/health-carts/points/summary/")

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "KronanClient":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()
