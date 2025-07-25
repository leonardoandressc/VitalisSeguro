# Firestore Composite Indexes Required

The following composite indexes need to be created in the Firebase Console for the analytics queries to work properly:

## 1. Payments Collection
**Fields:**
- `account_id` (Ascending)
- `created_at` (Ascending)
- `__name__` (Ascending)

**Create Index URL:**
```
https://console.firebase.google.com/v1/r/project/vitalis-chatbot/firestore/indexes?create_composite=ClBwcm9qZWN0cy92aXRhbGlzLWNoYXRib3QvZGF0YWJhc2VzLyhkZWZhdWx0KS9jb2xsZWN0aW9uR3JvdXBzL3BheW1lbnRzL2luZGV4ZXMvXxABGg4KCmFjY291bnRfaWQQARoOCgpjcmVhdGVkX2F0EAEaDAoIX19uYW1lX18QAQ
```

## 2. Bookings Collection
**Fields:**
- `doctor_id` (Ascending)
- `created_at` (Ascending)
- `__name__` (Ascending)

**Create Index URL:**
```
https://console.firebase.google.com/v1/r/project/vitalis-chatbot/firestore/indexes?create_composite=ClBwcm9qZWN0cy92aXRhbGlzLWNoYXRib3QvZGF0YWJhc2VzLyhkZWZhdWx0KS9jb2xsZWN0aW9uR3JvdXBzL2Jvb2tpbmdzL2luZGV4ZXMvXxABGg0KCWRvY3Rvcl9pZBABGg4KCmNyZWF0ZWRfYXQQARoMCghfX25hbWVfXxAB
```

## 3. Appointment Reminders Collection
**Fields:**
- `account_id` (Ascending)
- `sent_at` (Ascending)
- `__name__` (Ascending)

**Create Index URL:**
```
https://console.firebase.google.com/v1/r/project/vitalis-chatbot/firestore/indexes?create_composite=Cl1wcm9qZWN0cy92aXRhbGlzLWNoYXRib3QvZGF0YWJhc2VzLyhkZWZhdWx0KS9jb2xsZWN0aW9uR3JvdXBzL2FwcG9pbnRtZW50X3JlbWluZGVycy9pbmRleGVzL18QARoOCgphY2NvdW50X2lkEAEaCwoHc2VudF9hdBABGgwKCF9fbmFtZV9fEAE
```

## 4. Conversations Collection (if needed)
**Fields:**
- `account_id` (Ascending)
- `created_at` (Ascending)
- `__name__` (Ascending)

## How to Create Indexes

1. Click on each URL above or copy and paste into your browser
2. You'll be redirected to the Firebase Console
3. Review the index configuration
4. Click "Create Index"
5. Wait for the index to be built (can take a few minutes)

## Why These Indexes Are Needed

Firestore requires composite indexes when you query with:
- Multiple field filters (e.g., account_id AND created_at)
- A combination of equality and range filters
- Ordering by a field different from the filter field

These indexes optimize query performance and are required for the analytics dashboard to function properly.