import json
import os
from typing import Any

import click
from rich.console import Console
from rich.table import Table

from app import config
from app.client import KronanClient

console = Console()


def get_client() -> KronanClient:
    token = os.environ.get("KRONAN_TOKEN") or config.get_token()
    return KronanClient(token)


def _format_price(price: Any) -> str:
    """Format a price value in ISK."""
    if price is None:
        return "-"
    try:
        return f"{int(price):,} kr"
    except (ValueError, TypeError):
        return str(price)


@click.group()
def main() -> None:
    """Kronan CLI - Interact with Kronan grocery store (Iceland)."""


# === Authentication ===


@main.command()
@click.option("--token", "-t", help="Paste a Cognito JWT token directly")
def login(token: str | None) -> None:
    """Login to Kronan via Cognito OAuth (opens browser).

    \b
    Examples:
      kronan login                  # OAuth in browser (default)
      kronan login -t <jwt-token>   # paste token directly
    """
    if token:
        config.set_token(token)
        console.print("[green]Token saved![/green]")
        try:
            with KronanClient(token) as client:
                user = client.get_me()
                name = user.get("name") or user.get("email") or user.get("phone_number", "")
                console.print(f"Logged in as [bold]{name}[/bold]")
        except Exception:
            console.print("[yellow]Token saved but could not verify. It may be expired.[/yellow]")
        console.print(f"Config saved to {config.CONFIG_FILE}")
        return

    from app.auth_server import run_auth_server

    console.print("Opening browser for Kronan login...")
    result = run_auth_server()
    if not result:
        console.print("[red]Login timed out or was cancelled.[/red]")
        raise SystemExit(1)
    if "error" in result:
        console.print(f"[red]Login failed: {result['error']}[/red]")
        raise SystemExit(1)

    id_token = result.get("id_token", "")
    refresh = result.get("refresh_token", "")
    if id_token:
        config.set_token(id_token)
    if refresh:
        config.set_refresh_token(refresh)

    try:
        with KronanClient(id_token) as client:
            user = client.get_me()
            name = user.get("name") or user.get("email") or ""
            console.print(f"[green]Login successful![/green] Logged in as [bold]{name}[/bold]")
    except Exception:
        console.print("[green]Login successful![/green]")
    console.print(f"Config saved to {config.CONFIG_FILE}")


@main.command()
def logout() -> None:
    """Clear saved credentials."""
    config.clear_config()
    console.print("[green]Logged out - credentials cleared[/green]")


@main.command("config-show")
def config_show() -> None:
    """Show current configuration."""
    console.print(f"[bold]Config file:[/bold] {config.CONFIG_FILE}")
    token = config.get_token()
    console.print(f"[bold]Token:[/bold] {token[:20] + '...' if token else '[dim]not set[/dim]'}")


@main.command("whoami")
def whoami() -> None:
    """Show current user info."""
    with get_client() as client:
        user = client.get_me()
        for key, val in user.items():
            if val and not isinstance(val, (dict, list)):
                console.print(f"[bold]{key}:[/bold] {val}")


# === Products ===


@main.command()
@click.argument("query")
@click.option("--limit", "-l", default=20, help="Number of results")
@click.option("--page", "-p", default=1, help="Page number")
@click.option("--json-output", "-j", is_flag=True, help="Output as JSON")
def search(query: str, limit: int, page: int, json_output: bool) -> None:
    """Search for products."""
    with get_client() as client:
        result = client.search_products(query, limit, page)
        if json_output:
            console.print(json.dumps(result, indent=2, default=str))
            return
        hits = result.get("results", {}).get("hits", []) if isinstance(result.get("results"), dict) else result.get("results", [])
        if not hits:
            console.print("[dim]No products found[/dim]")
            return
        count = result.get("count", len(hits))
        table = Table(title=f"Products matching '{query}' ({count} total)")
        table.add_column("SKU", style="cyan")
        table.add_column("Name", style="green")
        table.add_column("Price", style="yellow", justify="right")
        table.add_column("Unit", style="dim")
        table.add_column("On Sale", style="red")
        for p in hits:
            on_sale = "[red]SALE[/red]" if p.get("on_sale") or p.get("discount_price") else ""
            price = p.get("discount_price") or p.get("price") or p.get("selling_price")
            table.add_row(
                str(p.get("sku", p.get("id", ""))),
                str(p.get("name", p.get("product_name", "")))[:50],
                _format_price(price),
                str(p.get("unit", p.get("unit_of_measure", ""))),
                on_sale,
            )
        console.print(table)
        page_count = result.get("pageCount", result.get("page_count", ""))
        if page_count:
            console.print(f"[dim]Page {page}/{page_count}[/dim]")


@main.command("product")
@click.argument("sku")
@click.option("--json-output", "-j", is_flag=True, help="Output as JSON")
def product_show(sku: str, json_output: bool) -> None:
    """Show product details by SKU."""
    with get_client() as client:
        results = client.get_products_by_sku([sku])
        if json_output:
            console.print(json.dumps(results, indent=2, default=str))
            return
        products = results if isinstance(results, list) else results.get("results", [results])
        if not products:
            console.print("[red]Product not found[/red]")
            return
        p = products[0] if isinstance(products, list) else products
        console.print(f"[bold cyan]{p.get('name', p.get('product_name', ''))}[/bold cyan]")
        for key, val in p.items():
            if val and not isinstance(val, (dict, list)):
                console.print(f"[bold]{key}:[/bold] {val}")


@main.command("sales")
@click.option("--json-output", "-j", is_flag=True, help="Output as JSON")
def sales(json_output: bool) -> None:
    """Show products on sale."""
    with get_client() as client:
        result = client.get_sale_products()
        if json_output:
            console.print(json.dumps(result, indent=2, default=str))
            return
        products = result if isinstance(result, list) else result.get("results", [])
        if not products:
            console.print("[dim]No sale products found[/dim]")
            return
        table = Table(title="Products on Sale")
        table.add_column("SKU", style="cyan")
        table.add_column("Name", style="green")
        table.add_column("Price", style="yellow", justify="right")
        table.add_column("Sale Price", style="red", justify="right")
        for p in products[:50]:
            table.add_row(
                str(p.get("sku", "")),
                str(p.get("name", ""))[:50],
                _format_price(p.get("price", p.get("selling_price"))),
                _format_price(p.get("discount_price", p.get("sale_price"))),
            )
        console.print(table)


@main.command("tags")
@click.option("--json-output", "-j", is_flag=True, help="Output as JSON")
def tags(json_output: bool) -> None:
    """List product tags."""
    with get_client() as client:
        result = client.get_product_tags()
        if json_output:
            console.print(json.dumps(result, indent=2, default=str))
            return
        items = result if isinstance(result, list) else result.get("results", [])
        for tag in items:
            if isinstance(tag, dict):
                console.print(f"  [cyan]{tag.get('name', tag.get('slug', ''))}[/cyan] - {tag.get('description', '')}")
            else:
                console.print(f"  [cyan]{tag}[/cyan]")


# === Categories ===


@main.command("categories")
@click.option("--json-output", "-j", is_flag=True, help="Output as JSON")
def categories(json_output: bool) -> None:
    """List product categories."""
    with get_client() as client:
        result = client.get_categories()
        if json_output:
            console.print(json.dumps(result, indent=2, default=str))
            return
        cats = result if isinstance(result, list) else result.get("results", [])
        if not cats:
            console.print("[dim]No categories found[/dim]")
            return
        table = Table(title="Categories")
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="green")
        table.add_column("Slug", style="dim")
        for c in cats:
            table.add_row(
                str(c.get("id", "")),
                str(c.get("name", "")),
                str(c.get("slug", "")),
            )
            for sub in c.get("children", []):
                table.add_row(
                    f"  {sub.get('id', '')}",
                    f"  {sub.get('name', '')}",
                    f"  {sub.get('slug', '')}",
                )
        console.print(table)


# === Stores ===


@main.command("stores")
@click.option("--json-output", "-j", is_flag=True, help="Output as JSON")
def stores(json_output: bool) -> None:
    """List all store locations."""
    with get_client() as client:
        result = client.get_stores()
        if json_output:
            console.print(json.dumps(result, indent=2, default=str))
            return
        store_list = result if isinstance(result, list) else result.get("results", [])
        if not store_list:
            console.print("[dim]No stores found[/dim]")
            return
        table = Table(title="Kronan Stores")
        table.add_column("Name", style="green")
        table.add_column("Address", style="dim")
        table.add_column("City", style="cyan")
        table.add_column("Hours", style="yellow")
        for s in store_list:
            hours = ""
            if s.get("opening_hours") or s.get("hours"):
                h = s.get("opening_hours") or s.get("hours", "")
                hours = str(h) if not isinstance(h, (dict, list)) else ""
            table.add_row(
                str(s.get("name", "")),
                str(s.get("address", "")),
                str(s.get("city", s.get("postal_code", ""))),
                hours[:30],
            )
        console.print(table)


# === Slots ===


@main.command("pickup-slots")
@click.option("--json-output", "-j", is_flag=True, help="Output as JSON")
def pickup_slots(json_output: bool) -> None:
    """Show available pickup time slots."""
    with get_client() as client:
        result = client.get_pickup_slots()
        if json_output:
            console.print(json.dumps(result, indent=2, default=str))
            return
        slots = result if isinstance(result, list) else result.get("results", [])
        if not slots:
            console.print("[dim]No pickup slots available[/dim]")
            return
        table = Table(title="Pickup Slots")
        table.add_column("Store", style="green")
        table.add_column("Date", style="cyan")
        table.add_column("Time", style="yellow")
        table.add_column("Available", style="bold")
        for slot in slots:
            if isinstance(slot, dict):
                table.add_row(
                    str(slot.get("store", slot.get("store_name", ""))),
                    str(slot.get("date", "")),
                    str(slot.get("time", slot.get("time_slot", ""))),
                    str(slot.get("available", slot.get("is_available", ""))),
                )
        console.print(table)


@main.command("delivery-slots")
@click.argument("address")
@click.option("--json-output", "-j", is_flag=True, help="Output as JSON")
def delivery_slots(address: str, json_output: bool) -> None:
    """Show delivery slots for an address."""
    with get_client() as client:
        result = client.get_delivery_slots(address)
        if json_output:
            console.print(json.dumps(result, indent=2, default=str))
            return
        slots = result if isinstance(result, list) else result.get("results", [])
        if not slots:
            console.print("[dim]No delivery slots available[/dim]")
            return
        table = Table(title=f"Delivery Slots for '{address}'")
        table.add_column("Date", style="cyan")
        table.add_column("Time", style="yellow")
        table.add_column("Price", style="green", justify="right")
        table.add_column("Available", style="bold")
        for slot in slots:
            if isinstance(slot, dict):
                table.add_row(
                    str(slot.get("date", "")),
                    str(slot.get("time", slot.get("time_slot", ""))),
                    _format_price(slot.get("price", slot.get("delivery_fee"))),
                    str(slot.get("available", slot.get("is_available", ""))),
                )
        console.print(table)


# === Orders (auth required) ===


@main.command("orders")
@click.option("--json-output", "-j", is_flag=True, help="Output as JSON")
def orders(json_output: bool) -> None:
    """List order history."""
    with get_client() as client:
        result = client.get_orders()
        if json_output:
            console.print(json.dumps(result, indent=2, default=str))
            return
        order_list = result if isinstance(result, list) else result.get("results", [])
        if not order_list:
            console.print("[dim]No orders found[/dim]")
            return
        table = Table(title="Orders")
        table.add_column("ID", style="cyan")
        table.add_column("Status", style="bold")
        table.add_column("Total", style="yellow", justify="right")
        table.add_column("Date", style="dim")
        table.add_column("Type", style="green")
        for o in order_list:
            status = str(o.get("status", ""))
            style = "green" if status.lower() in ("delivered", "completed") else "yellow" if status.lower() in ("pending", "processing") else "dim"
            table.add_row(
                str(o.get("id", o.get("order_number", ""))),
                f"[{style}]{status}[/{style}]",
                _format_price(o.get("total", o.get("grand_total"))),
                str(o.get("created", o.get("created_at", o.get("date", ""))))[:19],
                str(o.get("order_type", o.get("delivery_type", ""))),
            )
        console.print(table)


@main.command("order")
@click.option("--json-output", "-j", is_flag=True, help="Output as JSON")
def active_order(json_output: bool) -> None:
    """Show active order."""
    with get_client() as client:
        result = client.get_active_order()
        if json_output:
            console.print(json.dumps(result, indent=2, default=str))
            return
        if not result:
            console.print("[dim]No active order[/dim]")
            return
        for key, val in result.items():
            if isinstance(val, list):
                console.print(f"[bold]{key}:[/bold] ({len(val)} items)")
            elif isinstance(val, dict):
                console.print(f"[bold]{key}:[/bold] ...")
            else:
                console.print(f"[bold]{key}:[/bold] {val}")


# === Favorites (auth required) ===


@main.command("favorites")
@click.option("--json-output", "-j", is_flag=True, help="Output as JSON")
def favorites(json_output: bool) -> None:
    """List favorite products."""
    with get_client() as client:
        result = client.get_favorites()
        if json_output:
            console.print(json.dumps(result, indent=2, default=str))
            return
        items = result if isinstance(result, list) else result.get("results", [])
        if not items:
            console.print("[dim]No favorites[/dim]")
            return
        table = Table(title="Favorites")
        table.add_column("SKU", style="cyan")
        table.add_column("Name", style="green")
        table.add_column("Price", style="yellow", justify="right")
        for p in items:
            table.add_row(
                str(p.get("sku", "")),
                str(p.get("name", ""))[:50],
                _format_price(p.get("price", p.get("selling_price"))),
            )
        console.print(table)


@main.command("favorite-toggle")
@click.argument("sku")
def favorite_toggle(sku: str) -> None:
    """Toggle a product as favorite."""
    with get_client() as client:
        client.toggle_favorite(sku)
        console.print(f"[green]Toggled favorite for SKU {sku}[/green]")


# === Shopping Lists (auth required) ===


@main.command("lists")
@click.option("--json-output", "-j", is_flag=True, help="Output as JSON")
def lists(json_output: bool) -> None:
    """Show shopping lists."""
    with get_client() as client:
        result = client.get_product_lists()
        if json_output:
            console.print(json.dumps(result, indent=2, default=str))
            return
        items = result if isinstance(result, list) else result.get("results", [])
        if not items:
            console.print("[dim]No shopping lists[/dim]")
            return
        for lst in items:
            console.print(f"[bold cyan]{lst.get('name', 'Untitled')}[/bold cyan] (id: {lst.get('id', '')})")
            list_items = lst.get("items", [])
            if list_items:
                for item in list_items:
                    console.print(f"  {item.get('name', item.get('sku', ''))}")


# === Recipes ===


@main.command("recipes")
@click.argument("query")
@click.option("--limit", "-l", default=20, help="Number of results")
@click.option("--json-output", "-j", is_flag=True, help="Output as JSON")
def recipes(query: str, limit: int, json_output: bool) -> None:
    """Search for recipes."""
    with get_client() as client:
        result = client.search_recipes(query, limit)
        if json_output:
            console.print(json.dumps(result, indent=2, default=str))
            return
        hits = result.get("results", {}).get("hits", []) if isinstance(result.get("results"), dict) else result.get("results", result if isinstance(result, list) else [])
        if not hits:
            console.print("[dim]No recipes found[/dim]")
            return
        table = Table(title=f"Recipes matching '{query}'")
        table.add_column("Name", style="green")
        table.add_column("Time", style="yellow")
        table.add_column("Servings", style="cyan")
        for r in hits:
            table.add_row(
                str(r.get("name", r.get("title", "")))[:50],
                str(r.get("cooking_time", r.get("time", ""))),
                str(r.get("servings", r.get("portions", ""))),
            )
        console.print(table)


# === Coupons (auth required) ===


@main.command("coupons")
@click.option("--json-output", "-j", is_flag=True, help="Output as JSON")
def coupons(json_output: bool) -> None:
    """Show available coupons."""
    with get_client() as client:
        result = client.get_coupons()
        if json_output:
            console.print(json.dumps(result, indent=2, default=str))
            return
        items = result if isinstance(result, list) else result.get("results", [])
        if not items:
            console.print("[dim]No coupons available[/dim]")
            return
        table = Table(title="Coupons")
        table.add_column("Code", style="cyan")
        table.add_column("Description", style="green")
        table.add_column("Discount", style="yellow")
        table.add_column("Expires", style="dim")
        for c in items:
            table.add_row(
                str(c.get("code", "")),
                str(c.get("description", c.get("name", "")))[:40],
                str(c.get("discount", c.get("value", ""))),
                str(c.get("expires", c.get("valid_until", "")))[:10],
            )
        console.print(table)


# === Health Points (auth required) ===


@main.command("health")
@click.option("--json-output", "-j", is_flag=True, help="Output as JSON")
def health(json_output: bool) -> None:
    """Show health cart points summary."""
    with get_client() as client:
        result = client.get_health_points_summary()
        if json_output:
            console.print(json.dumps(result, indent=2, default=str))
            return
        if not result:
            console.print("[dim]No health data[/dim]")
            return
        for key, val in (result.items() if isinstance(result, dict) else []):
            console.print(f"[bold]{key}:[/bold] {val}")


# === Marketing ===


@main.command("promotions")
@click.option("--json-output", "-j", is_flag=True, help="Output as JSON")
def promotions(json_output: bool) -> None:
    """Show marketing collections / promotions."""
    with get_client() as client:
        result = client.get_marketing_collections()
        if json_output:
            console.print(json.dumps(result, indent=2, default=str))
            return
        items = result if isinstance(result, list) else result.get("results", [])
        if not items:
            console.print("[dim]No promotions[/dim]")
            return
        for promo in items:
            console.print(f"[bold cyan]{promo.get('name', promo.get('title', ''))}[/bold cyan]")
            if promo.get("description"):
                console.print(f"  {promo['description'][:80]}")


if __name__ == "__main__":
    main()
