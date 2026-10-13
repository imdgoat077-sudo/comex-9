import urllib.request
urls = [
    "https://the-internet.herokuapp.com/challenging_dom",
    "https://www.demoblaze.com/",
    "https://magento.softwaretestingboard.com/men/tops-men/jackets-men.html",
    "http://computer-database.gatling.io/computers",
    "https://petstore.octoperf.com/actions/Catalog.action",
    "https://the-internet.herokuapp.com/login",
    "https://practicetestautomation.com/practice-test-login/",
    "https://parabank.parasoft.com/parabank/register.htm"
]
for u in urls:
    try:
        urllib.request.urlopen(u, timeout=5)
        print(f"OK: {u}")
    except Exception as e:
        print(f"FAIL: {u} - {e}")
