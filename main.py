import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import csv
import requests
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from abebooks import AbeBooks
from ebay import setup_tokens

# ========================
# GLOBALS
# ========================
session = requests.Session()
session.headers.update({"Connection": "keep-alive"})

token_lock = threading.Lock()
access_token, access_token_expiry_time = setup_tokens()  # ✅ Only called ONCE now

start_time = None
lock = threading.Lock()

# ========================
# ABE BOOKS
# ========================
def get_abe_price_isbn(isbn):
    abebooks = AbeBooks()
    for _ in range(3):
        try:
            response = abebooks.getPriceByISBN(isbn)
            price = response.get('pricingInfoForBestUsed')
            if price:
                return price.get('bestPriceInPurchaseCurrencyValueOnly')
            return None
        except requests.RequestException:
            time.sleep(2)
    return None


def get_abe_price_other(author, title):
    abebooks = AbeBooks()
    for _ in range(3):
        try:
            response = abebooks.getPriceByAuthorTitle(author, title)
            price = response.get('pricingInfoForBestUsed')
            if price:
                return price.get('bestPriceInPurchaseCurrencyValueOnly')
            return None
        except requests.RequestException:
            time.sleep(2)
    return None


# ========================
# EBAY
# ========================
def get_ebay_prices(query, mode="both"):
    global access_token, access_token_expiry_time

    with token_lock:
        if access_token_expiry_time - 30 < time.time():
            access_token, access_token_expiry_time = setup_tokens()

    headers = {
        "Authorization": f"Bearer {access_token}",
        "X-EBAY-C-MARKETPLACE-ID": "EBAY_GB"
    }

    def fetch(params):
        try:
            response = session.get(
                "https://api.ebay.com/buy/browse/v1/item_summary/search",
                headers=headers,
                params=params,
                timeout=10
            )
            if response.status_code != 200:
                return []
            return response.json().get("itemSummaries", [])
        except:
            return []

    active_items = []
    sold_items = []

    if mode in ("active", "both"):
        active_items = fetch({"q": query})

    if mode in ("sold", "both"):
        sold_items = fetch({"q": query, "filter": "soldItems:true"})

    def split_prices(items):
        global_prices = []
        uk_prices = []
        for item in items:
            try:
                price = float(item["price"]["value"])
                global_prices.append(price)
                if item.get("listingMarketplaceId") == "EBAY_GB":
                    uk_prices.append(price)
            except:
                continue
        return global_prices, uk_prices

    active_global, active_uk = split_prices(active_items)
    sold_global, sold_uk = split_prices(sold_items)

    def stats(prices):
        if not prices:
            return {"min": None, "max": None, "avg": None, "qty": 0}
        return {
            "min": min(prices),
            "max": max(prices),
            "avg": sum(prices) / len(prices),
            "qty": len(prices)
        }

    return {
        "active_global": stats(active_global),
        "active_uk": stats(active_uk),
        "sold_global": stats(sold_global),
        "sold_uk": stats(sold_uk),
        "image": active_items[0].get("image", {}).get("imageUrl", "") if active_items else ""
    }


# ========================
# PROCESSING
# ========================
def process_row(row, ebay_mode):
    isbn = row.get('ISBN', '').strip().split(" ")[0]

    if isbn:
        row['Abe Price'] = get_abe_price_isbn(isbn)
        ebay_data = get_ebay_prices(isbn, ebay_mode)

        if not any([
            ebay_data['active_global']['qty'],
            ebay_data['sold_global']['qty'],
            ebay_data['active_uk']['qty'],
            ebay_data['sold_uk']['qty']
        ]):
            author = row.get('Author', '').strip()
            title = row.get('Title', '').strip()
            ebay_data = get_ebay_prices(f"{author} {title}", ebay_mode)
    else:
        author = row.get('Author', '').strip()
        title = row.get('Title', '').strip()
        row['Abe Price'] = get_abe_price_other(author, title)
        ebay_data = get_ebay_prices(f"{author} {title}", ebay_mode)

    if row.get('Abe Price'):
        row['Image'] = f'=IMAGE("https://pictures.abebooks.com/isbn/{isbn}.jpg")'

    if ebay_data and any([
        ebay_data['active_global']['qty'],
        ebay_data['sold_global']['qty'],
        ebay_data['active_uk']['qty'],
        ebay_data['sold_uk']['qty']
    ]):
        row['eBay Active Global Min'] = ebay_data['active_global']['min']
        row['eBay Active Global Avg'] = ebay_data['active_global']['avg']
        row['eBay Active Global Qty'] = ebay_data['active_global']['qty']
        row['eBay Active UK Min'] = ebay_data['active_uk']['min']
        row['eBay Active UK Avg'] = ebay_data['active_uk']['avg']
        row['eBay Active UK Qty'] = ebay_data['active_uk']['qty']
        row['eBay Sold Global Min'] = ebay_data['sold_global']['min']
        row['eBay Sold Global Max'] = ebay_data['sold_global']['max']
        row['eBay Sold Global Avg'] = ebay_data['sold_global']['avg']
        row['eBay Sold Global Qty'] = ebay_data['sold_global']['qty']
        row['eBay Sold UK Min'] = ebay_data['sold_uk']['min']
        row['eBay Sold UK Max'] = ebay_data['sold_uk']['max']
        row['eBay Sold UK Avg'] = ebay_data['sold_uk']['avg']
        row['eBay Sold UK Qty'] = ebay_data['sold_uk']['qty']

        if not row.get('Image'):
            row['Image'] = f'=IMAGE("{ebay_data["image"]}")'

    # ✅ Min Price = minimum across all prices (Abe + all eBay mins)
    all_prices = [
        row.get('Abe Price'),
        ebay_data['active_global']['min'],
        ebay_data['active_uk']['min'],
        ebay_data['sold_global']['min'],
        ebay_data['sold_uk']['min'],
    ]
    valid_prices = [float(p) for p in all_prices if p is not None]
    row['Min Price'] = min(valid_prices) if valid_prices else None

    return row


def process_csv(input_file, output_file, root, update_progress, ebay_mode):  # ✅ mode passed in
    with open(input_file, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = [
            'Image', 'Min Price', 'Abe Price',
            'eBay Active Global Min', 'eBay Active Global Avg', 'eBay Active Global Qty',
            'eBay Active UK Min', 'eBay Active UK Avg', 'eBay Active UK Qty',
            'eBay Sold Global Min', 'eBay Sold Global Max', 'eBay Sold Global Avg', 'eBay Sold Global Qty',
            'eBay Sold UK Min', 'eBay Sold UK Max', 'eBay Sold UK Avg', 'eBay Sold UK Qty',
            'Error',
        ] + reader.fieldnames

    results = [None] * len(rows)
    MAX_WORKERS = 8

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(process_row, row, ebay_mode): i for i, row in enumerate(rows)}  # ✅ pass mode

        for count, future in enumerate(as_completed(futures), start=1):
            idx = futures[future]
            results[idx] = future.result()
            root.after(0, update_progress, count, len(rows))

    with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(results)

    # ✅ Show success message from main thread
    root.after(0, lambda: messagebox.showinfo("Success", f"CSV processed! Saved as {output_file}"))


# ========================
# GUI
# ========================
def select_file():
    file_path = filedialog.askopenfilename(filetypes=[("CSV Files", "*.csv")])
    if file_path:
        entry_file.delete(0, tk.END)
        entry_file.insert(0, file_path)

def save_file():
    file_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV Files", "*.csv")])
    return file_path if file_path else None

def update_progress(count, total):
    global start_time
    progress_percent = int((count / total) * 100)
    progress_bar['value'] = progress_percent
    progress_label.config(text=f"Progress: {progress_percent}%")
    completed_label.config(text=f"Completed: {count}/{total}")

    if start_time:
        elapsed_time = int(time.time() - start_time)
        timer_label.config(text=f"Time Elapsed: {elapsed_time}s")
        time_left = (elapsed_time / count) * (total - count) if count > 0 else 0
        minutes_left = int(time_left // 60)
        seconds_left = int(time_left % 60)
        time_left_label.config(text=f"Estimated Time Left: {minutes_left}m {seconds_left}s")


def start_processing():
    global start_time
    input_file = entry_file.get()
    if not input_file:
        messagebox.showerror("Error", "Please select an input CSV file")
        return

    output_file = save_file()
    if not output_file:
        return

    progress_bar['value'] = 0
    progress_label.config(text="Progress: 0%")
    completed_label.config(text="Completed: 0")
    timer_label.config(text="Time Elapsed: 0s")
    time_left_label.config(text="Estimated Time Left: 0s")

    start_time = time.time()

    ebay_mode = listing_mode.get()  # ✅ Read StringVar on main thread BEFORE launching thread

    # ✅ Run process_csv in a background thread so the GUI doesn't freeze/crash
    thread = threading.Thread(
        target=process_csv,
        args=(input_file, output_file, root, update_progress, ebay_mode),
        daemon=True
    )
    thread.start()


# ========================
# RUN GUI
# ========================
root = tk.Tk()
root.title("Book Price Fetcher")
root.geometry("500x320")

listing_mode = tk.StringVar(value="both")

tk.Label(root, text="eBay Listing Type:").pack(pady=5)
tk.Radiobutton(root, text="Current Listings", variable=listing_mode, value="active").pack()
tk.Radiobutton(root, text="Sold Listings", variable=listing_mode, value="sold").pack()
tk.Radiobutton(root, text="Both", variable=listing_mode, value="both").pack()

tk.Label(root, text="Select CSV File:").pack(pady=5)
entry_file = tk.Entry(root, width=40)
entry_file.pack(pady=5)

tk.Button(root, text="Browse", command=select_file).pack(pady=5)
tk.Button(root, text="Process CSV", command=start_processing).pack(pady=10)

progress_bar = ttk.Progressbar(root, length=300, mode='determinate')
progress_bar.pack(pady=10)

progress_label = tk.Label(root, text="Progress: 0%")
progress_label.pack()

completed_label = tk.Label(root, text="Completed: 0")
completed_label.pack()

timer_label = tk.Label(root, text="Time Elapsed: 0s")
timer_label.pack()

time_left_label = tk.Label(root, text="Estimated Time Left: 0s")
time_left_label.pack()

root.mainloop()