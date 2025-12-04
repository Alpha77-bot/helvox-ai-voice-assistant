"""
Async PostgreSQL client for e-commerce order management.
"""
import asyncio
import logging
import os
from typing import Optional, Dict, Any, List
from datetime import datetime
import asyncpg
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

# Database configuration from environment variables
# Default to 'localhost' for running outside Docker, set to 'postgres' when running inside Docker
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_USER = os.getenv("POSTGRES_USER", "ecommerce_user")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "ecommerce_pass")
POSTGRES_DB = os.getenv("POSTGRES_DB", "ecommerce_db")


class AsyncPostgresClient:
    """
    Async PostgreSQL client for managing e-commerce orders.
    """

    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
        self._connection_string = (
            f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@"
            f"{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
        )

    async def connect(self) -> None:
        """Create connection pool."""
        try:
            self.pool = await asyncpg.create_pool(
                self._connection_string,
                min_size=2,
                max_size=10,
                command_timeout=60,
            )
            logger.info("✅ Connected to PostgreSQL database")
            await self._initialize_schema()
        except Exception as e:
            logger.error(f"❌ Failed to connect to PostgreSQL: {e}", exc_info=True)
            raise

    async def close(self) -> None:
        """Close connection pool."""
        if self.pool:
            await self.pool.close()
            logger.info("🔌 PostgreSQL connection pool closed")

    async def _initialize_schema(self) -> None:
        """Initialize database schema if tables don't exist."""
        async with self.pool.acquire() as conn:
            try:
                # Create orders table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS orders (
                        order_id VARCHAR(100) PRIMARY KEY,
                        product_description TEXT NOT NULL,
                        order_placed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        status VARCHAR(50) NOT NULL DEFAULT 'pending',
                        customer_issue TEXT,
                        resolution_status VARCHAR(50) DEFAULT NULL,
                        resolved_at TIMESTAMP DEFAULT NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create index on order_id for faster lookups
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_orders_order_id 
                    ON orders(order_id)
                """)
                
                # Create index on status for filtering
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_orders_status 
                    ON orders(status)
                """)
                
                logger.info("✅ Database schema initialized")
            except Exception as e:
                logger.error(f"❌ Error initializing schema: {e}", exc_info=True)
                raise

    async def get_order_by_id(self, order_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve order by order_id.
        
        Args:
            order_id: The order ID to search for
            
        Returns:
            Order dictionary or None if not found
        """
        if not self.pool:
            raise RuntimeError("Database connection pool not initialized")
            
        async with self.pool.acquire() as conn:
            try:
                row = await conn.fetchrow(
                    """
                    SELECT 
                        order_id,
                        product_description,
                        order_placed_at,
                        status,
                        customer_issue,
                        resolution_status,
                        resolved_at,
                        created_at,
                        updated_at
                    FROM orders
                    WHERE order_id = $1
                    """,
                    order_id,
                )
                
                if row:
                    return dict(row)
                return None
            except Exception as e:
                logger.error(f"❌ Error fetching order {order_id}: {e}", exc_info=True)
                raise

    async def update_order_resolution(
        self, 
        order_id: str, 
        resolution_status: str,
        customer_issue: Optional[str] = None
    ) -> bool:
        """
        Update order resolution status.
        
        Args:
            order_id: The order ID
            resolution_status: 'resolved' or 'not_resolved'
            customer_issue: Optional description of the customer's issue
            
        Returns:
            True if update successful, False otherwise
        """
        if not self.pool:
            raise RuntimeError("Database connection pool not initialized")
            
        async with self.pool.acquire() as conn:
            try:
                resolved_at = datetime.now() if resolution_status == "resolved" else None
                
                await conn.execute(
                    """
                    UPDATE orders
                    SET 
                        resolution_status = $1,
                        resolved_at = $2,
                        customer_issue = COALESCE($3, customer_issue),
                        updated_at = CURRENT_TIMESTAMP
                    WHERE order_id = $4
                    """,
                    resolution_status,
                    resolved_at,
                    customer_issue,
                    order_id,
                )
                
                logger.info(
                    f"✅ Updated order {order_id} resolution status to {resolution_status}"
                )
                return True
            except Exception as e:
                logger.error(
                    f"❌ Error updating order {order_id} resolution: {e}", 
                    exc_info=True
                )
                return False

    async def create_order(
        self,
        order_id: str,
        product_description: str,
        status: str = "pending",
        order_placed_at: Optional[datetime] = None,
    ) -> bool:
        """
        Create a new order (for testing/initialization purposes).
        
        Args:
            order_id: Unique order identifier
            product_description: Description of the product
            status: Order status (default: 'pending')
            order_placed_at: When the order was placed (default: now)
            
        Returns:
            True if creation successful, False otherwise
        """
        if not self.pool:
            raise RuntimeError("Database connection pool not initialized")
            
        async with self.pool.acquire() as conn:
            try:
                await conn.execute(
                    """
                    INSERT INTO orders (
                        order_id,
                        product_description,
                        order_placed_at,
                        status
                    ) VALUES ($1, $2, $3, $4)
                    ON CONFLICT (order_id) DO NOTHING
                    """,
                    order_id,
                    product_description,
                    order_placed_at or datetime.now(),
                    status,
                )
                logger.info(f"✅ Created order {order_id}")
                return True
            except Exception as e:
                logger.error(f"❌ Error creating order {order_id}: {e}", exc_info=True)
                return False


@asynccontextmanager
async def get_postgres_client():
    """
    Async context manager for PostgreSQL client.
    
    Usage:
        async with get_postgres_client() as client:
            order = await client.get_order_by_id("12345")
    """
    client = AsyncPostgresClient()
    try:
        await client.connect()
        yield client
    finally:
        await client.close()

