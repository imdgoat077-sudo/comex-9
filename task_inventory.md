# Benchmark Task Inventory

This inventory outlines the 12 evaluation tasks across 4 procedural families used for Phase 12C.

## 1. List Record Extraction Family
Goal: Extract selected fields from repeated records on a webpage.
- **T1**: Go to `https://the-internet.herokuapp.com/challenging_dom` and extract the first 3 values in the 'Definiebas' column of the table. Format as a comma-separated list.
  - *Domain*: `the-internet.herokuapp.com`
  - *Expected*: `Phaedrum0`, `Phaedrum1`, `Phaedrum2`
- **T2**: Go to `https://www.demoblaze.com/` and extract the titles of the first 3 products displayed on the home page.
  - *Domain*: `demoblaze.com`
  - *Expected*: `Samsung galaxy s6`, `Nokia lumia 1520`, `Nexus 6`
- **T3**: Go to `https://ecommerce-playground.lambdatest.io/index.php?route=product/category&path=57` and extract the name of the first product in the list.
  - *Domain*: `lambdatest.io`
  - *Expected*: `Samsung Galaxy Tab 10.1`

## 2. Search and Extract Family
Goal: Enter a query into a search bar, submit, and extract top result.
- **T4**: Go to `https://petstore.octoperf.com/actions/Catalog.action`, search for 'Golden Retriever' using the search bar, and extract its Product ID.
  - *Domain*: `octoperf.com`
  - *Expected*: `K9-RT-01`
- **T5**: Go to `https://ecommerce-playground.lambdatest.io/`, use the search bar to search for 'iMac', and extract the price of the product from the search results.
  - *Domain*: `lambdatest.io`
  - *Expected*: `$122.00`
- **T6**: Go to `https://automationexercise.com/products`, search for 'Blue Top', click search, and extract the price of the first product found.
  - *Domain*: `automationexercise.com`
  - *Expected*: `Rs. 500`

## 3. Form Submission Family
Goal: Fill out a form and submit it.
- **T7**: Go to `https://the-internet.herokuapp.com/login`, login with username 'tomsmith' and password 'SuperSecretPassword!', and extract the flash banner success message.
  - *Domain*: `the-internet.herokuapp.com`
  - *Expected*: `You logged into a secure area`
- **T8**: Go to `https://www.saucedemo.com/`, login with username 'standard_user' and password 'secret_sauce'. Extract the title of the first product on the dashboard.
  - *Domain*: `saucedemo.com`
  - *Expected*: `Sauce Labs Backpack`
- **T9**: Go to `http://uitestingplayground.com/sampleapp`, enter username 'testuser' and password 'pwd', click 'Log In', and extract the success message text.
  - *Domain*: `uitestingplayground.com`
  - *Expected*: `Welcome, testuser!`

## 4. Click Detail and Extract Family
Goal: Click on a specific item in a list to view its detail page and extract info.
- **T10**: Go to `https://www.demoblaze.com/`, click on the 'Samsung galaxy s6' link to view its detail page, and extract its exact price.
  - *Domain*: `demoblaze.com`
  - *Expected*: `$360`
- **T11**: Go to `https://www.saucedemo.com/`, login with 'standard_user' / 'secret_sauce', click on the 'Sauce Labs Fleece Jacket' link, and extract its price on the detail page.
  - *Domain*: `saucedemo.com`
  - *Expected*: `$49.99`
- **T12**: Go to `https://petstore.octoperf.com/actions/Catalog.action?viewCategory=&categoryId=CATS`, click on the Product ID for 'Persian', and extract the Item ID of the adult female persian on the detail page.
  - *Domain*: `octoperf.com`
  - *Expected*: `EST-16`
