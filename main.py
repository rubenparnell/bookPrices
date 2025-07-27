import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import csv
import requests
from abebooks import AbeBooks
from ebay import setup_tokens
import time

def get_abe_price_isbn(isbn):
    abebooks = AbeBooks()
    count = 0
    while count < 3:
        try:
            response = abebooks.getPriceByISBN(isbn)
            price = response.get('pricingInfoForBestUsed')
            if price:
                return price.get('bestPriceInPurchaseCurrencyValueOnly', None)
            return None
        except requests.RequestException:
            count += 1
            time.sleep(5)
    return 'Error'

def get_abe_price_other(author, title):
    abebooks = AbeBooks()
    count = 0
    while count < 3:
        try:
            response = abebooks.getPriceByAuthorTitle(author, title)
            price = response.get('pricingInfoForBestUsed')
            if price:
                return price.get('bestPriceInPurchaseCurrencyValueOnly', None)
            return None
        except requests.RequestException:
            count += 1
            time.sleep(5)
    return 'Error'

def get_ebay_prices(query):
    global access_token_expiry_time, access_token
    
    if access_token_expiry_time-30 < time.time():
        access_token, access_token_expiry_time = setup_tokens()

    print(access_token_expiry_time)
    print(time.time())

    headers = {"Authorization": f"Bearer {access_token}", "X-EBAY-C-MARKETPLACE-ID" : "EBAY_GB"}
    params = {"q": query}
    response = requests.get("https://api.ebay.com/buy/browse/v1/item_summary/search", headers=headers, params=params)
    response.raise_for_status()
    data = response.json()

    if len(data.get("itemSummaries", [])) == 0:
        return None

    all_prices = []
    uk_prices = []

    # Extract price information
    for item in data.get("itemSummaries", []):
        price = float(item["price"]["value"])
        all_prices.append(price)
        
        # Filter UK listings
        if item.get("listingMarketplaceId") == "EBAY_GB":
            uk_prices.append(price)

    # Calculate lowest and average prices
    def calculate_prices(prices):
        if not prices:
            return None, None  # No items found
        lowest_price = min(prices)
        avg_price = sum(prices) / len(prices)
        return lowest_price, avg_price

    lowest_all, avg_all = calculate_prices(all_prices)
    lowest_uk, avg_uk = calculate_prices(uk_prices)

    return {
        "global": {"min": lowest_all, "avg": avg_all, "qty": len(all_prices)},
        "uk": {"min": lowest_uk, "avg": avg_uk, "qty": len(uk_prices)},
        "image": data.get("itemSummaries", [])[0].get("image", {}).get("imageUrl", "")
    }

start_time = None

def process_csv(input_file, output_file, root, update_progress):
    with open(input_file, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        fieldnames = ['Image', 'Min Price', 'Abe Price', 'eBay UK Price min', 'eBay UK qty', 'eBay Global Price min', 'eBay Global qty'] + reader.fieldnames
        rows = list(reader)
        total_rows = len(rows)

        for index, row in enumerate(rows):
            isbn = row.get('ISBN', '').strip().split(" ")[0]
            if isbn:
                row['Abe Price'] = get_abe_price_isbn(isbn)

                ebay_data = get_ebay_prices(isbn)
                if not ebay_data:
                    author = row.get('Author', '').strip()
                    title = row.get('Title', '').strip()
                    ebay_data = get_ebay_prices(f"{author} {title}")
                    
            else:
                author = row.get('Author', '').strip()
                title = row.get('Title', '').strip()

                row['Abe Price'] = get_abe_price_other(author, title)
                ebay_data = get_ebay_prices(f"{author} {title}")

            if ebay_data:
                row['eBay UK Price min'] = ebay_data['uk']['min']
                row['eBay UK qty'] = ebay_data['uk']['qty']
                row['eBay Global Price min'] = ebay_data['global']['min']
                row['eBay Global qty'] = ebay_data['global']['qty']
                row['Image'] = f'=IMAGE("{ebay_data["image"]}")'

                if row['Abe Price']:
                    row['Min Price'] = min(float(row['Abe Price']), float(ebay_data['global']['min']))
                else:
                    row['Min Price'] = float(ebay_data['global']['min'])

            else:
                row['Image'] = f'=IMAGE("https://pictures.abebooks.com/isbn/{isbn}.jpg")'
                row['Min Price'] = row['Abe Price']

            # Update progress bar
            update_progress(index+1, total_rows)
            root.update()  # Ensure UI updates immediately

    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

def select_file():
    file_path = filedialog.askopenfilename(filetypes=[("CSV Files", "*.csv")])
    if file_path:
        entry_file.delete(0, tk.END)
        entry_file.insert(0, file_path)

def save_file():
    file_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV Files", "*.csv")])
    return file_path if file_path else None

def update_progress(count, total):
    global start_time  # Use the global variable
    progress_percent = int((count / total) * 100)
    progress_bar['value'] = progress_percent
    progress_label.config(text=f"Progress: {progress_percent}%")
    completed_label.config(text=f"Completed: {count}/{total}")

    if start_time:
        elapsed_time = int(time.time() - start_time)
        timer_label.config(text=f"Time Elapsed: {elapsed_time}s")

        time_left = (elapsed_time / count) * (total - count)  # Time remaining in seconds
        minutes_left = int(time_left // 60)  # Whole minutes
        seconds_left = int(time_left % 60)   # Remaining seconds

        time_left_label.config(text=f"Estimated Time Left: {minutes_left}m {seconds_left}s")

    root.update_idletasks()  # Refresh GUI
    
def start_processing():
    global start_time  # Ensure we update the global timer variable
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

    start_time = time.time()  # Start timer

    # Call the function with progress tracking
    process_csv(input_file, output_file, root, update_progress)

    messagebox.showinfo("Success", f"CSV file processed successfully! Saved as {output_file}")


access_token, access_token_expiry_time = setup_tokens()

# GUI Setup
root = tk.Tk()
root.title("Book Price Fetcher")
root.geometry("400x320")

tk.Label(root, text="Select CSV File:").pack(pady=5)
entry_file = tk.Entry(root, width=40)
entry_file.pack(pady=5)

tk.Button(root, text="Browse", command=select_file).pack(pady=5)
tk.Button(root, text="Process CSV", command=start_processing).pack(pady=10)

progress_bar = ttk.Progressbar(root, length=300, mode='determinate')
progress_bar.pack(pady=10)

# Labels for additional progress information
progress_label = tk.Label(root, text="Progress: 0%")
progress_label.pack()

completed_label = tk.Label(root, text="Completed: 0")
completed_label.pack()

timer_label = tk.Label(root, text="Time Elapsed: 0s")
timer_label.pack()

time_left_label = tk.Label(root, text="Estimated Time Left: 0s")
time_left_label.pack()

root.mainloop()