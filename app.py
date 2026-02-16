from flask import Flask, render_template, request, jsonify, session
import json
import os
import time
import random
from html import escape

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this'

# --- Load Local Products JSON ---
DATA_FILE = os.path.join(os.path.dirname(__file__), 'products.json')

with open(DATA_FILE, 'r', encoding='utf-8') as f:
    json_data = json.load(f)

# Indian Rupee conversion rate (as of early 2026)
INR_RATE = 90.65

def format_inr(usd_amount):
    inr = usd_amount * INR_RATE
    return f"₹{inr:.2f}"

# --- Data Access Functions ---
def get_product_catalog():
    return json_data['products']

def get_categories():
    return json_data['categories']

# --- Chatbot Logic ---
def chatbot_response(user_input, session_data):
    user_input = escape(user_input.lower().strip())
    session_data = session_data or {"step": "start", "selected_product": None}
    
    # Initialize session variables
    session.setdefault('cart', [])
    session.setdefault('discount_rate', 0.0)
    session.setdefault('free_shipping', False)
    session.setdefault('orders', [])

    # 1. GLOBAL COMMANDS
    if user_input in ["hi", "hello", "hey", "start"]:
        cats = get_categories()
        cat_list = "\n".join([f"• {cat.replace('-', ' ').replace('womens', 'women\'s').replace('mens', 'men\'s').title()}" 
                              for cat in cats])
        session_data["step"] = "select_category"
        session_data["categories"] = cats
        return (f"Hi neeraj! Welcome to the store 🇮🇳\n\n"
                f"Available Categories:\n{cat_list}\n\n"
                f"Type a category name to browse (e.g., 'laptops' or 'laptop accessories')\n"
                f"Or type 'help' for all commands."), session_data

    if user_input == "help":
        return ("Available commands anytime:\n"
                "- hi: show categories\n"
                "- cart: view cart\n"
                "- checkout: proceed to payment\n"
                "- clear cart: empty cart\n"
                "- remove <num>: remove item from cart\n"
                "- update <num> <qty>: change quantity\n"
                "- apply SAVE10 / apply FREESHIP: discount codes\n"
                "- orders: view past orders\n"
                "- cancel order <num>: cancel a past order (e.g., cancel order 1)\n"
                "- search: keyword search\n"
                "- cancel: abort checkout"), session_data

    if user_input == "cart":
        cart = session['cart']
        if not cart:
            return "Your cart is empty.", session_data
        
        cart_lines = "\n".join([f"{i+1}. {item['title']} (x{item['quantity']}) - {format_inr(item['price'] * item['quantity'])}"
                                for i, item in enumerate(cart)])
        subtotal_usd = sum(item['price'] * item['quantity'] for item in cart)
        subtotal_inr = subtotal_usd * INR_RATE
        discount_amt = subtotal_inr * session['discount_rate']
        after_discount = subtotal_inr - discount_amt
        shipping = 0 if (session.get('free_shipping') or after_discount >= 2000) else 99.00
        
        return (f"🛒 Your Cart:\n{cart_lines}\n\n"
                f"Subtotal: {format_inr(subtotal_usd)}\n"
                f"Discount: {int(session['discount_rate']*100)}% → -₹{discount_amt:.2f}\n"
                f"After discount: ₹{after_discount:.2f}\n"
                f"Shipping: ₹{shipping:.2f} {'(FREE! 🚚)' if shipping == 0 else ''}\n\n"
                f"Type 'checkout' to buy or continue shopping."), session_data

    if user_input == "clear cart":
        session['cart'] = []
        session.modified = True
        return "Cart cleared! Type 'hi' to shop again.", session_data

    if user_input == "orders":
        orders = session.get('orders', [])
        if not orders:
            return "You have no past orders.", session_data
        
        order_list = []
        for i, o in enumerate(orders):
            # Use .get() with a fallback of 0 to prevent KeyError
            total = o.get('totals', {}).get('grand_usd', 0)
            order_list.append(f"{i+1}. Order {o['id']} ({o['date']}) → {format_inr(total)}")
        
        return (f"Your Orders:\n" + "\n".join(order_list) + "\n\n"
                f"To cancel an order, type 'cancel order <number>'"), session_data

    # Improved cancel order handling
    if user_input.startswith("cancel order"):
        parts = user_input.split()
        if len(parts) < 3:
            return ("Please specify the order number.\n"
                    "Type 'orders' to see the list, then 'cancel order 1' (replace 1 with the number)."), session_data
        try:
            num = int(parts[2]) - 1
            if 0 <= num < len(session['orders']):
                cancelled = session['orders'].pop(num)
                session.modified = True
                return f"Order {cancelled['id']} has been cancelled and removed.", session_data
            return "Invalid order number.", session_data
        except ValueError:
            return "Please use a valid number (e.g., 'cancel order 1').", session_data

    if user_input.startswith("remove "):
        try:
            num = int(user_input.split()[1]) - 1
            if 0 <= num < len(session['cart']):
                removed = session['cart'].pop(num)
                session.modified = True
                return f"Removed {removed['title']} from cart.", session_data
            return "Invalid item number.", session_data
        except:
            return "Usage: remove <number>", session_data

    if user_input.startswith(("update ", "change ")):
        try:
            parts = user_input.split()
            num = int(parts[1]) - 1
            qty = int(parts[2])
            if qty <= 0:
                return "Quantity must be > 0.", session_data
            if 0 <= num < len(session['cart']):
                session['cart'][num]['quantity'] = qty
                session.modified = True
                return f"Updated to {qty} unit(s).", session_data
            return "Invalid item number.", session_data
        except:
            return "Usage: update <number> <new quantity>", session_data

    if user_input.startswith("apply "):
        code = " ".join(user_input.split()[1:]).upper()
        if code == "SAVE10":
            session['discount_rate'] = 0.10
            session.modified = True
            return "✅ 10% discount applied! (SAVE10)", session_data
        elif code == "FREESHIP":
            session['free_shipping'] = True
            session.modified = True
            return "✅ Free shipping applied! (FREESHIP)", session_data
        else:
            return "Invalid code. Try SAVE10 or FREESHIP.", session_data

    if user_input == "cancel":
        if session_data["step"].startswith("checkout_"):
            session_data["step"] = "start"
            return "Checkout cancelled.", session_data
        return "Nothing to cancel.", session_data

    if user_input == "search":
        session_data["step"] = "search_product"
        return "What are you looking for? Type a keyword:", session_data

    if user_input == "checkout":
        cart = session['cart']
        if not cart:
            return "Your cart is empty!", session_data
        
        subtotal_usd = sum(item['price'] * item['quantity'] for item in cart)
        subtotal_inr = subtotal_usd * INR_RATE
        discount_amt = subtotal_inr * session['discount_rate']
        after_discount = subtotal_inr - discount_amt
        shipping = 0 if (session.get('free_shipping') or after_discount >= 2000) else 99.00
        tax = (after_discount + shipping) * 0.18  # 18% GST
        grand_total_inr = after_discount + shipping + tax

        item_lines = "\n".join([f"• {item['title']} (x{item['quantity']}) - {format_inr(item['price'] * item['quantity'])}"
                                for item in cart])

        summary = (f"--- CHECKOUT SUMMARY ---\n{item_lines}\n\n"
                   f"Subtotal: {format_inr(subtotal_usd)}\n"
                   f"Discount: -₹{discount_amt:.2f}\n"
                   f"Shipping: ₹{shipping:.2f} {'(FREE! 🚚)' if shipping == 0 else ''}\n"
                   f"GST (18%): ₹{tax:.2f}\n"
                   f"Grand Total: ₹{grand_total_inr:.2f}\n\n"
                   f"Please enter your full name:")

        session_data.update({"step": "checkout_name", "checkout_temp": {
            "subtotal_usd": subtotal_usd,
            "discount_amt": discount_amt,
            "shipping": shipping,
            "tax": tax,
            "grand_total_inr": grand_total_inr}})
        return summary, session_data

    # 2. STEP-SPECIFIC LOGIC
    if session_data["step"] == "select_category":
        normalized = user_input.replace(" ", "-").lower()
        if normalized in [c.lower() for c in session_data.get("categories", [])]:
            cat_products = [p for p in get_product_catalog() if p['category'].lower() == normalized]
            if not cat_products:
                return "No products in this category yet.", session_data
            product_list = "\n".join([f"{i+1}. {p['title']} - {format_inr(p['price'])}"
                                      for i, p in enumerate(cat_products)])
            session_data.update({"step": "select_product", "catalog": cat_products})
            return f"Products in {user_input.title()}:\n{product_list}\n\nType a number for details:", session_data
        return "Category not found. Type 'hi' to see available categories.", session_data

    if session_data["step"] == "select_product":
        if user_input.isdigit():
            idx = int(user_input) - 1
            catalog = session_data.get("catalog", [])
            if 0 <= idx < len(catalog):
                product = catalog[idx]
                session_data.update({"selected_product": product, "step": "confirm_purchase"})
                return (f"📱 {product['title']}\n"
                        f"Brand: {product.get('brand', 'N/A')}\n"
                        f"Price: {format_inr(product['price'])}\n"
                        f"Rating: {product['rating']['rate']}/5 ({product['rating']['count']} reviews)\n"
                        f"{product['description']}\n"
                        f"Image: {product['image']}\n\n"
                        f"Type 'buy' to add to cart or 'back' to category."), session_data
        return "Please type a valid number.", session_data

    if session_data["step"] == "confirm_purchase":
        if user_input == "buy":
            session_data["step"] = "quantity"
            return f"How many {session_data['selected_product']['title']} do you want?", session_data
        elif user_input == "back":
            return chatbot_response("hi", session_data)

    if session_data["step"] == "quantity":
        if user_input.isdigit() and int(user_input) > 0:
            qty = int(user_input)
            product = session_data["selected_product"]
            session['cart'].append({**product, "quantity": qty})
            session.modified = True
            session_data["step"] = "start"
            return (f"Added {qty} × {product['title']} to cart! 🛒\n"
                    f"Type 'cart' to review or 'checkout' to buy."), session_data
        return "Please enter a valid quantity.", session_data

    if session_data["step"] == "search_product":
        keyword = user_input
        matches = [p for p in get_product_catalog() if keyword in p['title'].lower() or keyword in p.get('brand', '').lower()]
        if not matches:
            session_data["step"] = "start"
            return "No matches found. Type 'hi' to browse.", session_data
        product_list = "\n".join([f"{i+1}. {p['title']} - {format_inr(p['price'])}"
                                  for i, p in enumerate(matches)])
        session_data.update({"step": "select_product", "catalog": matches})
        return f"Search results for '{keyword}':\n{product_list}\nType a number:", session_data

    # Checkout flow
    if session_data["step"] == "checkout_name":
        session['customer_name'] = user_input.strip()
        session_data["step"] = "checkout_address"
        return "Great! Now enter your full shipping address (street, city, state, PIN):", session_data

    if session_data["step"] == "checkout_address":
        session['customer_address'] = user_input.strip()
        
        temp = session_data["checkout_temp"]
        order_id = f"ORD{random.randint(10000, 99999)}"
        cart = session['cart']
        item_lines = "\n".join([f"• {item['title']} (x{item['quantity']}) - {format_inr(item['price'] * item['quantity'])}"
                                for item in cart])

        final_msg = (f"🎉 ORDER CONFIRMED!\n"
                     f"Order ID: {order_id}\n"
                     f"Name: {session['customer_name']}\n"
                     f"Delivery: {session['customer_address']}\n\n"
                     f"{item_lines}\n\n"
                     f"Subtotal: {format_inr(temp['subtotal_usd'])}\n"
                     f"Discount: -₹{temp['discount_amt']:.2f}\n"
                     f"Shipping: ₹{temp['shipping']:.2f}\n"
                     f"GST: ₹{temp['tax']:.2f}\n"
                     f"Total Paid: ₹{temp['grand_total_inr']:.2f}\n\n"
                     f"Thank you neeraj! Your order will arrive in 3-5 days 🚚")

        # Save order with grand total in USD for consistency
        order = {
            "id": order_id,
            "date": time.strftime("%b %d, %Y"),
            "items": cart.copy(),
            "totals": {"grand_usd": temp['subtotal_usd'] + temp['shipping']/INR_RATE + temp['tax']/INR_RATE},  # approximate
            "name": session['customer_name'],
            "address": session['customer_address']
        }
        session['orders'].append(order)
        
        # Reset
        session['cart'] = []
        session['discount_rate'] = 0.0
        session['free_shipping'] = False
        session.pop('customer_name', None)
        session.pop('customer_address', None)
        session.modified = True
        session_data["step"] = "start"
        
        return final_msg, session_data

    return "I didn't understand. Type 'help' for commands.", session_data

# --- Flask Routes ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    response, updated_session = chatbot_response(data.get('message'), data.get('session_data'))
    return jsonify({'response': response, 'session_data': updated_session})

if __name__ == '__main__':
    app.run(debug=True)