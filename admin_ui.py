"""
Streamlit Admin UI for Pool Report User Management.
Run with: streamlit run admin_ui.py
"""
import streamlit as st
import pandas as pd
import httpx
import os
from sqlalchemy.orm import Session
from database import SessionLocal, User, UserPool

st.set_page_config(page_title="Pool Report Admin", layout="wide")

# API Configuration - use environment variable or default to localhost
API_URL = os.getenv("API_URL", "http://localhost:8000")

st.title("🏊 Pool Report - User Management")

# Create database session
db = SessionLocal()

# Tabs
tab1, tab2, tab3, tab4 = st.tabs(["👥 Users", "🏊 Manage Pools", "📧 Send Reports", "📊 Overview"])

with tab1:
    st.header("Registered Users")
    
    # Fetch all users
    users = db.query(User).all()
    
    if users:
        user_data = [{
            "User ID": u.user_id,
            "Username": u.username or "N/A",
            "Name": f"{u.first_name} {u.last_name or ''}".strip(),
            "Pools": len(u.pools),
            "Registered": u.created_at.strftime("%Y-%m-%d %H:%M"),
            "Last Seen": u.last_seen.strftime("%Y-%m-%d %H:%M")
        } for u in users]
        
        df = pd.DataFrame(user_data)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No users registered yet. Users appear here after sending /start to the bot.")

with tab2:
    st.header("Assign Pools to Users")
    
    users = db.query(User).all()
    
    if users:
        # User selection
        user_options = {f"{u.username or u.user_id} ({u.first_name})": u.user_id for u in users}
        selected_user = st.selectbox("Select User", list(user_options.keys()))
        user_id = user_options[selected_user]
        
        # Show current pools
        current_pools = db.query(UserPool).filter(UserPool.user_id == user_id).all()
        
        st.subheader("Current Pools")
        if current_pools:
            for i, up in enumerate(current_pools):
                col1, col2, col3 = st.columns([5, 2, 1])
                col1.text(up.pool_address)
                col2.text(up.added_at.strftime("%Y-%m-%d %H:%M"))
                if col3.button("Remove", key=f"remove_{i}"):
                    db.delete(up)
                    db.commit()
                    st.success(f"Pool removed!")
                    st.rerun()
        else:
            st.info("No pools assigned yet")
        
        # Add new pool
        st.subheader("Add Pool")
        col1, col2 = st.columns([4, 1])
        
        with col1:
            new_pool = st.text_input(
                "Pool Address (0x...)",
                placeholder="0x3de27efa2f1aa663ae5d458857e731c129069f29",
                help="Enter the full Ethereum address of the Balancer pool"
            )
        
        with col2:
            st.write("")  # Spacer
            st.write("")  # Spacer
            add_button = st.button("➕ Add Pool", use_container_width=True)
        
        if add_button:
            if new_pool.startswith("0x") and len(new_pool) == 42:
                # Check if already exists
                exists = db.query(UserPool).filter(
                    UserPool.user_id == user_id,
                    UserPool.pool_address == new_pool.lower()
                ).first()
                
                if not exists:
                    user_pool = UserPool(
                        user_id=user_id,
                        pool_address=new_pool.lower()
                    )
                    db.add(user_pool)
                    db.commit()
                    st.success(f"✅ Pool added to {selected_user}")
                    st.rerun()
                else:
                    st.warning("⚠️ Pool already assigned to this user")
            else:
                st.error("❌ Invalid pool address format. Should start with 0x and be 42 characters long.")
    else:
        st.warning("No users available. Wait for users to send /start to the bot.")

with tab3:
    st.header("Send Pool Reports")
    st.write("Send performance reports to users via email and Telegram")
    
    users = db.query(User).all()
    
    if users:
        # Filter controls
        col1, col2 = st.columns([3, 1])
        with col1:
            search = st.text_input("🔍 Search users", placeholder="Search by name or username...")
        with col2:
            show_only_with_pools = st.checkbox("Only show users with pools", value=True)
        
        # Filter users
        filtered_users = users
        if search:
            search_lower = search.lower()
            filtered_users = [u for u in filtered_users if 
                            search_lower in (u.username or "").lower() or 
                            search_lower in (u.first_name or "").lower() or
                            search_lower in str(u.user_id)]
        
        if show_only_with_pools:
            filtered_users = [u for u in filtered_users if len(u.pools) > 0]
        
        if filtered_users:
            st.write(f"**{len(filtered_users)} user(s) found**")
            st.divider()
            
            # Display users with send button
            for user in filtered_users:
                with st.container():
                    col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
                    
                    with col1:
                        st.write(f"**{user.first_name} {user.last_name or ''}**")
                        st.caption(f"@{user.username or 'N/A'} • ID: {user.user_id}")
                    
                    with col2:
                        pool_count = len(user.pools)
                        if pool_count > 0:
                            st.write(f"📊 {pool_count} pool(s)")
                            with st.expander("View pools"):
                                for pool in user.pools:
                                    st.code(pool.pool_address, language=None)
                        else:
                            st.write("⚠️ No pools assigned")
                    
                    with col3:
                        email_input = st.text_input(
                            "Email",
                            value="",
                            key=f"email_{user.user_id}",
                            placeholder="user@example.com",
                            label_visibility="collapsed"
                        )
                    
                    with col4:
                        send_button = st.button(
                            "📧 Send",
                            key=f"send_{user.user_id}",
                            disabled=(pool_count == 0 or not email_input),
                            use_container_width=True
                        )
                    
                    if send_button:
                        if not email_input:
                            st.error("Please enter an email address")
                        else:
                            with st.spinner(f"Sending report to {user.first_name}..."):
                                try:
                                    # Make API request to generate report
                                    response = httpx.post(
                                        f"{API_URL}/report",
                                        json={
                                            "user_id": user.user_id,
                                            "recipient_email": email_input
                                        },
                                        timeout=60.0
                                    )
                                    
                                    if response.status_code == 200:
                                        st.success(f"✅ Report sent to {user.first_name}!")
                                    else:
                                        error_detail = response.json().get("detail", "Unknown error")
                                        st.error(f"❌ Failed to send report: {error_detail}")
                                except httpx.TimeoutException:
                                    st.error("⏱️ Request timed out. The report may still be processing.")
                                except httpx.ConnectError:
                                    st.error("❌ Cannot connect to API. Make sure FastAPI is running on http://localhost:8000")
                                except Exception as e:
                                    st.error(f"❌ Error: {str(e)}")
                    
                    st.divider()
        else:
            st.info("No users match your search criteria")
    else:
        st.info("No users registered yet. Users will appear here after sending /start to the bot.")

with tab4:
    st.header("System Overview")
    
    total_users = db.query(User).count()
    total_pools = db.query(UserPool).count()
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Users", total_users)
    col2.metric("Total Pool Assignments", total_pools)
    col3.metric("Avg Pools/User", f"{total_pools/total_users:.1f}" if total_users > 0 else "0")
    
    # Recent activity
    st.subheader("Recent Users")
    recent_users = db.query(User).order_by(User.last_seen.desc()).limit(5).all()
    
    if recent_users:
        recent_data = [{
            "User ID": u.user_id,
            "Name": f"{u.first_name} {u.last_name or ''}".strip(),
            "Username": u.username or "N/A",
            "Last Seen": u.last_seen.strftime("%Y-%m-%d %H:%M:%S")
        } for u in recent_users]
        
        st.dataframe(pd.DataFrame(recent_data), use_container_width=True)
    else:
        st.info("No user activity yet")
    
    # Pool distribution
    st.subheader("Pool Distribution")
    if total_users > 0:
        pool_counts = db.query(User).all()
        distribution = {}
        for user in pool_counts:
            count = len(user.pools)
            distribution[count] = distribution.get(count, 0) + 1
        
        dist_data = pd.DataFrame([
            {"Pools": k, "Users": v}
            for k, v in sorted(distribution.items())
        ])
        st.bar_chart(dist_data.set_index("Pools"))
    else:
        st.info("No data available yet")

# Close database session
db.close()

# Footer
st.divider()
st.caption("Pool Report Admin Panel • User Management System")
