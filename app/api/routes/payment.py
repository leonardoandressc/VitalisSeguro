"""Payment callback routes for Stripe."""
from flask import Blueprint, request, redirect, jsonify, render_template_string
from app.services.payment_service import PaymentService
from app.services.conversation_service import ConversationService
from app.services.message_service import MessageService
from app.services.appointment_service import AppointmentService
from app.services.account_service import AccountService
from app.models.payment import PaymentStatus
from app.core.logging import get_logger
from app.core.exceptions import ValidationError, VitalisException

logger = get_logger(__name__)

bp = Blueprint("payment", __name__)

# Simple HTML templates for success and cancel pages
SUCCESS_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Pago Exitoso - Vitalis</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            background-color: #f5f5f5;
        }
        .container {
            text-align: center;
            padding: 2rem;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            max-width: 400px;
        }
        .success-icon {
            width: 80px;
            height: 80px;
            margin: 0 auto 1rem;
            background-color: #4CAF50;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .success-icon::after {
            content: "✓";
            color: white;
            font-size: 48px;
        }
        h1 {
            color: #333;
            margin-bottom: 0.5rem;
        }
        p {
            color: #666;
            line-height: 1.5;
        }
        .button {
            display: inline-block;
            margin-top: 1.5rem;
            padding: 0.75rem 2rem;
            background-color: #4CAF50;
            color: white;
            text-decoration: none;
            border-radius: 4px;
            font-weight: 500;
        }
        .button:hover {
            background-color: #45a049;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="success-icon"></div>
        <h1>¡Pago Exitoso!</h1>
        <p>Tu pago ha sido procesado correctamente.</p>
        <p>Recibirás un mensaje de WhatsApp con los detalles de tu cita.</p>
        <p>Puedes cerrar esta ventana.</p>
    </div>
</body>
</html>
"""

CANCEL_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Pago Cancelado - Vitalis</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            background-color: #f5f5f5;
        }
        .container {
            text-align: center;
            padding: 2rem;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            max-width: 400px;
        }
        .cancel-icon {
            width: 80px;
            height: 80px;
            margin: 0 auto 1rem;
            background-color: #f44336;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .cancel-icon::after {
            content: "✕";
            color: white;
            font-size: 48px;
        }
        h1 {
            color: #333;
            margin-bottom: 0.5rem;
        }
        p {
            color: #666;
            line-height: 1.5;
        }
        .button {
            display: inline-block;
            margin-top: 1.5rem;
            padding: 0.75rem 2rem;
            background-color: #2196F3;
            color: white;
            text-decoration: none;
            border-radius: 4px;
            font-weight: 500;
        }
        .button:hover {
            background-color: #1976D2;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="cancel-icon"></div>
        <h1>Pago Cancelado</h1>
        <p>Tu pago ha sido cancelado.</p>
        <p>Si necesitas ayuda o quieres intentar nuevamente, envíanos un mensaje por WhatsApp.</p>
        <p>Puedes cerrar esta ventana.</p>
    </div>
</body>
</html>
"""


@bp.route("/payment/success", methods=["GET"])
def payment_success():
    """Handle successful payment callback from Stripe."""
    try:
        conversation_id = request.args.get("conversation_id")
        
        logger.info(
            "Payment success callback received",
            extra={
                "conversation_id": conversation_id,
                "url": request.url,
                "query_params": dict(request.args)
            }
        )
        
        if not conversation_id:
            logger.warning("Payment success callback without conversation_id")
            return render_template_string(SUCCESS_HTML)
        
        logger.info(
            "Processing payment success callback",
            extra={"conversation_id": conversation_id}
        )
        
        # Get services
        payment_service = PaymentService()
        conversation_service = ConversationService()
        message_service = MessageService()
        appointment_service = AppointmentService()
        account_service = AccountService()
        
        # Get conversation
        conversation = conversation_service.repository.get(conversation_id)
        if not conversation:
            logger.error(f"Conversation not found: {conversation_id}")
            return render_template_string(SUCCESS_HTML)
        
        # Get account
        account = account_service.get_account(conversation.account_id)
        if not account:
            logger.error(f"Account not found: {conversation.account_id}")
            return render_template_string(SUCCESS_HTML)
        
        # Get payment from conversation context
        payment_id = None
        if conversation.context.appointment_info:
            payment_id = conversation.context.appointment_info.get("payment_id")
            logger.info(
                "Found appointment info in conversation",
                extra={
                    "payment_id": payment_id,
                    "has_appointment_info": True,
                    "appointment_datetime": conversation.context.appointment_info.get("datetime"),
                    "appointment_name": conversation.context.appointment_info.get("name")
                }
            )
        
        if payment_id:
            # Update payment status
            payment = payment_service.get_payment(payment_id)
            logger.info(
                "Retrieved payment record",
                extra={
                    "payment_id": payment_id,
                    "payment_status": payment.status.value if payment else "not_found"
                }
            )
            
            if payment:
                # Get appointment info first
                appointment_info = conversation.context.appointment_info
                
                # Track if payment was just updated
                payment_was_updated = False
                
                # Update payment status if still pending
                if payment.status == PaymentStatus.PENDING:
                    payment_service.update_payment_status(
                        payment_id,
                        PaymentStatus.COMPLETED,
                        {"completed_at": "payment_success_callback"}
                    )
                    logger.info(f"Updated payment {payment_id} status to COMPLETED")
                    payment_was_updated = True
                    
                    # Also update payment_status in appointment_info
                    if appointment_info:
                        appointment_info["payment_status"] = "completed"
                        conversation_service.update_appointment_info(
                            conversation_id=conversation_id,
                            appointment_info=appointment_info,
                            awaiting_confirmation=True
                        )
                
                # Create appointment in GHL regardless of who completed the payment
                # Check if appointment wasn't already created
                existing_appointment_id = appointment_info.get("ghl_appointment_id") if appointment_info else None
                
                # Check if payment is completed (either was already completed or we just updated it)
                if appointment_info and (payment_was_updated or payment.status == PaymentStatus.COMPLETED) and not existing_appointment_id:
                    logger.info("Processing appointment creation after payment completion")
                    try:
                        # Create the appointment
                        appointment_result = appointment_service.confirm_and_create_appointment(
                            conversation_id=conversation_id,
                            account=account,
                            payment_id=payment_id
                        )
                        
                        if appointment_result.get("success"):
                            # Store appointment ID to prevent duplicates
                            appointment_info["ghl_appointment_id"] = appointment_result.get("appointment_id")
                            conversation_service.update_appointment_info(
                                conversation_id=conversation_id,
                                appointment_info=appointment_info,
                                awaiting_confirmation=False
                            )
                            
                            # Send success message via WhatsApp
                            # Format the datetime
                            from datetime import datetime
                            dt = datetime.fromisoformat(appointment_info.get('datetime', ''))
                            formatted_datetime = dt.strftime("%d/%m/%Y a las %I:%M %p") if appointment_info.get('datetime') else 'N/A'
                            
                            success_message = (
                                "✅ ¡Pago confirmado y cita agendada!\n\n"
                                f"📅 Fecha: {formatted_datetime}\n"
                                f"👤 Nombre: {appointment_info.get('name', 'N/A')}\n"
                                f"📱 Teléfono: {conversation.phone_number}\n"
                                f"📍 {account.name}\n\n"
                                "Te esperamos. ¡Gracias por tu preferencia!"
                            )
                        else:
                            # Payment successful but appointment creation failed
                            success_message = (
                                "✅ Pago confirmado exitosamente.\n\n"
                                "Hubo un problema al agendar tu cita automáticamente. "
                                "Nuestro equipo te contactará pronto para confirmar tu cita.\n\n"
                                "¡Gracias por tu preferencia!"
                            )
                    except Exception as e:
                        logger.error(f"Error creating appointment after payment: {e}")
                        success_message = (
                            "✅ Pago confirmado exitosamente.\n\n"
                            "Nuestro equipo te contactará pronto para confirmar tu cita.\n\n"
                            "¡Gracias por tu preferencia!"
                        )
                    
                    # Send WhatsApp message
                    message_service._send_text_response(
                        account.phone_number_id,
                        conversation.phone_number,
                        success_message,
                        conversation_id
                    )
                elif existing_appointment_id:
                    logger.info(
                        "Appointment already created for this payment",
                        extra={
                            "payment_id": payment_id,
                            "appointment_id": existing_appointment_id
                        }
                    )
        else:
            logger.warning(
                "No payment_id found in conversation context",
                extra={
                    "conversation_id": conversation_id,
                    "has_appointment_info": bool(conversation.context.appointment_info)
                }
            )
        
        return render_template_string(SUCCESS_HTML)
        
    except Exception as e:
        logger.error(f"Error handling payment success: {e}")
        return render_template_string(SUCCESS_HTML)


@bp.route("/payment/cancel", methods=["GET"])
def payment_cancel():
    """Handle cancelled payment callback from Stripe."""
    try:
        conversation_id = request.args.get("conversation_id")
        
        if not conversation_id:
            logger.warning("Payment cancel callback without conversation_id")
            return render_template_string(CANCEL_HTML)
        
        logger.info(
            "Payment cancel callback",
            extra={"conversation_id": conversation_id}
        )
        
        # Get services
        payment_service = PaymentService()
        conversation_service = ConversationService()
        message_service = MessageService()
        account_service = AccountService()
        
        # Get conversation
        conversation = conversation_service.repository.get(conversation_id)
        if not conversation:
            logger.error(f"Conversation not found: {conversation_id}")
            return render_template_string(CANCEL_HTML)
        
        # Get account
        account = account_service.get_account(conversation.account_id)
        if not account:
            logger.error(f"Account not found: {conversation.account_id}")
            return render_template_string(CANCEL_HTML)
        
        # Update payment status if exists
        payment_id = None
        if conversation.context.appointment_info:
            payment_id = conversation.context.appointment_info.get("payment_id")
        if payment_id:
            payment = payment_service.get_payment(payment_id)
            if payment and payment.status == PaymentStatus.PENDING:
                payment_service.update_payment_status(
                    payment_id,
                    PaymentStatus.CANCELLED,
                    {"cancelled_at": "payment_cancel_callback"}
                )
        
        # Send WhatsApp message
        cancel_message = (
            "❌ El proceso de pago fue cancelado.\n\n"
            "Si necesitas ayuda o quieres intentar nuevamente, "
            "solo escríbeme y con gusto te asisto.\n\n"
            "¿Hay algo en lo que pueda ayudarte?"
        )
        
        message_service._send_text_response(
            account.phone_number_id,
            conversation.phone_number,
            cancel_message,
            conversation_id
        )
        
        # Clear appointment context
        conversation_service.cancel_appointment(conversation_id)
        
        return render_template_string(CANCEL_HTML)
        
    except Exception as e:
        logger.error(f"Error handling payment cancel: {e}")
        return render_template_string(CANCEL_HTML)