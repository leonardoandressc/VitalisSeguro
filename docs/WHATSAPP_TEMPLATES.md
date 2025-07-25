# WhatsApp Business Message Templates Setup

This document explains how to set up WhatsApp Business message templates for appointment notifications.

## Why Templates?

WhatsApp has a 24-hour messaging window policy. You can only send regular messages to users who have messaged you in the last 24 hours. After this window, you must use pre-approved message templates.

## Required Templates

### 1. Appointment Confirmation Template

**Template Name:** `appointment_confirmation`

**Language:** Spanish (Mexico) - `es_MX`

**Template Content:**
```
Hola {{1}}, tu cita ha sido confirmada.

📅 Fecha: {{2}}
🕐 Hora: {{3}}
👨‍⚕️ Doctor: {{4}}
📍 Ubicación: {{5}}

Por favor llega 10 minutos antes. Si necesitas cancelar, hazlo con 24 horas de anticipación.

¿Tienes alguna pregunta? Responde a este mensaje.
```

**Parameters:**
1. {{1}} - Patient name
2. {{2}} - Appointment date (e.g., "miércoles, 23 de julio de 2025")
3. {{3}} - Appointment time (e.g., "11:00 a.m.")
4. {{4}} - Doctor name
5. {{5}} - Office location/address

### 2. Appointment Reminder Template

**Template Name:** `appointment_reminder`

**Language:** Spanish (Mexico) - `es_MX`

**Template Content:**
```
Hola {{1}}, este es un recordatorio de tu cita para hoy a las {{2}}.

{{3}}

Por favor confirma tu asistencia:
```

**Buttons (Quick Reply):**
- ✅ Confirmar
- 📅 Reprogramar
- ❌ Cancelar

**Parameters:**
1. {{1}} - Patient name
2. {{2}} - Appointment time (e.g., "3:00 p.m.")
3. {{3}} - Service/Calendar name (optional)

## How to Create Templates

1. **Access WhatsApp Business Manager**
   - Go to https://business.facebook.com
   - Select your business account
   - Navigate to WhatsApp Manager

2. **Create New Template**
   - Click "Message Templates" in the left menu
   - Click "Create Template"
   - Select "Appointment Update" as category
   - Choose "Spanish (Mexico)" as language

3. **Configure Template**
   - Enter the template name exactly as shown above
   - Copy the template content
   - Add parameters by clicking "Add Variable"
   - For reminder template, add Quick Reply buttons

4. **Submit for Approval**
   - Review the template
   - Submit for WhatsApp approval
   - Wait 24-48 hours for approval

## Testing Templates

Once approved, templates can be tested using:

```python
from app.services.whatsapp_template_service import WhatsAppTemplateService

template_service = WhatsAppTemplateService()

# Test appointment confirmation
template_service.send_appointment_confirmation_template(
    phone_number_id="YOUR_PHONE_NUMBER_ID",
    to_number="521XXXXXXXXXX",
    patient_name="Juan Pérez",
    doctor_name="Dr. García",
    appointment_date="miércoles, 23 de julio de 2025",
    appointment_time="11:00 a.m.",
    location="Av. Universidad 123, Col. Centro"
)
```

## Important Notes

1. **Template Names Must Match**: The template names in WhatsApp Business must exactly match those in the code:
   - `appointment_confirmation`
   - `appointment_reminder`

2. **Language Code**: Templates must be created in Spanish (Mexico) with code `es_MX`

3. **Approval Time**: Templates typically take 24-48 hours to be approved

4. **Template Quality**: Ensure templates are:
   - Professional and clear
   - Free of spelling errors
   - Compliant with WhatsApp policies

5. **Fallback**: If templates fail, the system logs the error but doesn't fail the appointment creation

## Monitoring

Check logs for template sending status:
```
grep "template" /path/to/logs/app.log
```

Template failures will show:
- Template not found
- Template not approved
- Invalid parameters
- Rate limiting errors