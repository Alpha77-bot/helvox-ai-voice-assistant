import asyncio
import logging
import os
import uuid
from typing import Literal, Optional, cast
from dataclasses import dataclass
from datetime import datetime
from google.genai import types

from dotenv import load_dotenv
from livekit import agents
from livekit.agents import (
    AgentSession,
    Agent,
    RoomInputOptions,
    AutoSubscribe,
)
from livekit.plugins import (
    noise_cancellation,
    google,
    silero,
)
from livekit.agents.llm import function_tool
from livekit.agents.voice import RunContext

# Import Weaviate client for RAG
from weaviate_client.async_weaviate_client import (
    get_weaviate_client,
    search,
    collection_exists,
)

# Import PostgreSQL client
from postgres_client import AsyncPostgresClient

logger = logging.getLogger(__name__)
load_dotenv()

# Weaviate RAG Configuration - Constants
WEAVIATE_COLLECTION = os.getenv("WEAVIATE_COLLECTION", "textCollection")
WEAVIATE_PROVIDER = cast(
    Literal["google_studio", "vertex_ai"], os.getenv("WEAVIATE_PROVIDER", "vertex_ai")
)
RAG_SEARCH_LIMIT = 2  # Number of knowledge base entries to retrieve
RAG_SEARCH_TYPE = "hybrid"  # "semantic" or "hybrid"
RAG_ALPHA = 0.9  # For hybrid search: 0=keyword, 1=semantic



@dataclass
class EcommerceSupportContext:
    """Holds the context for an e-commerce customer support call session."""

    order_id: Optional[str] = None
    customer_issue: Optional[str] = None
    order_data: Optional[dict] = None
    issue_resolved: Optional[bool] = None
    call_id: Optional[str] = None
    call_start_time: Optional[datetime] = None
    current_language: str = "en"  # Default to English


ECOMMERCE_SYSTEM_PROMPT = """
# E-Commerce Customer Support Agent

## WHO YOU ARE

You are a professional, empathetic, and solution-oriented customer support agent for an e-commerce service. Your goal is to help customers resolve their issues efficiently and leave them satisfied.

## SPEECH AND ACCENT

- **ALWAYS** speak with an Indian accent when communicating in English
- Use natural Indian English pronunciation and intonation patterns
- Maintain a warm, friendly, and professional tone that is characteristic of Indian customer service

## LANGUAGE HANDLING

1. **ALWAYS** start the conversation in English
2. Detect language from customer's response:
   - Hindi: Look for words like "हैं", "क्या", "मुझे", "चाहिए", "समस्या", "आदेश"
   - Kannada: Look for words like "ಆಗಿದೆ", "ಏನು", "ನನಗೆ", "ಬೇಕು", "ಸಮಸ್ಯೆ", "ಆದೇಶ"
   - English: Default language
3. Once you detect a language shift, seamlessly switch to that language and maintain it throughout
4. Use natural, conversational language appropriate to the detected language

## CONVERSATION FLOW

### 1. INITIAL STATE
**IMPORTANT:** The greeting has already been completed. The customer has been welcomed with "Welcome to our e-commerce service. How may I assist you today?" 

- You are now waiting for the customer's response
- Listen actively to what they say
- Detect language from their response and switch if needed
- Do NOT repeat the greeting - proceed directly to understanding their issue

### 2. UNDERSTAND THE ISSUE
- Listen actively to the customer's concern
- If they mention an issue but haven't provided order_id yet, ask for it:
  **Script:** "I understand you're facing an issue. To help you better, could you please provide your order ID?"

### 3. COLLECT ORDER ID
- Call `get_order_by_id(order_id)` to retrieve order information
- If order not found:
  **Script:** "I'm sorry, but I couldn't find an order with that ID. Could you please double-check and provide the correct order ID?"
- If order found:
  - If there's a previous customer_issue recorded:
    **Script:** "Thank you! I found your order for [product_description]. I can see it was placed on [order_placed_at]. I also notice there was a previous issue recorded: [previous_customer_issue]. Are you calling about the same issue, or is this a new concern?"
  - If no previous customer_issue:
    **Script:** "Thank you! I found your order for [product_description]. I can see it was placed on [order_placed_at]. How can I help you with this order?"

### 4. HANDLE CUSTOMER QUERIES
- If customer asks any question or needs information:
  - Call `search_knowledge_base(query)` to find relevant information
  - The knowledge base contains customer queries with corresponding agent responses, including:
    - Customer queries (what the customer says)
    - Agent scripts (prepared responses you should use)
    - Actions (what actions to take)
    - Categories and subcategories (for classification)
    - Scenarios (the context/situation)
    - Notes (additional guidance)
  - Use the knowledge base results to provide accurate answers
  - Follow the agent scripts closely, but adapt them naturally to the conversation
  - Be empathetic and clear in your explanations

### 5. RESOLVE THE ISSUE
- Try to understand and resolve the customer's issue
- If you can resolve it:
  - Explain the solution clearly
  - Call `mark_issue_resolved(order_id, customer_issue)` with resolution_status="resolved"
  - **Script:** "I've resolved your issue. Is there anything else I can help you with today?"
  
- If you cannot resolve it:
  - Be empathetic and apologize
  - Call `mark_issue_resolved(order_id, customer_issue)` with resolution_status="not_resolved"
  - **Script:** "I sincerely apologize for the inconvenience. I'm unable to resolve this issue directly, but I will escalate this to our specialized support team. They will contact you within 24 hours to assist you further. Is there anything else I can help you with?"

### 6. CLOSING
- Thank the customer for contacting us
- Ensure they are satisfied with the interaction
- End on a positive note

## KEY PRINCIPLES

- **EMPATHY FIRST:** Always acknowledge the customer's feelings and concerns
- **ACTIVE LISTENING:** Pay attention to what the customer is saying
- **CLARITY:** Use simple, clear language appropriate to the detected language
- **SOLUTION-ORIENTED:** Focus on finding solutions, not excuses
- **PROFESSIONALISM:** Maintain a calm, professional tone even in difficult situations
- **ACCURACY:** Use knowledge base search to provide accurate information
- **FOLLOW-UP:** Always confirm if the customer needs anything else before ending

## GUARDRAILS AND SCOPE LIMITATIONS

**CRITICAL:** Your role is STRICTLY LIMITED to e-commerce product and order-related support. You MUST NOT respond to any queries outside this scope.

### WHAT YOU MUST NOT RESPOND TO

**DO NOT** answer, engage with, or provide information about:
- Jokes, humor, or entertainment requests
- General knowledge questions (e.g., "Who is the PM of India?", "What is the capital of France?")
- Current events, news, or politics
- Weather, sports, or unrelated topics
- Personal advice or opinions unrelated to products/orders
- Technical support for non-product issues
- Any query that is not directly related to:
  - Order inquiries and issues
  - Product information and support
  - Return and refund policies
  - Shipping and delivery questions
  - Account-related order issues
  - E-commerce policies and procedures

### HOW TO HANDLE OUT-OF-SCOPE QUERIES

When a customer asks something unrelated to products or orders:
1. **IMMEDIATELY** recognize it's outside your scope
2. **DO NOT** attempt to answer the question
3. **DO NOT** use any tools (get_order_by_id, search_knowledge_base, mark_issue_resolved)
4. Politely redirect using this exact script:

**Script:** "I'm only here to assist you with your product queries and order-related concerns. How can I help you with your order today?"

5. If they persist with non-product queries, politely repeat the redirect:
   **Script:** "I understand, but I'm specifically designed to help with product and order inquiries. Do you have any questions about your order or products?"

### SCOPE VERIFICATION

Before responding to any query, ask yourself:
- Is this related to an order, product, or e-commerce service?
- If NO → Use the redirect script above
- If YES → Proceed with normal support flow

**REMEMBER:** Even if the world ends, your job is ONLY to assist with product queries. Stay focused and redirect politely but firmly.

## TOOLS AVAILABLE

- `get_order_by_id(order_id)` - Retrieve order information from database
- `search_knowledge_base(query)` - Search knowledge base for answers to customer queries. Returns:
  - Customer queries matching the search
  - Agent scripts (prepared responses to use)
  - Actions to take
  - Categories and subcategories
  - Scenarios (context)
  - Notes (additional guidance)
  Use the agent scripts as templates, adapting them naturally to the conversation flow.
- `mark_issue_resolved(order_id, customer_issue, resolution_status)` - Update order resolution status in database

## SUCCESS METRICS

- Order ID collected and verified
- Customer issue understood and documented
- Appropriate resolution path taken (resolved or escalated)
- Customer satisfaction maintained
- Language appropriately detected and used
"""


class GreetingAgent(Agent):
    """
    An agent that handles the initial greeting.
    """

    def __init__(self, weaviate_client=None, postgres_client=None) -> None:
        super().__init__(
            instructions="You are a customer support agent for an e-commerce service. Greet the customer warmly in English with an Indian accent and ask how you can help them.",
        )
        self.weaviate_client = weaviate_client
        self.postgres_client = postgres_client

    async def on_enter(self) -> None:
        """Initial greeting when the call begins."""
        logger.info("[GreetingAgent] 🎬 Greeting agent started")
        
        await self.session.generate_reply(
            instructions="Greet the customer by saying: 'Welcome to our e-commerce service. How may I assist you today?'"
        )
        
        logger.info("[GreetingAgent] 🎬 Greeting completed, updating to EcommerceSupportAgent")
        self.session.update_agent(
            EcommerceSupportAgent(
                weaviate_client=self.weaviate_client,
                postgres_client=self.postgres_client
            )
        )
        logger.info("[GreetingAgent] 🎬 EcommerceSupportAgent updated")


class EcommerceSupportAgent(Agent):
    """
    An agent that handles e-commerce customer support calls.
    It retrieves order information, searches knowledge base, and resolves issues.
    """

    def __init__(self, weaviate_client=None, postgres_client=None) -> None:
        super().__init__(
            instructions=ECOMMERCE_SYSTEM_PROMPT,
            llm=google.realtime.RealtimeModel(
                model="gemini-2.5-flash-native-audio-preview-09-2025",
                voice="Charon",  # Male voice
                temperature=0.8,
                tool_behavior=types.Behavior.BLOCKING,
                thinking_config=types.ThinkingConfig(include_thoughts=False),
            ),
        )
        self.weaviate_client = weaviate_client
        self.postgres_client = postgres_client

    @function_tool()
    async def get_order_by_id(
        self,
        context: RunContext[EcommerceSupportContext],
        order_id: str,
    ) -> str:
        """
        Retrieve order information by order ID from the database.
        
        Call this when the customer provides their order ID.
        
        Args:
            order_id: The order ID provided by the customer
            
        Returns:
            Order information as a formatted string, or error message if not found
        """
        if not self.postgres_client:
            logger.warning("⚠️ PostgreSQL client not available")
            return "I apologize, but I'm currently unable to access order information. Please try again in a moment."

        try:
            logger.info(f"🔍 Retrieving order: {order_id}")
            
            order_data = await self.postgres_client.get_order_by_id(order_id)
            
            if not order_data:
                logger.info(f"ℹ️ Order {order_id} not found")
                context.userdata.order_id = order_id  # Store even if not found
                return f"Order ID {order_id} not found in our system. Please verify the order ID and try again."
            
            # Store order data in context
            context.userdata.order_id = order_id
            context.userdata.order_data = order_data
            
            # Store customer_issue if it exists from previous calls
            if order_data.get('customer_issue'):
                context.userdata.customer_issue = order_data['customer_issue']
            
            # Format order information for the agent
            order_info = f"Order ID: {order_data['order_id']}\n"
            order_info += f"Product: {order_data['product_description']}\n"
            order_info += f"Order Date: {order_data['order_placed_at']}\n"
            order_info += f"Status: {order_data['status']}\n"
            
            if order_data.get('resolution_status'):
                order_info += f"Resolution Status: {order_data['resolution_status']}\n"
            
            # Include previous customer_issue if it exists
            if order_data.get('customer_issue'):
                order_info += f"\nPrevious Customer Issue: {order_data['customer_issue']}\n"
                order_info += "NOTE: This order has a previous customer issue recorded. Acknowledge this and ask if they're calling about the same issue or a new one."
            
            logger.info(f"✅ Order {order_id} retrieved successfully")
            if order_data.get('customer_issue'):
                logger.info(f"📝 Previous customer issue found: {order_data['customer_issue']}")
            return order_info

        except Exception as e:
            logger.error(f"❌ Error retrieving order {order_id}: {e}", exc_info=True)
            return f"I encountered an error while retrieving order {order_id}. Please try again."

    @function_tool()
    async def search_knowledge_base(
        self,
        context: RunContext[EcommerceSupportContext],
        query: str,
    ) -> str:
        """
        Search the knowledge base for answers to customer queries.
        
        Use this when the customer asks questions about:
        - Return policies
        - Refund processes
        - Product information
        - Shipping details
        - Account issues
        - General e-commerce policies
        
        Args:
            query: The customer's question or query
            
        Returns:
            Relevant information from the knowledge base
        """
        if not self.weaviate_client:
            logger.warning("⚠️ Knowledge base search requested but client not available")
            return "I apologize, but I'm currently unable to access detailed information. However, I can help you with basic support."

        try:
            logger.info(f"🔍 Knowledge base search for: '{query[:100]}...'")

            # Perform semantic/hybrid search on the knowledge base
            search_results = await search(
                client=self.weaviate_client,
                query_text=query,
                collection_name=WEAVIATE_COLLECTION,
                limit=RAG_SEARCH_LIMIT,
                search_type=RAG_SEARCH_TYPE,
                alpha=RAG_ALPHA,
            )

            if not search_results:
                logger.info("ℹ️ No knowledge base results found for query")
                return "I don't have specific information about that in my knowledge base right now. Let me help you with general support."

            # Format results for the agent
            formatted_results = []

            for idx, result in enumerate(search_results, 1):
                scenario = result.get("scenario", "")
                agent_responses = result.get("agent_responses", {})
                customer_query = result.get("customer_query", "")
                score = result.get("score", 0)

                # Skip low-quality results
                if score and score < 0.05:
                    logger.debug(f"Skipping low-score result: {score}")
                    continue

                # Format the result
                result_text = f"SCENARIO: {scenario}\n"
                result_text += f"Customer Query: {customer_query}\n\n"

                # Extract agent response details (agent_responses is a single object, not array)
                if agent_responses:
                    agent_script = agent_responses.get("agent_script", "")
                    actions = agent_responses.get("actions", "")
                    category = agent_responses.get("category", "")
                    subcategory = agent_responses.get("subcategory", "")
                    notes = agent_responses.get("notes", "")

                    result_text += f"Category: {category}\n"
                    result_text += f"Subcategory: {subcategory}\n"
                    result_text += f"Actions: {actions}\n"
                    result_text += f"Agent Script: {agent_script}\n"
                    if notes:
                        result_text += f"Notes: {notes}\n"

                formatted_results.append(result_text)

            if not formatted_results:
                logger.info("ℹ️ All results were filtered out")
                return "I don't have specific information about that in my knowledge base right now. Let me help you with general support."

            result_text = "\n\n" + "=" * 60 + "\n\n".join(formatted_results)
            logger.info(f"✅ Found {len(formatted_results)} relevant scenario(s)")
            
            return result_text

        except Exception as e:
            logger.error(f"❌ Error in knowledge base search: {e}", exc_info=True)
            return "I'm having trouble accessing detailed information right now, but I can still help you with basic support."

    @function_tool()
    async def mark_issue_resolved(
        self,
        context: RunContext[EcommerceSupportContext],
        order_id: str,
        customer_issue: str,
        resolution_status: str,
    ) -> str:
        """
        Mark an issue as resolved or not resolved in the database.
        
        Call this after attempting to resolve the customer's issue.
        
        Args:
            order_id: The order ID associated with the issue
            customer_issue: Description of the customer's issue
            resolution_status: Either "resolved" or "not_resolved"
            
        Returns:
            Success confirmation message
        """
        if not self.postgres_client:
            logger.warning("⚠️ PostgreSQL client not available")
            return "Unable to update resolution status in database."

        if resolution_status not in ["resolved", "not_resolved"]:
            logger.warning(f"⚠️ Invalid resolution_status: {resolution_status}")
            return "Invalid resolution status. Must be 'resolved' or 'not_resolved'."

        try:
            logger.info(
                f"📝 Updating order {order_id} resolution status to {resolution_status}"
            )

            success = await self.postgres_client.update_order_resolution(
                order_id=order_id,
                resolution_status=resolution_status,
                customer_issue=customer_issue,
            )

            if success:
                context.userdata.issue_resolved = resolution_status == "resolved"
                context.userdata.customer_issue = customer_issue
                logger.info(f"✅ Order {order_id} resolution status updated")
                return f"Resolution status updated to {resolution_status}."
            else:
                logger.error(f"❌ Failed to update resolution status for order {order_id}")
                return "Failed to update resolution status."

        except Exception as e:
            logger.error(
                f"❌ Error updating resolution status: {e}", exc_info=True
            )
            return "Error updating resolution status in database."

    async def on_exit(self) -> None:
        """Called when the agent is about to exit."""
        context = self.session.userdata
        logger.info(f"🎬 Call ending - Call ID: {context.call_id}")
        
        # Log summary
        logger.info("=" * 80)
        logger.info("📋 E-COMMERCE SUPPORT CALL SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Call ID: {context.call_id}")
        logger.info(
            f"Call Start: {context.call_start_time.strftime('%Y-%m-%d %H:%M:%S') if context.call_start_time else 'N/A'}"
        )
        logger.info(f"Call End: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("-" * 80)
        logger.info(f"📦 Order ID: {context.order_id or 'Not provided'}")
        logger.info(f"📝 Customer Issue: {context.customer_issue or 'Not provided'}")
        logger.info(
            f"✅ Issue Resolved: {context.issue_resolved if context.issue_resolved is not None else 'Not determined'}"
        )
        logger.info(f"🌐 Language: {context.current_language}")
        logger.info("=" * 80)
        self.session.shutdown()


async def _initialize_weaviate() -> tuple[Optional[object], Optional[object]]:
    """
    Initialize Weaviate connection for RAG functionality.
    
    Returns:
        Tuple of (client, context_manager) or (None, None) if connection fails
    """
    try:
        logger.info(
            f"🔌 Connecting to Weaviate (provider: {WEAVIATE_PROVIDER}, collection: {WEAVIATE_COLLECTION})"
        )

        context_manager = get_weaviate_client(WEAVIATE_PROVIDER)
        client = await context_manager.__aenter__()

        if not await collection_exists(client, WEAVIATE_COLLECTION):
            logger.warning(
                f"⚠️ Collection '{WEAVIATE_COLLECTION}' does not exist. RAG will be disabled."
            )
            await context_manager.__aexit__(None, None, None)
            return None, None

        logger.info(
            f"✅ Successfully connected to Weaviate collection: {WEAVIATE_COLLECTION}"
        )
        return client, context_manager

    except Exception as e:
        logger.error(f"❌ Failed to connect to Weaviate: {e}", exc_info=True)
        logger.warning("⚠️ Continuing without RAG functionality")
        return None, None


async def _initialize_postgres() -> Optional[AsyncPostgresClient]:
    """
    Initialize PostgreSQL connection.
    
    Returns:
        PostgreSQL client or None if connection fails
    """
    try:
        logger.info("🔌 Connecting to PostgreSQL database")
        
        client = AsyncPostgresClient()
        await client.connect()
        
        logger.info("✅ Successfully connected to PostgreSQL")
        return client

    except Exception as e:
        logger.error(f"❌ Failed to connect to PostgreSQL: {e}", exc_info=True)
        logger.warning("⚠️ Continuing without database functionality")
        return None


async def entrypoint(ctx: agents.JobContext):
    """
    Entry point for the LiveKit e-commerce support agent.
    Sets up the voice assistant session and initializes RAG and PostgreSQL connections.
    """
    await ctx.connect(auto_subscribe=AutoSubscribe.SUBSCRIBE_ALL)

    # Initialize Weaviate and PostgreSQL in parallel
    weaviate_init_task = asyncio.create_task(_initialize_weaviate())
    postgres_init_task = asyncio.create_task(_initialize_postgres())

    # Wait for participant to join the room
    await ctx.wait_for_participant()

    # Get connection results
    weaviate_client, weaviate_context_manager = await weaviate_init_task
    postgres_client = await postgres_init_task

    # Register cleanup callbacks
    if weaviate_context_manager is not None:
        async def cleanup_weaviate():
            try:
                await weaviate_context_manager.__aexit__(None, None, None)
                logger.info("🔌 Weaviate connection closed gracefully")
            except Exception as e:
                logger.error(
                    f"❌ Error closing Weaviate connection: {e}", exc_info=True
                )

        ctx.add_shutdown_callback(cleanup_weaviate)
        logger.debug("✅ Weaviate cleanup callback registered")

    if postgres_client is not None:
        async def cleanup_postgres():
            try:
                await postgres_client.close()
                logger.info("🔌 PostgreSQL connection closed gracefully")
            except Exception as e:
                logger.error(
                    f"❌ Error closing PostgreSQL connection: {e}", exc_info=True
                )

        ctx.add_shutdown_callback(cleanup_postgres)
        logger.debug("✅ PostgreSQL cleanup callback registered")

    # Create session with typed userdata
    session = AgentSession[EcommerceSupportContext](
        llm = google.realtime.RealtimeModel(
            # model="gemini-live-2.5-flash-preview-native-audio-09-2025",
            model="gemini-2.5-flash-native-audio-preview-09-2025",  # latest model
            voice="Charon",  # Male voice
            temperature=0.8,
            # instructions=LR_SYSTEM_PROMPT,
            tool_behavior=types.Behavior.NON_BLOCKING,
            thinking_config=types.ThinkingConfig(include_thoughts=False),
        ),
        userdata=EcommerceSupportContext(
            call_id=str(uuid.uuid4()),
            call_start_time=datetime.now(),
        ),
        vad=silero.VAD.load(),  # Voice Activity Detection
    )

    # Start the agent session
    await session.start(
        agent=GreetingAgent(
            weaviate_client=weaviate_client,
            postgres_client=postgres_client
        ),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC()  # Background Voice Cancellation
        ),
    )


if __name__ == "__main__":
    # Hard-coded agent name for LiveKit routing
    agent_name = "interactive-agent"
    
    agents.cli.run_app(
        agents.WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name=agent_name
        )
    )
