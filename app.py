import streamlit as st
import pandas as pd
import random
import string
import json
from datetime import datetime
from pymongo import MongoClient
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from pymongo import MongoClient
from pymongo.errors import AutoReconnect
import time


# ===============================
#  MONGO CONNECTION (Production Safe)
# ===============================

MONGO_URI = st.secrets["mongo"]["uri"]
DB_NAME = st.secrets["mongo"]["database"]
@st.cache_resource
def get_client():
    return MongoClient(
        MONGO_URI,
        connectTimeoutMS=30000,
        socketTimeoutMS=30000,
        serverSelectionTimeoutMS=30000
    )

def safe_get_db():
    client = get_client()
    for _ in range(5):
        try:
            client.admin.command("ping")
            return client
        except AutoReconnect:
            time.sleep(2)
    st.error("MongoDB connection failed after retries.")
    return None

client = safe_get_db()
if client:
    db = client[DB_NAME]
else:
    st.stop()

st.title("Billing App")
items_col = db["items"]
bills_col = db["bills"]

# ===============================
#  PDF GENERATION
# ===============================
def generate_bill_pdf(bill, items):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    c.setFont("Helvetica-Bold", 18)
    c.drawString(250, 750, "ADS Group")

    c.setFont("Helvetica", 12)
    c.drawString(50, 730, f"Bill ID: {bill['bill_id']}")
    c.drawString(50, 715, f"Buyer: {bill['buyer_name']}")
    c.drawString(50, 700, f"Mobile: {bill['buyer_mobile']}")
    c.drawString(50, 685, f"Date: {bill['date']}")

    y = 660
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, y, "Item")
    c.drawString(250, y, "Qty")
    c.drawString(300, y, "Price")
    c.drawString(380, y, "Total")
    y -= 20
    c.setFont("Helvetica", 10)

    for it in items:
        c.drawString(50, y, it["item_id"])
        c.drawString(250, y, str(it["quantity"]))
        c.drawString(300, y, str(it["sell_price"]))
        c.drawString(380, y, str(it["quantity"] * it["sell_price"]))
        y -= 20

    y -= 20
    c.drawString(50, y, f"Total Amount: {bill['total_amount']}")

    c.setFont("Helvetica-Oblique", 9)
    c.drawString(200, 50, "Thank You. Visit us again")
    c.drawString(150, 40, "Address: Chatauni Road, NH-28A Near J. J. Kanak Hospital, Motihari, 845401")
    c.drawString(200,30,'ads.company.group@gmail.com  |  7079704030')

    c.save()
    buffer.seek(0)
    return buffer

# ===============================
#  VALIDATION HELPERS
# ===============================
def is_valid_mobile(m):
    return m.isdigit() and len(m) == 10

# ===============================
#  SIDEBAR MENU
# ===============================
st.sidebar.title("Admin Panel")
menu = st.sidebar.radio("Navigation", ["Add Item", "Show Items", "Generate Bill", "Show Bills"])

# ===============================
#  ADD ITEM
# ===============================
if menu == "Add Item":
    st.header("Add / Update Item")

    item_id = st.text_input("Item ID")
    category = st.text_input("Category")
    subcategory = st.text_input("Subcategory")
    cost_price = st.number_input("Cost Price", min_value=0)
    sell_price = st.number_input("Sell Price", min_value=0)
    quantity = st.number_input("Quantity", min_value=0)

    if st.button("Save Item"):
        if not item_id or not category or not subcategory:
            st.error("All fields required!")
        else:
            existing = items_col.find_one({"item_id": item_id})

            if existing:
                # Increase quantity instead of duplicate insert
                new_qty = existing["quantity"] + quantity
                items_col.update_one({"item_id": item_id}, {"$set": {"quantity": new_qty}})
                st.success(f"Item exists. Updated quantity to {new_qty}.")
            else:
                items_col.insert_one({
                    "item_id": item_id,
                    "category": category,
                    "subcategory": subcategory,
                    "cost_price": cost_price,
                    "sell_price": sell_price,
                    "quantity": quantity
                })
                st.success("Item added successfully!")

# ===============================
#  SHOW ITEMS (With Edit Option)
# ===============================
elif menu == "Show Items":
    st.header("Items Available in Stock")
    items = list(items_col.find({}, {"_id": 0}))

    df = pd.DataFrame(items)
    st.dataframe(df)

    st.subheader("Edit an Existing Item")
    all_ids = [i["item_id"] for i in items]
    edit_id = st.selectbox("Select Item", ["None"] + all_ids)

    if edit_id != "None":
        doc = items_col.find_one({"item_id": edit_id})

        new_price = st.number_input("New Sell Price", min_value=0, value=doc["sell_price"])
        new_qty = st.number_input("New Quantity", min_value=0, value=doc["quantity"])

        if st.button("Update Item"):
            items_col.update_one({"item_id": edit_id}, {"$set": {"sell_price": new_price, "quantity": new_qty}})
            st.success("Item updated successfully!")

# ===============================
#  GENERATE BILL
# ===============================
elif menu == "Generate Bill":
    st.header("Generate Bill")

    buyer_name = st.text_input("Buyer Name")
    buyer_mobile = st.text_input("Buyer Mobile")

    if buyer_mobile and not is_valid_mobile(buyer_mobile):
        st.error("Enter a valid 10-digit mobile number")

    st.subheader("Select Items")

    all_items = list(items_col.find({}, {"_id": 0}))

    selected_items = []
    total_amount = 0

    for it in all_items:
        col1, col2 = st.columns([3,1])
        with col1:
            qty = st.number_input(
                f"{it['item_id']} | ₹{it['sell_price']} | Stock: {it['quantity']}",
                min_value=0, max_value=int(it["quantity"]), step=1,
                key=it["item_id"]
            )

        if qty > 0:
            selected_items.append({
                "item_id": it["item_id"],
                "quantity": qty,
                "sell_price": it["sell_price"]
            })
            total_amount += qty * it["sell_price"]

    st.write(f"**Total Amount: ₹{total_amount}** (GST Removed)")

    if st.button("Generate Bill"):
        if not buyer_name or not is_valid_mobile(buyer_mobile):
            st.error("Fill all details correctly!")
        elif not selected_items:
            st.error("Select at least one item")
        else:
            bill_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

            bill_data = {
                "bill_id": bill_id,
                "buyer_name": buyer_name,
                "buyer_mobile": buyer_mobile,
                "items": selected_items,
                "total_amount": total_amount,
                "date": datetime.now().strftime("%d-%m-%Y %H:%M")
            }

            bills_col.insert_one(bill_data)

            # Deduct stock
            for it in selected_items:
                items_col.update_one({"item_id": it["item_id"]}, {"$inc": {"quantity": -it["quantity"]}})

            pdf = generate_bill_pdf(bill_data, selected_items)

            st.success("Bill generated successfully!")
            st.download_button("Download Bill PDF", data=pdf, file_name=f"Bill_{bill_id}.pdf")

# ===============================
#  SHOW BILLS + FILTERS
# ===============================
elif menu == "Show Bills":
    st.header("All Transactions / Bills")

    # Filters
    st.subheader("🔍 Search & Filters")
    name_filter = st.text_input("Search by Buyer Name")
    mobile_filter = st.text_input("Search by Mobile")
    date_from = st.date_input("From Date", value=None)
    date_to = st.date_input("To Date", value=None)

    query = {}

    if name_filter:
        query["buyer_name"] = {"$regex": name_filter, "$options": "i"}

    if mobile_filter:
        query["buyer_mobile"] = {"$regex": mobile_filter}

    # Fetch bills
    bills = list(bills_col.find(query, {"_id": 0}))

    # Date filtering (Python-side)
    if date_from:
        bills = [b for b in bills if datetime.strptime(b["date"], "%d-%m-%Y %H:%M").date() >= date_from]
    if date_to:
        bills = [b for b in bills if datetime.strptime(b["date"], "%d-%m-%Y %H:%M").date() <= date_to]

    if not bills:
        st.info("No bills found.")
    else:
        for b in bills:
            st.write(f"### Bill ID: {b['bill_id']}")
            st.write(f"Buyer: {b['buyer_name']}")
            st.write(f"Mobile: {b['buyer_mobile']}")
            st.write(f"Total Amount: ₹{b['total_amount']}")
            st.write(f"Date: {b['date']}")

            pdf = generate_bill_pdf(b, b["items"])
            st.download_button(
                f"Download Bill {b['bill_id']}",
                data=pdf,
                file_name=f"Bill_{b['bill_id']}.pdf"
            )
            st.divider()
