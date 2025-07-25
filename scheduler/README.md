# Appointment Reminder System

Sistema automatizado para enviar recordatorios de citas vía WhatsApp a los clientes.

## Características

- **Recordatorios automáticos**: Envía recordatorios el día de la cita
- **Mensajes personalizados**: Incluye el nombre del cliente, hora y tipo de cita
- **Prevención de duplicados**: Rastrea qué recordatorios ya fueron enviados
- **Multi-cuenta**: Soporta múltiples cuentas de GHL/WhatsApp
- **Registro detallado**: Guarda logs de cada ejecución en Firestore

## Estructura del Módulo

```
scheduler/
├── __init__.py
├── appointment_reminder.py    # Lógica principal del servicio
├── templates.py              # Plantillas de mensajes en español
└── README.md                 # Esta documentación
```

## Configuración

### 1. Variables de Entorno Requeridas

Las siguientes variables deben estar configuradas en el archivo `.env`:

```bash
# Firebase
FIREBASE_CREDENTIALS_PATH=path/to/firebase-credentials.json

# WhatsApp Business API
GRAPH_API_TOKEN=your_whatsapp_api_token

# GoHighLevel
GHL_CLIENT_ID=your_ghl_client_id
GHL_CLIENT_SECRET=your_ghl_client_secret
```

### 2. Configuración de Cuentas

Cada cuenta en Firestore debe tener:
- `phone_number_id`: ID del número de WhatsApp Business
- `calendar_id`: ID del calendario en GHL
- `location_id`: ID de la ubicación en GHL
- `status`: Debe ser "active" para procesar recordatorios

## Uso

### Ejecución Manual

Para ejecutar el job de recordatorios manualmente:

```bash
# Desde el directorio raíz del proyecto
python run_reminder_job.py

# Con zona horaria específica
python run_reminder_job.py --timezone America/Mexico_City

# Modo dry-run (sin enviar mensajes)
python run_reminder_job.py --dry-run
```

### Programación con Cron

Para ejecutar diariamente a las 8:00 AM:

```bash
# Editar crontab
crontab -e

# Agregar línea (ajustar rutas según tu entorno)
0 8 * * * cd /path/to/vitalis-chatbot && /usr/bin/python run_reminder_job.py >> /var/log/vitalis-reminders.log 2>&1
```

### Configuración en Render.com

1. Crear un nuevo "Cron Job" en Render
2. Configurar:
   - **Name**: Vitalis Appointment Reminders
   - **Environment**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Command**: `python run_reminder_job.py --timezone America/Los_Angeles`
   - **Schedule**: `0 8 * * *` (diariamente a las 8 AM)

3. Agregar las variables de entorno necesarias en la configuración

## Flujo del Sistema

1. **Consulta de citas**: Obtiene todas las citas del día desde GHL
2. **Filtrado**: Excluye citas canceladas y sin número de teléfono
3. **Verificación**: Revisa si ya se envió recordatorio para cada cita
4. **Envío**: Manda mensaje personalizado vía WhatsApp
5. **Registro**: Marca el recordatorio como enviado en Firestore

## Base de Datos

### Colección: `appointment_reminders`

Almacena recordatorios enviados:
```json
{
  "appointment_id": "apt_123",
  "contact_id": "cont_456",
  "contact_phone": "+5211234567890",
  "appointment_time": "2024-01-15T10:00:00Z",
  "sent_at": "2024-01-15T08:00:00Z",
  "account_id": "acc_789",
  "location_id": "loc_012"
}
```

### Colección: `reminder_job_runs`

Registra cada ejecución del job:
```json
{
  "timestamp": "2024-01-15T08:00:00Z",
  "total_accounts": 5,
  "total_appointments": 12,
  "reminders_sent": 10,
  "errors": ["Error details..."]
}
```

## Mensajes de WhatsApp

Los mensajes se envían en español con el siguiente formato:

```
¡Buenos días Juan! 👋

Este es un recordatorio amistoso de que tiene una cita programada para hoy:

📅 *Cita:* Consulta General
🕐 *Hora:* 10:00 AM

Por favor, llegue 10 minutos antes de su cita.

Si necesita cancelar o reprogramar, responda a este mensaje y con gusto le ayudaremos.

¡Esperamos verle pronto! 😊
```

## Monitoreo

### Logs

Los logs incluyen:
- Inicio y fin de cada ejecución
- Número de cuentas procesadas
- Cantidad de recordatorios enviados
- Errores encontrados

### Métricas

Después de cada ejecución, se imprime un resumen:
```
Reminder Job Summary:
  Total Accounts: 5
  Total Appointments: 12
  Reminders Sent: 10
  Errors: 0
```

## Solución de Problemas

### Error: "No module named 'app'"
Asegúrate de ejecutar desde el directorio raíz del proyecto.

### Error: "Failed to get appointments"
Verifica que los tokens de GHL estén actualizados y las cuentas tengan acceso al calendario.

### Error: "Failed to send WhatsApp message"
- Revisa que el `GRAPH_API_TOKEN` sea válido
- Confirma que el número de WhatsApp esté registrado
- Verifica el formato del número telefónico (+52...)

### No se envían recordatorios
1. Verifica que las citas tengan número de teléfono
2. Revisa que las citas no estén canceladas
3. Confirma la zona horaria configurada
4. Busca en la colección `appointment_reminders` si ya se enviaron

## Mejoras Futuras

- [ ] Soporte para recordatorios múltiples (24h antes, 1h antes)
- [ ] Plantillas de mensaje configurables por cuenta
- [ ] Confirmación de asistencia interactiva
- [ ] Reportes de efectividad de recordatorios
- [ ] Integración con métricas de cancelación