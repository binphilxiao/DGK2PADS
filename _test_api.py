"""Quick API test to debug filter format"""
import json, os
from digikey_api import DigiKeyClient

# Load config
cfg_path = os.path.join(os.path.expanduser("~"), ".digikey_pads_config.json")
with open(cfg_path) as f:
    cfg = json.load(f)

client = DigiKeyClient(cfg["client_id"], cfg["client_secret"], use_sandbox=False)
client._ensure_auth()

# Test 1: keyword only + manufacturer + category (no param filters)
print("=== Test 1: Mfr only ===")
r = client.search_keyword("resistor", limit=1, category_id=52, manufacturer_ids=[13])
print("ProductsCount:", r.get("ProductsCount", 0))

# Test 2: keyword + manufacturer + ONE param filter (tolerance ±1%)
print("\n=== Test 2: Mfr + Tolerance ===")
try:
    r = client.search_keyword("resistor", limit=1, category_id=52, manufacturer_ids=[13],
        parameter_filters=[{"ParameterId": 3, "FilterValues": [{"Id": "1131"}]}])
    print("ProductsCount:", r.get("ProductsCount", 0))
except Exception as e:
    print("ERROR:", e)

# Test 3: keyword + manufacturer + package filter (0603)
print("\n=== Test 3: Mfr + Package ===")
try:
    r = client.search_keyword("resistor", limit=1, category_id=52, manufacturer_ids=[13],
        parameter_filters=[{"ParameterId": 16, "FilterValues": [{"Id": "39246"}]}])
    print("ProductsCount:", r.get("ProductsCount", 0))
except Exception as e:
    print("ERROR:", e)

# Test 4: all 3 param filters
print("\n=== Test 4: Mfr + all 3 params ===")
try:
    r = client.search_keyword("resistor", limit=1, category_id=52, manufacturer_ids=[13],
        parameter_filters=[
            {"ParameterId": 16, "FilterValues": [{"Id": "39246"}]},
            {"ParameterId": 2, "FilterValues": [{"Id": "14064"}]},
            {"ParameterId": 3, "FilterValues": [{"Id": "1131"}]},
        ])
    print("ProductsCount:", r.get("ProductsCount", 0))
except Exception as e:
    print("ERROR:", e)

print("\nDone. Check _debug_request.json for the last request body.")
