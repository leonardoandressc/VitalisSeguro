# 📋 Complete Stripe Testing Guide

This guide covers the complete process of setting up and testing Stripe payments for appointment bookings through WhatsApp.

## Prerequisites
- **Stripe Test Mode**: Using sandbox/test keys ✅
- **Test WhatsApp Number**: Connected to an account
- **AdminHub Access**: To configure the account

---

## Step 1: Create & Configure Stripe Connect Account

### 1.1 Enable Stripe in AdminHub
1. Go to AdminHub (https://your-admin-hub-url/admin)
2. Select your test account (e.g., "Vitalis Stream Test")
3. Click Edit → Stripe Settings tab
4. You'll see: 🔴 "Stripe Account Not Connected"
5. Click "Connect Stripe Account" button

### 1.2 Complete Stripe Connect Onboarding (Test Mode)
When the Stripe onboarding window opens:

**BUSINESS INFORMATION:**
- Business type: Individual
- Country: Mexico
- First name: Test
- Last name: Doctor
- Email: test@example.com
- Date of birth: 01/01/1990

**BUSINESS DETAILS:**
- Industry: Healthcare
- Website: https://example.com (or skip)
- Product description: "Medical consultation services"

**BANK ACCOUNT (Test):**
- Use Stripe's test bank account:
  - Routing number: 110000000
  - Account number: 000123456789
- Or for Mexico:
  - CLABE: 000000000000000018

**IDENTITY VERIFICATION:**
- Phone: +52 55 1234 5678
- Address: Any valid address
- ID verification: Skip in test mode

**PAYOUT SCHEDULE:**
- Daily, Weekly, or Monthly (your choice)

Click "Submit" to complete onboarding

### 1.3 Verify Connect Status
1. Return to AdminHub
2. Refresh the page (or wait 5 seconds for auto-refresh)
3. Edit the account again
4. Stripe Settings should now show:
   - 🟢 "Stripe Account Connected"
   - Account ID: acct_xxxxxxxxxxxxx
   - Charges: ✅ Enabled | Payouts: ✅ Enabled

### 1.4 Configure Pricing
1. Set Appointment Price: 500.00 (MXN)
2. Currency: MXN
3. Payment Description: "Consulta médica"
4. Save Changes

---

## Step 2: Test Payment Flow in WhatsApp

### 2.1 Start Appointment Booking
Send these messages to your WhatsApp bot:

```
You: Hola, quiero agendar una cita
Bot: ¡Hola! Claro, con gusto te ayudo a agendar tu cita...

You: Mi nombre es Juan Pérez
Bot: Perfecto Juan...

You: Necesito consulta para dolor de cabeza
Bot: Entiendo, una consulta para dolor de cabeza...

You: Prefiero mañana a las 10 de la mañana
Bot: [Shows confirmation with appointment details]
```

### 2.2 Confirm Appointment
Click: **✅ Sí, confirmar**

Expected response:
```
📋 ¡Perfecto! He registrado tu cita.

💳 Para confirmarla, necesitas realizar el pago de $500.00 MXN.

🔗 Por favor realiza el pago aquí:
https://checkout.stripe.com/c/pay/cs_test_xxxxx

⏱️ Este enlace expirará en 30 minutos.
Una vez confirmado el pago, tu cita quedará agendada.
```

### 2.3 Complete Test Payment
1. Click the Stripe payment link
2. Use test card details:
   - Card number: `4242 4242 4242 4242`
   - Expiry: `12/34` (any future date)
   - CVC: `123`
   - Name: Juan Pérez
   - Email: juan@example.com
   - Phone: +52 33 1234 5678

3. Click "Pay $500.00 MXN"
4. You'll see "Payment successful" page

### 2.4 Verify Payment Webhook
The webhook should:
1. Update payment status to "completed"
2. Create appointment in GoHighLevel
3. Send WhatsApp confirmation:
   ```
   ✅ ¡Tu pago ha sido confirmado! 
   Tu cita está agendada para [fecha y hora]
   ```

---

## Step 3: Verify Results

### 3.1 Check Firestore
Look for these collections:

**conversations/{conversation_id}:**
```json
{
  "context": {
    "appointment_info": {
      "payment_id": "pi_xxx",
      "payment_status": "completed"
    }
  }
}
```

**payments/{payment_id}:**
```json
{
  "status": "completed",
  "amount": 50000,
  "stripe_payment_intent_id": "pi_xxx"
}
```

### 3.2 Check Stripe Dashboard (Test Mode)
1. Go to https://dashboard.stripe.com/test/payments
2. You should see:
   - Payment of $500.00 MXN
   - Status: Succeeded
   - Connected account: acct_xxx

3. Check Connect account:
   - Go to Connect → Accounts
   - Find your test account
   - Should show the payment received

### 3.3 Check GoHighLevel
1. Go to GHL → Calendar
2. Find the appointment for tomorrow 10 AM
3. Contact: Juan Pérez
4. Status: Confirmed

---

## Step 4: Test Edge Cases

### 4.1 No Connect Account
1. Disable and re-enable Stripe (without Connect)
2. Try to book appointment
3. Should see: "❌ La cuenta de pagos no está configurada"

### 4.2 Payment Cancellation
1. Get payment link
2. Open but click "Back" or close
3. Try booking again
4. Should get new payment link

### 4.3 Expired Payment Link
1. Get payment link
2. Wait 30+ minutes
3. Try to pay
4. Should show "Session expired"

---

## Troubleshooting

### If onboarding doesn't complete:
```bash
# Check account status via API
curl -X GET https://vitalis-chatbot-1-0.onrender.com/api/stripe/connect/status \
  -H "X-API-Key: your-api-key"
```

### If payment webhook fails:
```bash
# Use Stripe CLI to test webhook locally
stripe listen --forward-to localhost:5000/api/stripe/webhooks
stripe trigger checkout.session.completed
```

### Common Issues:
1. **"Stripe account not connected"** → Complete onboarding first
2. **Payment link not working** → Check if account has charges_enabled
3. **Webhook not received** → Verify STRIPE_WEBHOOK_SECRET matches
4. **Payment not creating appointment** → Check webhook logs in Render dashboard

---

## Test Card Numbers

### Successful Payment Cards:
- `4242 4242 4242 4242` - Visa (Most common)
- `5555 5555 5555 4444` - Mastercard
- `3782 822463 10005` - American Express

### Cards for Testing Failures:
- `4000 0000 0000 0002` - Card declined
- `4000 0000 0000 9995` - Insufficient funds
- `4000 0000 0000 0069` - Expired card

### 3D Secure Test Cards:
- `4000 0027 6000 3184` - Authentication required
- `4000 0027 6000 0016` - Authentication supported but not required

---

## Success Checklist

- [ ] Stripe Connect account created
- [ ] Onboarding completed (test mode)
- [ ] Charges & Payouts enabled
- [ ] Price configured in AdminHub
- [ ] Payment link generated in WhatsApp
- [ ] Test payment completed
- [ ] Webhook received and processed
- [ ] Appointment created in GHL
- [ ] Confirmation sent via WhatsApp

---

## Important Notes

1. **Test Mode**: All testing should be done with Stripe test keys (sk_test_...)
2. **Real Cards**: Never use real credit cards in test mode
3. **Webhook Secret**: Ensure STRIPE_WEBHOOK_SECRET in .env matches Stripe dashboard
4. **Connect Account**: Each business needs their own Connect account for payouts
5. **Currency**: Currently configured for MXN, adjust as needed

---

## Switching to Live Mode

When you're ready to accept real payments:

### Environment Variables to Update:
1. **`STRIPE_SECRET_KEY`**: Change from `sk_test_...` to `sk_live_...`
2. **`STRIPE_WEBHOOK_SECRET`**: Create new webhook in live mode and use its signing secret

### Steps:
1. **Update Stripe Webhook**:
   - Go to Stripe Dashboard → Webhooks
   - Toggle to "Live mode" (top right)
   - Add endpoint: `https://vitalis-chatbot-1-0.onrender.com/api/stripe/webhooks`
   - Select events: `checkout.session.completed`
   - Copy signing secret for `STRIPE_WEBHOOK_SECRET`

2. **Complete Live Connect Onboarding**:
   - Each account must complete real onboarding
   - Real bank accounts and identity verification required
   - Creates live Connect account ID

3. **Update Environment Variables** (Render):
   ```
   STRIPE_SECRET_KEY=sk_live_YOUR_LIVE_KEY
   STRIPE_WEBHOOK_SECRET=whsec_YOUR_LIVE_WEBHOOK_SECRET
   ```

### Live Mode Differences:
- Real credit cards only (test cards won't work)
- Real money transactions
- Stripe fees apply (~2.9% + 30¢)
- Payouts to real bank accounts

---

## API Endpoints Reference

### Stripe Connect
- `POST /api/stripe/accounts/{account_id}/connect` - Create onboarding link
- `GET /api/stripe/connect/status` - Check Connect account status

### Payments
- `POST /api/stripe/checkout/create` - Create checkout session
- `POST /api/stripe/webhooks` - Stripe webhook handler

### Testing with cURL
```bash
# Create onboarding link
curl -X POST https://vitalis-chatbot-1-0.onrender.com/api/stripe/accounts/{account_id}/connect \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"return_url": "https://your-admin-hub/admin", "refresh_url": "https://your-admin-hub/admin"}'
```

Once all items are checked, your Stripe integration is fully working! 🎉