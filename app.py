import streamlit as st
import pandas as pd
import os
import random
import string
import json
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

ITEMS_FILE = "items.csv"
BILLS_FILE = "bills.csv"

# Load data
def load_items():
    return pd.read_csv(ITEMS_FILE) if os.path.exists(ITEMS_FILE) else pd.DataFrame(columns=["Item ID","Category","Subcategory","Cost Price","Sell Price","Quantity"])

def load_bills():
    return pd.read_csv(BILLS_FILE) if os.path.exists(BILLS_FILE) else pd.DataFrame(columns=["bill_id","buyer_name","buyer_mobile","amount","gst","discount","total_amount","net_amount"])

def save_items(df):
    df.to_csv(ITEMS_FILE, index=False)

def save_bills(df):
    df.to_csv(BILLS_FILE, index=False)

def generate_bill_pdf(bill_data, items_data):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    c.setFont("Helvetica-Bold", 18)
    c.drawString(250, 750, "ADS Group")
    c.setFont("Helvetica", 12)
    c.drawString(50, 730, f"Bill ID: {bill_data['bill_id']}")
    c.drawString(50, 715, f"Buyer: {bill_data['buyer_name']} ")
    c.drawString(50, 700, f"Contact: {bill_data['buyer_mobile']}")

    y = 690
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, y, "Item")
    c.drawString(250, y, "Qty")
    c.drawString(300, y, "Price")
    c.drawString(400, y, "Total")
    y -= 20

    c.setFont("Helvetica", 10)
    for _, row in items_data.iterrows():
        c.drawString(50, y, row["Item ID"])
        c.drawString(250, y, str(row["Quantity"]))
        c.drawString(300, y, str(row["Sell Price"]))
        c.drawString(400, y, str(row["Quantity"] * row["Sell Price"]))
        y -= 20

    y -= 20
    c.drawString(50, y, f"Amount: {bill_data['amount']}")
    y -= 15
    c.drawString(50, y, f"GST: {bill_data['gst']}")
    y -= 15
    c.drawString(50, y, f"Discount: {bill_data['discount']}")
    y -= 15
    c.drawString(50, y, f"Total Amount: {bill_data['total_amount']}")
    y -= 15
    c.drawString(50, y, f"Net Amount: {bill_data['net_amount']}")

    # Footer
    c.setFont("Helvetica-Oblique", 9)
    c.drawString(200, 50, "Thank You. Visit us again")
    c.drawString(150, 40, "Address: Chatauni Road, NH-28A Near J. J. Kanak Hospital, Motihari, 845401")
    c.drawString(200,30,'ads.company.group@gmail.com  |  7079704030')

    c.save()
    buffer.seek(0)
    return buffer

# Streamlit UI
st.sidebar.title("Admin Panel")
menu = st.sidebar.radio("Navigation", ["Add Item", "Show Items", "Generate Bill", "Show Bills"])

# ADD ITEM
if menu == "Add Item":
    st.header("Add New Item")
    items = load_items()

    categories = items["Category"].unique().tolist()
    subcategories = items["Subcategory"].unique().tolist()

    col1, col2 = st.columns(2)
    with col1:
        item_id = st.text_input("Item ID")
        category = st.selectbox("Category", options=["Add New"] + categories)
        if category == "Add New":
            category = st.text_input("New Category")

    with col2:
        subcategory = st.selectbox("Subcategory", options=["Add New"] + subcategories)
        if subcategory == "Add New":
            subcategory = st.text_input("New Subcategory")

    cost_price = st.number_input("Cost Price", min_value=0, step=1)
    sell_price = st.number_input("Sell Price", min_value=0, step=1)
    quantity = st.number_input("Quantity", min_value=0, step=1)

    if st.button("Save Item"):
        if item_id in items["Item ID"].values:
            st.warning("Duplicate Item ID! Please use a unique one.")
        else:
            new_item = pd.DataFrame([[item_id, category, subcategory, cost_price, sell_price, quantity]],
                                    columns=items.columns)
            items = pd.concat([items, new_item], ignore_index=True)
            save_items(items)
            st.success("Item Added Successfully!")

# SHOW ITEMS
elif menu == "Show Items":
    st.header("Available Items")
    items = load_items()
    st.dataframe(items)

# GENERATE BILL
elif menu == "Generate Bill":
    st.header("Generate Bill")
    items = load_items()
    bills = load_bills()

    buyer_name = st.text_input("Buyer Name")
    buyer_mobile = st.text_input("Buyer Mobile")

    st.subheader("Select Items")
    selected_items = []
    total_amount = 0

    for idx, row in items.iterrows():
        col1, col2 = st.columns([3,1])
        with col1:
            qty = st.number_input(f"{row['Item ID']} ({row['Sell Price']})", min_value=0, max_value=int(row['Quantity']), step=1, key=row['Item ID'])
        with col2:
            if qty > 0:
                selected_items.append((row, qty))
                total_amount += row['Sell Price'] * qty

    gst = total_amount * 0.18
    discount = st.number_input("Discount", min_value=0, step=1)
    net_amount = total_amount + gst - discount

    st.write(f"Amount: {total_amount}")
    st.write(f"GST (18%): {gst}")
    st.write(f"Net Amount: {net_amount}")

    if st.button("Generate Bill"):
        if not buyer_name or not buyer_mobile or not selected_items:
            st.error("Please fill all details and select at least one item.")
        else:
            bill_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            new_bill = pd.DataFrame([[bill_id, buyer_name, buyer_mobile, total_amount, gst, discount, total_amount+gst, net_amount]],
                                    columns=bills.columns)
            bills = pd.concat([bills, new_bill], ignore_index=True)
            save_bills(bills)

            # Update inventory
            for row, qty in selected_items:
                items.loc[items["Item ID"] == row["Item ID"], "Quantity"] -= qty
            save_items(items)

            # Generate PDF
            selected_df = pd.DataFrame([{
                "Item ID": row["Item ID"],
                "Quantity": qty,
                "Sell Price": row["Sell Price"]
            } for row, qty in selected_items])

            pdf_buffer = generate_bill_pdf(new_bill.iloc[0], selected_df)

            st.download_button("Download Bill PDF", data=pdf_buffer, file_name=f"Bill_{bill_id}.pdf", mime="application/pdf")

# SHOW BILLS
elif menu == "Show Bills":
    st.header("All Bills")
    bills = load_bills()

    if bills.empty:
        st.info("No bills available.")
    else:
        for idx, row in bills.iterrows():
            st.write(row.to_dict())

            if "items" in row and pd.notna(row["items"]):
                bill_items = pd.DataFrame(json.loads(row["items"]))
            else:
                bill_items = pd.DataFrame(columns=["item_id", "quantity", "sell_price"])
            pdf_buffer = generate_bill_pdf(row, bill_items)
            # st.download_button(
            #     f"Download Bill {row['bill_id']}",
            #     data=pdf_buffer,
            #     file_name=f"Bill_{row['bill_id']}.pdf",
            #     mime="application/pdf"
            # )