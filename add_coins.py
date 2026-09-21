#!/usr/bin/env python3
"""
Add coins to a user for testing purposes.
"""
import sys
from pymongo import MongoClient

if len(sys.argv) < 3:
    print("Usage: python3 add_coins.py <user_id> <coins>")
    sys.exit(1)

user_id = sys.argv[1]
coins = int(sys.argv[2])

client = MongoClient("mongodb://localhost:27017")
db = client["test_database"]

result = db.users.update_one(
    {"id": user_id},
    {"$inc": {"coins": coins}}
)

if result.matched_count > 0:
    print(f"✅ Added {coins} coins to user {user_id}")
    user = db.users.find_one({"id": user_id}, {"_id": 0, "coins": 1, "withdrawable": 1})
    print(f"  New balance: {user.get('coins', 0)} coins, {user.get('withdrawable', 0)} withdrawable")
else:
    print(f"❌ User {user_id} not found")
