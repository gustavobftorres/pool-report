"""
Database initialization script.
Creates all required tables in the PostgreSQL database.

Run this once after setting up PostgreSQL:
    python init_db.py
"""
from db.database import init_db, engine
from sqlalchemy import text

def check_connection():
    """Test database connection."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

if __name__ == "__main__":
    print("🗄️  Pool Report - Database Initialization")
    print("=" * 50)
    
    # Check connection
    print("\n1️⃣  Testing database connection...")
    if not check_connection():
        print("\n❌ Failed to connect to database.")
        print("\nMake sure:")
        print("  • PostgreSQL is running")
        print("  • Database exists (e.g., createdb pool_report)")
        print("  • DATABASE_URL in .env is correct")
        exit(1)
    
    print("✅ Database connection successful!")
    
    # Initialize tables
    print("\n2️⃣  Creating database tables...")
    try:
        init_db()
        print("✅ Tables created successfully!")
    except Exception as e:
        print(f"❌ Error creating tables: {e}")
        exit(1)
    
    # Verify tables
    print("\n3️⃣  Verifying tables...")
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name
            """))
            tables = [row[0] for row in result]
            
            if 'allowed_users' in tables and 'clients' in tables and 'client_pools' in tables:
                print("✅ All required tables exist:")
                for table in tables:
                    print(f"   • {table}")
            else:
                print("⚠️  Warning: Some tables may be missing")
    except Exception as e:
        print(f"⚠️  Could not verify tables: {e}")
    
    print("\n" + "=" * 50)
    print("🎉 Database initialized successfully!")
    print("\nNext steps:")
    print("  1. Start FastAPI: uvicorn main:app --reload")
    print("  2. Start Admin UI: streamlit run admin_ui.py")
    print("  3. Set up Telegram webhook (see README)")
