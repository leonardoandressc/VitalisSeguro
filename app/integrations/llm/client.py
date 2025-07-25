"""DeepSeek LLM client."""
from typing import List, Dict, Any, Optional
from langchain_deepseek import ChatDeepSeek
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from app.core.config import get_config
from app.core.exceptions import ExternalServiceError
from app.core.logging import get_logger

logger = get_logger(__name__)


class LLMClient:
    """Client for DeepSeek LLM."""
    
    def __init__(self):
        self.config = get_config()
        self.llm = ChatDeepSeek(
            model=self.config.llm_model,
            api_key=self.config.deepseek_api_key,
            temperature=self.config.llm_temperature
        )
    
    def process_conversation(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str
    ) -> str:
        """Process a conversation and return AI response."""
        try:
            # Convert messages to LangChain format
            langchain_messages = [SystemMessage(content=system_prompt)]
            
            for msg in messages:
                if msg["role"] == "user":
                    langchain_messages.append(HumanMessage(content=msg["content"]))
                elif msg["role"] == "assistant":
                    langchain_messages.append(AIMessage(content=msg["content"]))
            
            # Get response from LLM
            response = self.llm.invoke(langchain_messages)
            
            logger.info(
                "LLM processed conversation",
                extra={
                    "message_count": len(messages),
                    "response_length": len(response.content)
                }
            )
            
            return response.content
            
        except Exception as e:
            logger.error(f"LLM processing failed: {e}")
            raise ExternalServiceError(
                "DeepSeek LLM",
                f"Failed to process conversation: {str(e)}"
            )
    
    def extract_appointment_info(
        self,
        conversation_text: str,
        custom_prompt: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Extract appointment information from conversation."""
        try:
            from app.integrations.llm.prompts import get_extraction_prompt
            
            system_prompt = get_extraction_prompt(custom_prompt)
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=conversation_text)
            ]
            
            response = self.llm.invoke(messages)
            
            # Parse JSON response
            import json
            try:
                result = json.loads(response.content)
                
                # Validate required fields
                if result.get("has_appointment_info") and all(
                    result.get(field) for field in ["name", "reason", "datetime"]
                ):
                    logger.info(
                        "Extracted appointment info",
                        extra={"info": result}
                    )
                    return result
                
                return None
                
            except json.JSONDecodeError:
                # Try to extract JSON from markdown code blocks
                import re
                json_match = re.search(r'```json\s*\n(.*?)\n```', response.content, re.DOTALL)
                if json_match:
                    try:
                        result = json.loads(json_match.group(1))
                        
                        logger.info(
                            "Extracted appointment info from markdown",
                            extra={"info": result}
                        )
                        return result
                    except json.JSONDecodeError:
                        pass
                
                logger.error(f"Failed to parse LLM response as JSON: {response.content}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to extract appointment info: {e}")
            return None
    
    def generate_response(
        self,
        user_message: str,
        context: Optional[str] = None,
        custom_prompt: Optional[str] = None
    ) -> str:
        """Generate a response to a user message."""
        try:
            from app.integrations.llm.prompts import get_conversation_prompt
            
            system_prompt = get_conversation_prompt(custom_prompt, context)
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_message)
            ]
            
            response = self.llm.invoke(messages)
            
            return response.content
            
        except Exception as e:
            logger.error(f"Failed to generate response: {e}")
            raise ExternalServiceError(
                "DeepSeek LLM",
                f"Failed to generate response: {str(e)}"
            )
    
    def extract_customer_name(
        self,
        conversation_text: str
    ) -> Optional[str]:
        """Extract customer name from conversation."""
        try:
            system_prompt = """You are a name extraction assistant. Your task is to extract the customer's name from the conversation.

Rules:
1. Only extract the name if the customer explicitly provides it
2. Do not infer or guess names
3. Return ONLY the name, nothing else
4. If no name is found, return "NO_NAME_FOUND"

Examples:
- "Hola, soy Juan Pérez" → "Juan Pérez"
- "Mi nombre es María" → "María"
- "Hola, quiero agendar una cita" → "NO_NAME_FOUND"
"""
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=conversation_text)
            ]
            
            response = self.llm.invoke(messages)
            content = response.content.strip()
            
            if content and content != "NO_NAME_FOUND":
                logger.info(f"Extracted customer name: {content}")
                return content
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to extract customer name: {e}")
            return None