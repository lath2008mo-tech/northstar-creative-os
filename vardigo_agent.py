import json
import logging
import os
import urllib.parse
import urllib.request

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

STORE = os.getenv("SHOPIFY_STORE", "vardigo.myshopify.com")
TOKEN = os.getenv("SHOPIFY_ACCESS_TOKEN", "")
CLIENT_ID = os.getenv("SHOPIFY_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("SHOPIFY_CLIENT_SECRET", "")
AUTO = os.getenv("AUTO", "rapport")
API = "2026-10"


def request(method, url, data=None, headers=None, form=False):
    payload = None
    hdrs = dict(headers or {})
    if data is not None:
        if form:
            payload = urllib.parse.urlencode(data).encode()
            hdrs["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            payload = json.dumps(data).encode()
            hdrs["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=payload, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            body = res.read().decode()
            return res.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as err:
        raw = err.read().decode()
        try:
            parsed = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            parsed = {"error": raw}
        return err.code, parsed


def ensure_token():
    global TOKEN
    if TOKEN or not CLIENT_ID or not CLIENT_SECRET:
        return
    status, body = request(
        "POST",
        f"https://{STORE}/admin/oauth/access_token",
        data={
            "grant_type": "client_credentials",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        },
        form=True,
    )
    if status >= 300:
        logging.error("Shopify gav ingen nyckel: %s", status)
        return
    TOKEN = body.get("access_token", "")


def admin_headers():
    return {"X-Shopify-Access-Token": TOKEN}


def admin_get(path):
    if not TOKEN:
        return None
    status, body = request("GET", f"https://{STORE}/admin/api/{API}/{path}", headers=admin_headers())
    logging.info("GET %s -> %s", path, status)
    return body if status < 300 else None


def fetch_products():
    status, body = request("GET", f"https://{STORE}/products.json?limit=50")
    if status >= 300:
        raise SystemExit(f"Kunde inte lasa produkter: {status}")
    items = []
    for product in body.get("products", []):
        variant = (product.get("variants") or [{}])[0]
        items.append({
            "id": product["id"],
            "title": product["title"],
            "price": variant.get("price", "?"),
        })
    return items


def hook_for(title):
    low = title.lower()
    if any(word in low for word in ("frost", "isskrapa", "sno", "snö", "vindruta")):
        return "Morgonen ska inte borja med skrapa."
    if "handduk" in low or "badrock" in low:
        return "Handduken glider av. Den har sitter kvar."
    if "pals" in low or "päls" in low or "hund" in low or "katt" in low:
        return "Palsen ska inte sitta kvar i soffan."
    return title.split("–")[0].strip() + " ska inte ta tid."


def copy_for(title, price):
    return f"{hook_for(title)}\n{title}. {price} kr.\nLanken i bio."


def run():
    ensure_token()
    products = fetch_products()
    orders = admin_get("orders.json?status=any&limit=5")
    lines = [f"# {STORE}", f"Lage: {AUTO}", ""]
    if orders and orders.get("orders") is not None:
        lines.append(f"Ordrar lasta: {len(orders['orders'])}")
    elif TOKEN:
        lines.append("Ordrar gick inte att lasa.")
    else:
        lines.append("Ingen nyckel. Laser bara oppna produkter.")
    for product in products:
        text = copy_for(product["title"], product["price"])
        lines += [f"## {product['title']}", f"{product['price']} kr", text, ""]
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rapport.md")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines))
    print("Klar. Oppna rapport.md i samma mapp.")


if __name__ == "__main__":
    run()
