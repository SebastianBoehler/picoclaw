---
name: shopify
description: Manage a Shopify store via the Admin API. Use when asked to manage products, inventory, orders, customers, collections, discounts, themes, pages, blogs, files, returns, refunds, metaobjects, or any Shopify store data. Also handles promoting changes from dev to prod store. Requires shopify-stores.yaml config. Triggers on: "shopify", "product", "inventory", "order", "customer", "collection", "discount", "theme", "page", "blog", "store", "promote", "deploy to prod".
---

# Shopify Admin API Skill

Manage your Shopify store using the `ShopifyAPI` Python library (baked into the agent image).

**Env vars required** (injected via container environment):

- `SHOPIFY_STORE_URL` — e.g. `your-store.myshopify.com`
- `SHOPIFY_ACCESS_TOKEN` — Admin API access token (from Shopify Admin → Apps → Develop apps)
- `SHOPIFY_API_VERSION` — e.g. `2026-04` (optional, defaults to `2026-04`)

---

## Setup — Multi-Store (preferred)

Use the helper at `/home/picoclaw/shopify_stores.py`. Stores are configured in `/home/picoclaw/shopify-stores.yaml`.

```python
import sys
sys.path.insert(0, '/home/picoclaw')
from shopify_stores import get_shopify_session, list_stores

# List available stores
stores = list_stores()
for s in stores:
    print(s['key'], s['name'], '✅' if s['configured'] else '❌ not configured')

# Activate default store (currently: dev)
store = get_shopify_session()
print("Connected to:", store['name'])

# Activate a specific store by key
store = get_shopify_session("dev")   # dev store
store = get_shopify_session("main")  # main/production store
```

## Adding a New Store

Edit `/home/picoclaw/shopify-stores.yaml` on the host at `picoclaw/config/shopify-stores.yaml`:

```yaml
stores:
  dev:
    name: "Sunderlabs Dev Shop"
    url: "sunderlabs-dev-shop.myshopify.com"
    access_token: "shpat_..."
    api_version: "2024-01"
    default: true

  main:
    name: "Sunderlabs Main Shop"
    url: "your-main-store.myshopify.com"
    access_token: "shpat_..."
    api_version: "2024-01"
    default: false
```

No container restart needed — the file is live-mounted.

## Setup — Single Store (fallback)

```python
import shopify, os
session = shopify.Session(os.environ["SHOPIFY_STORE_URL"], os.environ.get("SHOPIFY_API_VERSION", "2024-01"), os.environ["SHOPIFY_ACCESS_TOKEN"])
shopify.ShopifyResource.activate_session(session)
```

---

## Products

```python
# List all products (paginated)
products = shopify.Product.find(limit=50)
for p in products:
    print(p.id, p.title, p.status)

# Get single product
product = shopify.Product.find(1234567890)
print(product.title, product.variants[0].price)

# Create product
new_product = shopify.Product()
new_product.title = "My New Product"
new_product.body_html = "<p>Description here</p>"
new_product.vendor = "My Brand"
new_product.product_type = "T-Shirt"
new_product.status = "draft"  # or "active"
new_product.variants = [{"price": "29.99", "sku": "SKU-001"}]
new_product.save()
print("Created:", new_product.id)

# Update product
product = shopify.Product.find(1234567890)
product.title = "Updated Title"
product.status = "active"
product.save()

# Delete product
product = shopify.Product.find(1234567890)
product.destroy()

# Search products by title
products = shopify.Product.find(title="My Product")

# Filter by status
active = shopify.Product.find(status="active", limit=50)
drafts = shopify.Product.find(status="draft", limit=50)
```

## Variants & Inventory

```python
# Get variants for a product
product = shopify.Product.find(1234567890)
for v in product.variants:
    print(v.id, v.title, v.price, v.inventory_quantity)

# Update variant price
variant = shopify.Variant.find(9876543210)
variant.price = "39.99"
variant.compare_at_price = "49.99"
variant.save()

# Update inventory level (requires location_id)
locations = shopify.Location.find()
location_id = locations[0].id

inventory_item_id = variant.inventory_item_id
shopify.InventoryLevel.set(
    location_id=location_id,
    inventory_item_id=inventory_item_id,
    available=100
)

# Adjust inventory (relative change)
shopify.InventoryLevel.adjust(
    location_id=location_id,
    inventory_item_id=inventory_item_id,
    available_adjustment=10  # +10 units
)
```

## Orders

```python
# List recent orders
orders = shopify.Order.find(status="any", limit=50)
for o in orders:
    print(o.id, o.name, o.financial_status, o.total_price)

# Get single order
order = shopify.Order.find(1234567890)
print(order.line_items[0].title, order.shipping_address.city)

# Filter orders
open_orders = shopify.Order.find(status="open", limit=50)
paid_orders = shopify.Order.find(financial_status="paid", limit=50)

# Fulfill an order
fulfillment = shopify.Fulfillment({"order_id": order.id})
fulfillment.tracking_number = "1Z999AA10123456784"
fulfillment.tracking_company = "UPS"
fulfillment.save()

# Cancel an order
order = shopify.Order.find(1234567890)
order.cancel()
```

## Customers

```python
# List customers
customers = shopify.Customer.find(limit=50)
for c in customers:
    print(c.id, c.email, c.first_name, c.last_name)

# Search customers
results = shopify.Customer.search(query="email:test@example.com")

# Create customer
customer = shopify.Customer()
customer.first_name = "Jane"
customer.last_name = "Doe"
customer.email = "jane@example.com"
customer.phone = "+4917612345678"
customer.tags = "vip,newsletter"
customer.save()

# Update customer
customer = shopify.Customer.find(1234567890)
customer.tags = "vip,newsletter,loyal"
customer.save()
```

## Collections

```python
# List custom collections
collections = shopify.CustomCollection.find()
for c in collections:
    print(c.id, c.title)

# Create custom collection
col = shopify.CustomCollection()
col.title = "Summer Sale"
col.body_html = "<p>Best summer deals</p>"
col.save()

# Add product to collection
collect = shopify.Collect()
collect.product_id = 1234567890
collect.collection_id = col.id
collect.save()

# List smart collections
smart = shopify.SmartCollection.find()
```

## Discounts / Price Rules

```python
# Create a price rule (% discount)
rule = shopify.PriceRule()
rule.title = "SUMMER20"
rule.target_type = "line_item"
rule.target_selection = "all"
rule.allocation_method = "across"
rule.value_type = "percentage"
rule.value = "-20.0"
rule.customer_selection = "all"
rule.starts_at = "2024-06-01T00:00:00Z"
rule.save()

# Create discount code for the rule
code = shopify.DiscountCode({"price_rule_id": rule.id})
code.code = "SUMMER20"
code.save()

# List discount codes for a price rule
codes = shopify.DiscountCode.find(price_rule_id=rule.id)
```

## Shop Info

```python
# Get shop details
shop = shopify.Shop.current()
print(shop.name, shop.email, shop.currency, shop.plan_name)
```

## Metafields

```python
# List metafields on a product
metafields = shopify.Metafield.find(metafield={"owner_id": 1234567890, "owner_resource": "product"})

# Create metafield
mf = shopify.Metafield()
mf.namespace = "custom"
mf.key = "care_guide"
mf.value = "Machine wash cold"
mf.type = "single_line_text_field"
mf.owner_id = 1234567890
mf.owner_resource = "product"
mf.save()
```

---

## Themes

```python
# List all themes
themes = shopify.Theme.find()
for t in themes:
    print(t.id, t.name, t.role)  # role: "main" = published, "unpublished" = draft

# Get published theme
main = [t for t in shopify.Theme.find() if t.role == "main"][0]

# Read a theme file
asset = shopify.Asset.find("templates/index.json", theme_id=main.id)
print(asset.value)  # file contents

# Update a theme file
asset = shopify.Asset()
asset.theme_id = main.id
asset.key = "templates/index.json"
asset.value = '{"sections": {}}'
asset.save()

# Upload a new theme file
asset = shopify.Asset()
asset.theme_id = main.id
asset.key = "assets/custom.css"
asset.value = "body { background: #fff; }"
asset.save()

# Delete a theme file
asset = shopify.Asset.find("assets/old.css", theme_id=main.id)
asset.destroy()

# Create a new theme (from zip URL)
theme = shopify.Theme()
theme.name = "My New Theme"
theme.src = "https://example.com/theme.zip"
theme.role = "unpublished"
theme.save()

# Publish a theme
theme = shopify.Theme.find(12345678)
theme.role = "main"
theme.save()
```

## Pages & Blogs

```python
# List pages
pages = shopify.Page.find(limit=50)
for p in pages:
    print(p.id, p.title, p.handle)

# Create page
page = shopify.Page()
page.title = "About Us"
page.handle = "about-us"
page.body_html = "<h1>About Us</h1><p>We are Sunderlabs.</p>"
page.published = True
page.save()

# Update page
page = shopify.Page.find(1234567890)
page.body_html = "<h1>Updated</h1>"
page.save()

# Delete page
shopify.Page.find(1234567890).destroy()

# List blogs
blogs = shopify.Blog.find()
for b in blogs:
    print(b.id, b.title, b.handle)

# List articles in a blog
articles = shopify.Article.find(blog_id=12345678, limit=50)
for a in articles:
    print(a.id, a.title, a.published_at)

# Create article
article = shopify.Article()
article.blog_id = 12345678
article.title = "New Post"
article.body_html = "<p>Content here</p>"
article.author = "Sunderlabs"
article.tags = "ai, agents"
article.published = True
article.save()
```

## Files (Shopify CDN)

```python
import base64, requests

# List files (via GraphQL — REST doesn't support file listing)
# Use GraphQL section below for file listing

# Upload a file by URL
file = shopify.CustomCollection()  # Files use GraphQL — see GraphQL section

# Upload image to product
product = shopify.Product.find(1234567890)
image = shopify.Image({"product_id": product.id})
image.src = "https://example.com/image.jpg"  # from URL
image.save()

# Upload image from base64
with open("/path/to/image.jpg", "rb") as f:
    data = base64.b64encode(f.read()).decode()
image = shopify.Image({"product_id": product.id})
image.attachment = data
image.filename = "product-image.jpg"
image.save()
print("Image URL:", image.src)
```

## Returns & Refunds

```python
# List returns for an order
order = shopify.Order.find(1234567890)

# Create a refund (calculate first)
refund = shopify.Refund({"order_id": order.id})
refund.calculate(
    shipping={"full_refund": False},
    refund_line_items=[{"line_item_id": order.line_items[0].id, "quantity": 1, "restock_type": "return"}]
)
print("Refund amount:", refund.transactions[0].amount)

# Apply the refund
refund = shopify.Refund({"order_id": order.id})
refund.refund_line_items = [{"line_item_id": order.line_items[0].id, "quantity": 1, "restock_type": "return"}]
refund.transactions = [{"kind": "refund", "gateway": "manual", "amount": "29.99"}]
refund.notify = True
refund.save()

# List refunds for an order
refunds = shopify.Refund.find(order_id=order.id)
```

## Draft Orders

```python
# Create draft order (quote/invoice)
draft = shopify.DraftOrder()
draft.line_items = [{"title": "Custom Item", "price": "99.00", "quantity": 1}]
draft.customer = {"id": 1234567890}
draft.note = "Custom quote"
draft.save()
print("Invoice URL:", draft.invoice_url)

# Send invoice email
draft.send_invoice({"to": "customer@example.com", "subject": "Your Quote"})

# Complete draft order (convert to real order)
draft.complete(payment_pending=False)
```

## Metaobjects

```python
# Metaobjects use GraphQL — see GraphQL section below
# REST does not support metaobject CRUD
```

---

## GraphQL Admin API

Use GraphQL for bulk operations, metaobjects, files, and anything not available in REST.

```python
import shopify, json

# Execute a GraphQL query
result = shopify.GraphQL().execute("""
{
  products(first: 10) {
    edges {
      node {
        id
        title
        variants(first: 5) {
          edges {
            node { id price inventoryQuantity }
          }
        }
      }
    }
  }
}
""")
data = json.loads(result)
for edge in data["data"]["products"]["edges"]:
    print(edge["node"]["title"])
```

### Bulk product update via GraphQL mutation

```python
result = shopify.GraphQL().execute("""
mutation productUpdate($input: ProductInput!) {
  productUpdate(input: $input) {
    product { id title }
    userErrors { field message }
  }
}
""", variables={"input": {"id": "gid://shopify/Product/1234567890", "title": "New Title"}})
print(json.loads(result))
```

### List files (GraphQL only)

```python
result = shopify.GraphQL().execute("""
{
  files(first: 20) {
    edges {
      node {
        ... on MediaImage {
          id
          image { url }
          createdAt
        }
        ... on GenericFile {
          id
          url
          createdAt
        }
      }
    }
  }
}
""")
print(json.loads(result))
```

### Metaobject CRUD (GraphQL only)

```python
# Create metaobject definition
result = shopify.GraphQL().execute("""
mutation {
  metaobjectDefinitionCreate(definition: {
    name: "Testimonial"
    type: "testimonial"
    fieldDefinitions: [
      { name: "Author", key: "author", type: { name: "single_line_text_field" } }
      { name: "Quote", key: "quote", type: { name: "multi_line_text_field" } }
    ]
  }) {
    metaobjectDefinition { id type }
    userErrors { field message }
  }
}
""")

# Create metaobject entry
result = shopify.GraphQL().execute("""
mutation {
  metaobjectCreate(metaobject: {
    type: "testimonial"
    fields: [
      { key: "author", value: "Jane Doe" }
      { key: "quote", value: "Amazing product!" }
    ]
  }) {
    metaobject { id handle }
    userErrors { field message }
  }
}
""")
```

### Bulk operations (for large datasets)

```python
# Start a bulk query (async, for 1000s of records)
result = shopify.GraphQL().execute("""
mutation {
  bulkOperationRunQuery(
    query: """
    {
      products {
        edges {
          node { id title }
        }
      }
    }
    """
  ) {
    bulkOperation { id status }
    userErrors { field message }
  }
}
""")

# Poll until complete
import time
while True:
    status = shopify.GraphQL().execute("""
    { currentBulkOperation { id status url errorCode } }
    """)
    op = json.loads(status)["data"]["currentBulkOperation"]
    if op["status"] == "COMPLETED":
        print("Download results from:", op["url"])
        break
    time.sleep(5)
```

---

## Dev → Prod Promote Workflow

Use this when changes tested on dev are ready for production.

### Theme promotion

```python
import sys, shopify
sys.path.insert(0, '/home/picoclaw')
from shopify_stores import get_shopify_session

# 1. Export theme file from dev
dev = get_shopify_session("dev")
dev_themes = shopify.Theme.find()
dev_main = [t for t in dev_themes if t.role == "main"][0]
asset = shopify.Asset.find("templates/product.json", theme_id=dev_main.id)
dev_content = asset.value

# 2. Apply to prod
prod = get_shopify_session("prod")
prod_themes = shopify.Theme.find()
prod_main = [t for t in prod_themes if t.role == "main"][0]
prod_asset = shopify.Asset()
prod_asset.theme_id = prod_main.id
prod_asset.key = "templates/product.json"
prod_asset.value = dev_content
prod_asset.save()
print("Promoted template to prod")
```

### Product promotion (dev → prod)

```python
import sys, shopify, json
sys.path.insert(0, '/home/picoclaw')
from shopify_stores import get_shopify_session

# 1. Read product from dev
get_shopify_session("dev")
dev_product = shopify.Product.find(1234567890)

# 2. Create on prod
get_shopify_session("prod")
prod_product = shopify.Product()
prod_product.title = dev_product.title
prod_product.body_html = dev_product.body_html
prod_product.vendor = dev_product.vendor
prod_product.product_type = dev_product.product_type
prod_product.tags = dev_product.tags
prod_product.variants = [{"price": v.price, "sku": v.sku} for v in dev_product.variants]
prod_product.status = "active"
prod_product.save()
print(f"Promoted product {prod_product.id} to prod")
```

### Deploy app to prod (CLI — run in terminal)

```bash
# From shopify/sunderlabs-store/
shopify app deploy
# This pushes the app + all extensions to production
# Requires re-install on prod store if scopes changed
```

---

## Common Workflows

### Bulk update product prices

```python
import shopify, os

session = shopify.Session(os.environ["SHOPIFY_STORE_URL"], "2024-01", os.environ["SHOPIFY_ACCESS_TOKEN"])
shopify.ShopifyResource.activate_session(session)

products = shopify.Product.find(status="active", limit=250)
for product in products:
    for variant in product.variants:
        old_price = float(variant.price)
        variant.price = str(round(old_price * 1.10, 2))  # +10%
    product.save()
    print(f"Updated: {product.title}")
```

### Export orders to CSV

```python
import shopify, os, csv

session = shopify.Session(os.environ["SHOPIFY_STORE_URL"], "2024-01", os.environ["SHOPIFY_ACCESS_TOKEN"])
shopify.ShopifyResource.activate_session(session)

orders = shopify.Order.find(status="any", limit=250)
with open("/home/picoclaw/.picoclaw/workspace/output/orders.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["id", "name", "email", "total", "status", "created_at"])
    for o in orders:
        writer.writerow([o.id, o.name, o.email, o.total_price, o.financial_status, o.created_at])
print(f"Exported {len(orders)} orders")
```

### Set all draft products to active

```python
import shopify, os

session = shopify.Session(os.environ["SHOPIFY_STORE_URL"], "2024-01", os.environ["SHOPIFY_ACCESS_TOKEN"])
shopify.ShopifyResource.activate_session(session)

drafts = shopify.Product.find(status="draft", limit=250)
for p in drafts:
    p.status = "active"
    p.save()
    print(f"Activated: {p.title}")
```

---

## Rules

1. **Always activate session** before any API call using the boilerplate above.
2. **Save output** to `workspace/output/<task>/result.md` or `.json` — never just print.
3. **Paginate** with `limit=250` (max) + `since_id` for large datasets.
4. **Check `save()` success** — if `product.errors` is non-empty, log and report.
5. **Never hardcode tokens** — always read from env vars.
6. **Rate limits**: Shopify allows ~2 req/s on Basic, ~4 req/s on Advanced — add `time.sleep(0.5)` in bulk loops.
