# Vitalis Platform Fee Structure

## Overview
Vitalis charges a **5% platform fee** with a **minimum of 10 MXN** per appointment to cover operational costs and Stripe processing fees.

## Fee Calculation
- **Platform fee**: 5% of appointment amount
- **Minimum fee**: 10 MXN
- **Formula**: `max(appointment_amount * 0.05, 10)`

## Stripe Processing Costs
Stripe charges us: **3.6% + 3 MXN** per successful transaction

Important: With Stripe Connect's `application_fee_amount`, these processing fees are deducted from our platform fee, not from the doctor's portion.

## Profit Margins by Appointment Amount

| Appointment Amount | Platform Fee (5%) | Stripe Fee | Net Profit | Profit Margin |
|-------------------|------------------|------------|------------|---------------|
| 50 MXN | 10 MXN (min) | 4.80 MXN | 5.20 MXN | 10.4% |
| 100 MXN | 10 MXN (min) | 6.60 MXN | 3.40 MXN | 3.4% |
| 200 MXN | 10 MXN (min) | 10.20 MXN | -0.20 MXN | -0.1% |
| 250 MXN | 12.50 MXN | 12.00 MXN | 0.50 MXN | 0.2% |
| 300 MXN | 15 MXN | 13.80 MXN | 1.20 MXN | 0.4% |
| 500 MXN | 25 MXN | 21.00 MXN | 4.00 MXN | 0.8% |
| 1,000 MXN | 50 MXN | 39.00 MXN | 11.00 MXN | 1.1% |
| 2,000 MXN | 100 MXN | 75.00 MXN | 25.00 MXN | 1.25% |
| 5,000 MXN | 250 MXN | 183.00 MXN | 67.00 MXN | 1.34% |

## Key Insights

### Break-even Point
- We break even at approximately **206 MXN** appointments
- Below this amount, the minimum fee ensures profitability
- Above this amount, the 5% fee provides increasing margins

### Small Appointments (< 200 MXN)
- The 10 MXN minimum fee provides good margins
- Most profitable in percentage terms due to the minimum

### Medium Appointments (200-500 MXN)
- Margins are tight but positive
- Volume in this range is important for overall profitability

### Large Appointments (> 1,000 MXN)
- Consistent ~1.3% net margin after Stripe fees
- Higher absolute profit amounts

## Doctor's Perspective
Doctors receive their portion cleanly without worrying about:
- Stripe processing fees
- Platform infrastructure costs
- Payment processing complexity

## Example Scenarios

### Scenario 1: General Consultation (300 MXN)
- Patient pays: 300 MXN
- Vitalis fee: 15 MXN (5%)
- Stripe costs: 13.80 MXN
- Vitalis keeps: 1.20 MXN
- Doctor receives: 285 MXN

### Scenario 2: Specialist Consultation (1,000 MXN)
- Patient pays: 1,000 MXN
- Vitalis fee: 50 MXN (5%)
- Stripe costs: 39 MXN
- Vitalis keeps: 11 MXN
- Doctor receives: 950 MXN

### Scenario 3: Quick Follow-up (100 MXN)
- Patient pays: 100 MXN
- Vitalis fee: 10 MXN (minimum)
- Stripe costs: 6.60 MXN
- Vitalis keeps: 3.40 MXN
- Doctor receives: 90 MXN

## Future Considerations
1. Monitor appointment price distribution to ensure fee structure remains profitable
2. Consider tiered pricing for high-volume doctors
3. Potential bulk payment options to reduce per-transaction costs
4. Regular review as Stripe fees or business costs change