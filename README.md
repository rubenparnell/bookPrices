# Book Price Fetcher

A Python GUI tool that fetches prices for books from AbeBooks and eBay based on ISBN, author, or title. An output csv file is created with the prices.

# Features

* GUI interface for selecting input/output CSV files
* Fetches book prices from AbeBooks and eBay (via ISBN or Author + Title)
* Retrieves global and UK-specific price data from eBay
* Automatically embeds book cover images via Excel-compatible formula
* Tracks progress with estimated time remaining during processing

# Requirements

* Python 3.7+

# Dependencies

Create a virtual environment and install required packages using pip:

```Bash
pip install -r requirements.txt
```

You’ll also need to:
* Add your eBay Access Token and Refresh Token json files to the main directory. These files must be named `ebayAccessToken.json` and `ebayRefreshToken.json`.
* Add your eBay client id, client secret, and redirect uri to a python file called `config.py`, in this format:

```python
client_id = "your-client-id"
client_secret = "your-client-secret"
redirect_uri = "your-redirect-uri"
```

# Installation

1. Clone or download this repository.
2. Install the required Python modules.
3. Add your ebay API tokens to the folder.
4. Run the script using Python:

   `python main.py`

# How to Use

1. Prepare a CSV file with the following columns:
   * `ISBN` (if available)
   * `Author`
   * `Title`
   * Any other metadata (will be retained in the output)
2. Launch the script:
   * Click **Browse** to select your input CSV.
   * Click **Process CSV** to choose a save location for the output file.
   * Wait for the program to run (this can take a long time for large files).
   * When complete, the final CSV will contain:
     * AbeBooks price
     * eBay UK and Global prices
     * Quantity available
     * Minimum price comparison
     * Embedded image from eBay using Excel’s `=IMAGE(...)` formula.

# Notes

* AbeBooks and eBay API calls include retry logic to handle temporary failures.
* Token expiry for eBay is automatically managed.
