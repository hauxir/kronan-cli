# kronan-cli

A command-line tool for interacting with the [Kronan](https://kronan.is) grocery store in Iceland.

## Installation

Requires Python 3.12+.

```bash
pip install .
```

Or with [uv](https://github.com/astral-sh/uv):

```bash
uv pip install .
```

## Authentication

Some commands require authentication via Kronan's Cognito OAuth.

```bash
# Login via browser (opens OAuth flow)
kronan login

# Or paste a JWT token directly
kronan login -t <token>

# Check current user
kronan whoami

# Logout
kronan logout
```

You can also set the `KRONAN_TOKEN` environment variable instead of logging in.

Config is stored in `~/.config/kronan/config.json`.

## Commands

### Products

```bash
kronan search "mjólk"           # Search for products
kronan search "brauð" -l 5      # Limit results
kronan product <sku>             # Show product details
kronan sales                     # Show products on sale
kronan tags                      # List product tags
```

### Categories

```bash
kronan categories                # List product categories
```

### Stores

```bash
kronan stores                    # List all store locations
```

### Delivery & Pickup

```bash
kronan pickup-slots              # Show available pickup slots
kronan delivery-slots "Laugavegur 1"  # Show delivery slots for an address
```

### Orders (auth required)

```bash
kronan orders                    # List order history
kronan order                     # Show active order
```

### Favorites (auth required)

```bash
kronan favorites                 # List favorite products
kronan favorite-toggle <sku>     # Toggle a product as favorite
```

### Shopping Lists (auth required)

```bash
kronan lists                     # Show shopping lists
```

### Recipes

```bash
kronan recipes "kjúklingur"      # Search for recipes
```

### Coupons & Promotions (auth required)

```bash
kronan coupons                   # Show available coupons
kronan promotions                # Show promotions
```

### Health Points (auth required)

```bash
kronan health                    # Show health cart points summary
```

### Other

```bash
kronan config-show               # Show current configuration
```

## JSON Output

All listing commands support `-j` / `--json-output` for raw JSON output:

```bash
kronan search "mjólk" -j
kronan stores -j
```

## Development

```bash
pip install -e ".[dev]"
ruff check app/
basedpyright
pytest
```

## License

MIT
