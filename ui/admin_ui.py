"""
Streamlit Admin UI for Pool Report User Management.
Run with: streamlit run admin_ui.py
"""
import os
import sys
import streamlit as st
import pandas as pd

# Ensure project root is on sys.path when running from ui/
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from database import SessionLocal, AllowedUser, Client, ClientPool

st.set_page_config(page_title="Pool Report Admin", layout="wide")

st.title("🏊 Pool Report - Admin")

# Create database session
db = SessionLocal()

# Tabs
tab1, tab2 = st.tabs(["👥 Allowed Users", "🏷️ Clients & Pools"])

with tab1:
    st.header("Allowed Users (Telegram bot whitelist)")
    st.caption("Only users listed here can request reports by sending a client name to the Telegram bot (e.g. `aave`).")
    
    users = db.query(AllowedUser).order_by(AllowedUser.last_seen.desc()).all()
    
    if users:
        user_data = [{
            "User ID": u.user_id,
            "Username": u.username or "N/A",
            "Registered": u.created_at.strftime("%Y-%m-%d %H:%M"),
            "Last Seen": u.last_seen.strftime("%Y-%m-%d %H:%M")
        } for u in users]
        
        df = pd.DataFrame(user_data)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No allowed users yet. Add a Telegram user_id to whitelist them.")

    st.divider()
    st.subheader("Add Allowed User")
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        new_user_id = st.text_input("Telegram user_id", placeholder="5979348250")
    with col2:
        new_username = st.text_input("Username (optional)", placeholder="gustavo")
    with col3:
        st.write("")
        st.write("")
        add_user_btn = st.button("➕ Add", use_container_width=True)

    if add_user_btn:
        try:
            uid = int(new_user_id.strip())
            existing = db.query(AllowedUser).filter(AllowedUser.user_id == uid).first()
            if existing:
                st.warning("User already allowed.")
            else:
                user = AllowedUser(user_id=uid, username=new_username.strip() or None)
                db.add(user)
                db.commit()
                st.success("✅ User added to whitelist")
                st.rerun()
        except Exception:
            st.error("❌ Invalid user_id. Please enter a numeric Telegram user_id.")

    st.subheader("Remove Allowed User")
    if users:
        remove_options = {f"{u.username or 'N/A'} ({u.user_id})": u.user_id for u in users}
        to_remove = st.selectbox("Select user", list(remove_options.keys()))
        if st.button("🗑️ Remove selected user"):
            uid = remove_options[to_remove]
            db.query(AllowedUser).filter(AllowedUser.user_id == uid).delete()
            db.commit()
            st.success("✅ User removed")
            st.rerun()

with tab2:
    st.header("Clients & Pools")
    st.caption("Create a client key (e.g. `aave`) and assign one or more pool addresses to it.")

    clients = db.query(Client).order_by(Client.client_key.asc()).all()

    st.subheader("Create Client")
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        new_client_key = st.text_input("Client key", placeholder="aave", help="Lowercase key users will type in Telegram")
    with col2:
        new_display_name = st.text_input("Display name (optional)", placeholder="Aave")
    with col3:
        st.write("")
        st.write("")
        create_client_btn = st.button("➕ Create", use_container_width=True)

    if create_client_btn:
        key = (new_client_key or "").strip().lower()
        if not key:
            st.error("❌ Client key is required.")
        else:
            existing = db.query(Client).filter(Client.client_key == key).first()
            if existing:
                st.warning("Client already exists.")
            else:
                db.add(Client(client_key=key, display_name=(new_display_name.strip() or None)))
                db.commit()
                st.success("✅ Client created")
                st.rerun()

    st.divider()

    if not clients:
        st.info("No clients yet. Create one above.")
    else:
        client_options = {f"{c.client_key} ({c.display_name or 'no display'})": c.client_key for c in clients}
        selected = st.selectbox("Select client", list(client_options.keys()))
        client_key = client_options[selected]
        client = db.query(Client).filter(Client.client_key == client_key).first()

        st.subheader("Assigned Pools")
        pools = db.query(ClientPool).filter(ClientPool.client_key == client_key).order_by(ClientPool.added_at.desc()).all()
        if pools:
            for i, p in enumerate(pools):
                colA, colB, colC = st.columns([6, 2, 1])
                colA.code(p.pool_address, language=None)
                colB.write(p.added_at.strftime("%Y-%m-%d %H:%M"))
                if colC.button("Remove", key=f"rm_pool_{client_key}_{i}"):
                    db.delete(p)
                    db.commit()
                    st.success("✅ Pool removed")
                    st.rerun()
        else:
            st.info("No pools assigned yet.")

        st.subheader("Add Pool to Client")
        new_pool = st.text_input("Pool address (0x...)", placeholder="0x3de27efa2f1aa663ae5d458857e731c129069f29")
        if st.button("➕ Add pool"):
            addr = (new_pool or "").strip().lower()
            if not (addr.startswith("0x") and len(addr) == 42):
                st.error("❌ Invalid pool address format.")
            else:
                exists = db.query(ClientPool).filter(
                    ClientPool.client_key == client_key,
                    ClientPool.pool_address == addr
                ).first()
                if exists:
                    st.warning("Pool already assigned to this client.")
                else:
                    db.add(ClientPool(client_key=client_key, pool_address=addr))
                    db.commit()
                    st.success("✅ Pool added")
                    st.rerun()

        st.subheader("Danger zone")
        if st.button("🗑️ Delete client and all pools"):
            db.query(Client).filter(Client.client_key == client_key).delete()
            db.commit()
            st.success("✅ Client deleted")
            st.rerun()

# Close database session
db.close()

# Footer
st.divider()
st.caption("Pool Report Admin Panel • Client mapping + Telegram whitelist")
