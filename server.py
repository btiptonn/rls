# ============================================================
#  RESIDENTIAL LAUNDRY SYSTEM — BACKEND
# ============================================================

from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import urllib.request
import urllib.parse

PHONE_NUMBER = "+12569246101"
TEXTBELT_KEY = "797d161d1c256b18b56a937777d3011de59b4c0eiaUVHwbOvxFgv01X2jDWEyWye"

PORT = 10000

def http_post(url, fields):
  data = urllib.parse.urlencode(fields).encode()
  req = urllib.request.Request(url, data=data)
  req.add_header("Content-Type", "application/x-www-form-urlencoded")
  with urllib.request.urlopen(req) as resp:
    return resp.read().decode()

def send_sms(message):
  print("📱 SEND SMS:", message)
  try:
    out = http_post("https://textbelt.com/text", {
      "phone": PHONE_NUMBER,
      "message": message,
      "key": TEXTBELT_KEY
    })
    print("📨 TEXTBELT:", out)
  except Exception as e:
    print("❌ SMS ERROR:", e)

state = {
  "rfid": "None",
  "state": "Idle",
  "
