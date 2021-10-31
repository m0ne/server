import json
from flask import Flask, render_template, send_from_directory, request
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Substitution
from pymongo import MongoClient
import os

app = Flask(__name__)

formatted_orders = []

#webhook_stub = '{   "responseId": "8e48f59c-3360-48a5-a016-82cd0cb82f56-cad07fe1",   "queryResult": {     "queryText": "bahnhofsplatz 5",     "action": "order.drink.different_card.orderdrinkdelivery-custom",     "parameters": {       "address": "bahnhofsplatz 5"     },     "allRequiredParamsPresent": true,     "fulfillmentText": "Thanks. Delivery is to bahnhofsplatz 5. A confirmation mail with all the details will be sent to you.",     "fulfillmentMessages": [       {         "text": {           "text": [             "Thanks. Delivery is to bahnhofsplatz 5. A confirmation mail with all the details will be sent to you."           ]         }       }     ],     "outputContexts": [       {         "name": "projects/coffee-shop-iudl/agent/sessions/9b5fa3f0-e3dd-06f4-5e74-309f81d5b046/contexts/orderdrink-yes-followup",         "parameters": {           "number": "number",           "number.original": "",           "address": "bahnhofsplatz 5",           "address.original": "bahnhofsplatz 5"         }       },       {         "name": "projects/coffee-shop-iudl/agent/sessions/9b5fa3f0-e3dd-06f4-5e74-309f81d5b046/contexts/orderdrink-followup",         "parameters": {           "drink": "coffee",           "drink.original": "coffee",           "size": "small",           "size.original": "small",           "E-Mail": "michael.schneider@hispeed.ch",           "E-Mail.original": "michael.schneider@hispeed.ch",           "iced": "",           "iced.original": "",           "amount": "",           "amount.original": "",           "milk-type": "",           "milk-type.original": "",           "number": "number",           "number.original": "",           "address": "bahnhofsplatz 5",           "address.original": "bahnhofsplatz 5"         }       },       {         "name": "projects/coffee-shop-iudl/agent/sessions/9b5fa3f0-e3dd-06f4-5e74-309f81d5b046/contexts/orderdrinkdelivery-followup",         "lifespanCount": 1,         "parameters": {           "address": "bahnhofsplatz 5",           "address.original": "bahnhofsplatz 5"         }       },       {         "name": "projects/coffee-shop-iudl/agent/sessions/9b5fa3f0-e3dd-06f4-5e74-309f81d5b046/contexts/__system_counters__",         "parameters": {           "no-input": 0,           "no-match": 0,           "address": "bahnhofsplatz 5",           "address.original": "bahnhofsplatz 5"         }       }     ],     "intent": {       "name": "projects/coffee-shop-iudl/agent/intents/2948b710-1163-4310-afac-b9782e90c93b",       "displayName": "order.drink.delivery - address",       "endInteraction": true     },     "intentDetectionConfidence": 1,     "languageCode": "en",     "sentimentAnalysisResult": {       "queryTextSentiment": {         "score": 0.6,         "magnitude": 0.6       }     }   },   "originalDetectIntentRequest": {     "source": "DIALOGFLOW_CONSOLE",     "payload": {}   },   "session": "projects/coffee-shop-iudl/agent/sessions/9b5fa3f0-e3dd-06f4-5e74-309f81d5b046" }'


def order_as_string(order):
    output = ""
    for k, v in order.items():
        if v:
            output += k + ': ' + v + "\n"
    return output


def create_confirmation_message(order):
    e_mail = str(order['E-Mail'])
    order_formatted = order_as_string(order)
    message = Mail(
        from_email="michael.schneider@hispeed.ch",
        to_emails=e_mail,
        subject="Bestellbestätigung: RAPPOS Webshop",
        plain_text_content="Wir danken Ihnen herzlich für Ihre Bestellung: \n\n" + order_formatted + "\nFreundliche Grüsse\nIhr RAPPOS Team")
    return message


def load_sendgrid_key():
    try:
        with open('config.json') as f:
            config = json.load(f)
        if (config['deployed_at'] == "local"):
            sendgrid_key = config['sendgrid_key']
        else:
            sendgrid_key = os.environ.get('sendgrid_key')
        return sendgrid_key
    except Exception as e:
        print(e.message)


def send_confirmation(message):
    sendgrid_key = load_sendgrid_key()
    sg = SendGridAPIClient(sendgrid_key)
    response = sg.send(message)


def format_order(order):
    return order


def check_availability(client, item_name, quantity):
    db = client["store"]
    col = db["items"]

    status = ""
    for x in col.find({}, {"_id": 0}):
        if x['name'] == item_name:
            if x['quantity'] >= int(quantity):
                store_quantity = int(x['quantity'])
                updated_quantity = {
                    "$set": {"quantity": store_quantity-int(quantity)}}
                col.update_one(x, updated_quantity)
                print("sold", item_name)
                status = "item available"
                break
            else:
                status = "item sold out"
                break
    return status


def store(item, quantity):
    with open('config.json') as f:
        config = json.load(f)

    connection_string = config['mongo_db_connection_string']
    client = MongoClient(connection_string)

    item_name = str(item)

    availability = check_availability(client, item_name, quantity)

    if availability == "item available":
        return True
    else:
        return False


def process_order(order):
    order_parameters = order['queryResult']['outputContexts'][2]['parameters']
    order_parameters_clean = {}
    for param, param_key in order_parameters.items():
        if ('original' not in param):
            order_parameters_clean[param] = param_key

    item = order_parameters_clean['drink']
    if order_parameters_clean['amount'] == '':
        quantity = 1
    else:
        quantity = int(order_parameters_clean['amount'])

    if (store(item, quantity)):
        return order_parameters_clean
    else:
        {}


def format_dialogflow(order_parameters):
    dialogflow_response = {
        "fulfillmentMessages": [
            {
                "text": {
                    "text": []
                }
            }
        ]
    }

    text_message = dialogflow_response['fulfillmentMessages'][0]['text']['text']
    text_message.append(
        "Your order has been confirmed by the server, thank you very much")

    if "address" in order_parameters.keys():
        text_message.append("Delivery is to " + order_parameters['address'] + ". A confirmation mail will be sent to you.")
    else:
        text_message.append("You can pickup your order at " + order_parameters['restaurantlocations'] + ". A confirmation mail will be sent to you.")
    text_message.append(order_as_string(
        order_parameters))

    return dialogflow_response


def initialize_order(order):
    webhook_response = {
        "fulfillmentMessages": [
            {
                "text": {
                    "text": ["Unfortunately the item has been sold out, please order a different one"]
                }
            }
        ]
    }

    formatted_order = format_order(order)
    processed_order = process_order(formatted_order)

    if (processed_order):
        webhook_response = format_dialogflow(processed_order)
        formatted_orders.append(processed_order)
        send_confirmation(create_confirmation_message(processed_order))

    return webhook_response


@ app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico', mimetype='image/favicon.png')


@ app.route('/dialogflow', methods=['POST'])
def webhook():
    req = request.get_json(force=True)
    order = req
    webhook_response = initialize_order(order)

    return webhook_response


# @ app.route('/debug')
# def debug():
#     order = json.loads(webhook_stub)
#    webhook_response = initialize_order(order)

#    return webhook_response


@ app.route('/')
def index():
    user_message = "RAPPOS Dashboard"
    nr_orders = len(formatted_orders)

    return render_template("index.html", message=user_message, count=nr_orders, orders=formatted_orders)


if __name__ == "__main__":
    app.run()
