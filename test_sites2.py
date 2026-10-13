import urllib.request
urls = [
    "http://uitestingplayground.com/",
    "https://www.saucedemo.com/",
    "https://ecommerce-playground.lambdatest.io/",
    "https://automationexercise.com/"
]
for u in urls:
    try:
        req = urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0'})
        urllib.request.urlopen(req, timeout=5)
        print(f"OK: {u}")
    except Exception as e:
        print(f"FAIL: {u} - {e}")
