"""
Script to seed PostgreSQL database with sample order data.

Usage Examples:
    # Seed with 10 sample orders
    python -m scripts.seed_orders

    # Add a single order
    python -m scripts.seed_orders --single --order-id "ORD-2024-100" --product "Product Name"

    # Add order with all options
    python -m scripts.seed_orders --single --order-id "ORD-2024-101" \\
        --product "Wireless Mouse" --status "shipped" --days-ago 2
"""
import asyncio
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from postgres_client import AsyncPostgresClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# Sample order data
SAMPLE_ORDERS = [
    {
        "order_id": "1231",
        "product_description": "Wireless Bluetooth Headphones - Premium Quality",
        "status": "delivered",
        "days_ago": 5,
    },
    {
        "order_id": "1232",
        "product_description": "Smartphone Case - iPhone 15 Pro Max",
        "status": "shipped",
        "days_ago": 2,
    },
    {
        "order_id": "1233",
        "product_description": "4K Ultra HD Monitor - 27 inch",
        "status": "processing",
        "days_ago": 1,
    }

]


async def seed_orders():
    """Seed the database with sample orders."""
    client = AsyncPostgresClient()
    
    try:
        # Connect to database
        await client.connect()
        logger.info("✅ Connected to PostgreSQL database")
        
        # Create sample orders
        created_count = 0
        skipped_count = 0
        
        for order_data in SAMPLE_ORDERS:
            order_placed_at = datetime.now() - timedelta(days=order_data["days_ago"])
            
            success = await client.create_order(
                order_id=order_data["order_id"],
                product_description=order_data["product_description"],
                status=order_data["status"],
                order_placed_at=order_placed_at,
            )
            
            if success:
                created_count += 1
                logger.info(
                    f"✅ Created order: {order_data['order_id']} - "
                    f"{order_data['product_description'][:50]}..."
                )
            else:
                skipped_count += 1
                logger.info(
                    f"⏭️  Skipped order: {order_data['order_id']} (may already exist)"
                )
        
        logger.info("=" * 80)
        logger.info(f"📊 Summary: {created_count} orders created, {skipped_count} skipped")
        logger.info("=" * 80)
        
        # Verify orders were created
        logger.info("\n🔍 Verifying orders in database...")
        for order_data in SAMPLE_ORDERS[:3]:  # Check first 3 orders
            order = await client.get_order_by_id(order_data["order_id"])
            if order:
                logger.info(
                    f"✅ Verified: {order['order_id']} - Status: {order['status']}"
                )
            else:
                logger.warning(f"⚠️  Not found: {order_data['order_id']}")
        
    except Exception as e:
        logger.error(f"❌ Error seeding orders: {e}", exc_info=True)
        sys.exit(1)
    finally:
        await client.close()
        logger.info("🔌 Database connection closed")


async def add_single_order(
    order_id: str,
    product_description: str,
    status: str = "pending",
    days_ago: int = 0,
):
    """Add a single order to the database."""
    client = AsyncPostgresClient()
    
    try:
        await client.connect()
        logger.info("✅ Connected to PostgreSQL database")
        
        order_placed_at = datetime.now() - timedelta(days=days_ago)
        
        success = await client.create_order(
            order_id=order_id,
            product_description=product_description,
            status=status,
            order_placed_at=order_placed_at,
        )
        
        if success:
            logger.info(f"✅ Successfully created order: {order_id}")
            logger.info(f"   Product: {product_description}")
            logger.info(f"   Status: {status}")
            logger.info(f"   Order Date: {order_placed_at.strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            logger.warning(f"⚠️  Failed to create order: {order_id} (may already exist)")
        
        return success
        
    except Exception as e:
        logger.error(f"❌ Error adding order: {e}", exc_info=True)
        return False
    finally:
        await client.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Seed PostgreSQL database with orders",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Seed with sample orders (default)
  python -m scripts.seed_orders

  # Add a single order (REQUIRES --order-id and --product)
  python -m scripts.seed_orders --single --order-id "ORD-2024-100" --product "Product Name"

  # Add order with status and date
  python -m scripts.seed_orders --single --order-id "ORD-2024-101" \\
      --product "Wireless Mouse" --status "shipped" --days-ago 2
        """,
    )
    parser.add_argument(
        "--single",
        action="store_true",
        help="Add a single order (requires --order-id and --product)",
    )
    parser.add_argument(
        "--order-id",
        type=str,
        help="Order ID (REQUIRED for single order, e.g., 'ORD-2024-100')",
    )
    parser.add_argument(
        "--product",
        type=str,
        help="Product description (REQUIRED for single order, e.g., 'Wireless Mouse')",
    )
    parser.add_argument(
        "--status",
        type=str,
        default="pending",
        choices=["pending", "processing", "shipped", "delivered"],
        help="Order status (default: 'pending')",
    )
    parser.add_argument(
        "--days-ago",
        type=int,
        default=0,
        help="Days ago the order was placed (default: 0)",
    )
    
    args = parser.parse_args()
    
    if args.single or args.order_id:
        if not args.order_id or not args.product:
            logger.error("❌ ERROR: Both --order-id and --product are REQUIRED for single order")
            logger.error("")
            logger.error("Example:")
            logger.error('  python -m scripts.seed_orders --single --order-id "ORD-2024-100" --product "Product Name"')
            sys.exit(1)
        
        success = asyncio.run(
            add_single_order(
                order_id=args.order_id,
                product_description=args.product,
                status=args.status,
                days_ago=args.days_ago,
            )
        )
        sys.exit(0 if success else 1)
    else:
        # Seed with sample orders
        asyncio.run(seed_orders())

