import streamlit as st
import sqlite3
import pandas as pd
import qrcode
import io
import numpy as np
import cv2
import uuid
import zipfile
from PIL import Image, ImageDraw, ImageFont

# ---------------- PAGE CONFIG ----------------
st.set_page_config(page_title="AI Innovate QR System", page_icon="🚀", layout="wide")

CLUB_NAME = "AINNOVAT CLUB"

# ---------------- DATABASE ----------------
conn = sqlite3.connect("teams.db", check_same_thread=False)
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS participants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    unique_id TEXT,
    student_name TEXT,
    college_name TEXT,
    phone_no TEXT,
    status TEXT DEFAULT 'Pending'
)
""")
conn.commit()

# ---------------- SESSION ----------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "role" not in st.session_state:
    st.session_state.role = None

# ---------------- USERS ----------------
users = {
    "admin": {"password": "admin123", "role": "Admin"},
    "admin1": {"password": "admin", "role": "Admin"},
    "scanner1": {"password": "scan123", "role": "Scanner"},
    "staff1": {"password": "staff123", "role": "Staff"}
}

# ---------------- LOGIN PAGE ----------------
if not st.session_state.logged_in:

    st.markdown(f"<h1 style='text-align:center; color:#2E8B57;'>{CLUB_NAME}</h1>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align:center;'>Food Token System</h3>", unsafe_allow_html=True)

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login", use_container_width=True):
        if username in users and users[username]["password"] == password:
            st.session_state.logged_in = True
            st.session_state.role = users[username]["role"]
            st.rerun()
        else:
            st.error("Invalid Credentials")

    st.stop()

# ---------------- SIDEBAR ----------------
st.sidebar.title("Navigation")

if st.session_state.role == "Admin":
    menu = st.sidebar.radio("Go to", ["Dashboard", "Upload Excel", "Scanner", "Download QR"])
elif st.session_state.role == "Scanner":
    menu = st.sidebar.radio("Go to", ["Scanner"])
else:
    menu = st.sidebar.radio("Go to", ["Dashboard", "Download QR"])

if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.session_state.role = None
    st.rerun()

# ---------------- TOP HEADER ----------------
st.markdown(f"<h1 style='text-align:center; color:#2E8B57;'>{CLUB_NAME}</h1>", unsafe_allow_html=True)

# ---------------- DASHBOARD ----------------
if menu == "Dashboard":

    st.title("Dashboard")

    df = pd.read_sql_query("SELECT * FROM participants WHERE status!='Deleted'", conn)

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Participants", len(df))
    col2.metric("Collected", len(df[df["status"] == "Collected"]))
    col3.metric("Pending", len(df[df["status"] == "Pending"]))

    st.dataframe(df, use_container_width=True)

# ---------------- UPLOAD EXCEL ----------------
elif menu == "Upload Excel":

    st.title("Upload Participants Excel")
    st.info("Excel must contain columns: student_name | college_name | phone_no")

    add_file = st.file_uploader("Upload Excel to ADD Participants", type=["xlsx"])
    delete_file = st.file_uploader("Upload Excel to DELETE Participants", type=["xlsx"])

    # -------- ADD EXCEL --------
    if add_file:
        df_add = pd.read_excel(add_file)
        required_cols = {"student_name", "college_name", "phone_no"}

        if required_cols.issubset(df_add.columns):

            for _, row in df_add.iterrows():
                unique_id = "AI-" + str(uuid.uuid4())[:8]

                c.execute("""
                    INSERT INTO participants (unique_id, student_name, college_name, phone_no)
                    VALUES (?, ?, ?, ?)
                """, (unique_id, row["student_name"], row["college_name"], str(row["phone_no"])))

            conn.commit()
            st.success("✅ Participants Added Successfully")

        else:
            st.error("Excel Format Incorrect")

    # -------- DELETE EXCEL (SOFT DELETE) --------
    if delete_file:
        df_delete = pd.read_excel(delete_file)
        required_cols = {"student_name", "college_name", "phone_no"}

        if required_cols.issubset(df_delete.columns):

            for _, row in df_delete.iterrows():
                c.execute("""
                    UPDATE participants
                    SET status='Deleted'
                    WHERE student_name=? AND college_name=? AND phone_no=?
                """, (row["student_name"], row["college_name"], str(row["phone_no"])))

            conn.commit()
            st.warning("⚠ Participants Marked as Deleted")

        else:
            st.error("Delete Excel Format Incorrect")

    # -------- SHOW ALL DATA INCLUDING DELETED --------
    st.subheader("📋 All Participants (Including Deleted)")
    full_df = pd.read_sql_query("SELECT * FROM participants", conn)
    st.dataframe(full_df, use_container_width=True)

    # -------- PERMANENT DELETE OPTION (ONLY HERE) --------
    st.subheader("⚠ Permanent Delete Section")

    deleted_count = len(full_df[full_df["status"] == "Deleted"])
    st.write(f"Deleted Records Count: {deleted_count}")

    if st.button("🔥 Permanently Delete All Marked Records"):
        c.execute("DELETE FROM participants WHERE status='Deleted'")
        conn.commit()
        st.success("Deleted Records Permanently Removed")
        st.rerun()
# ---------------- SCANNER ----------------
elif menu == "Scanner":

    st.title("QR Scanner")

    # ✅ CREATE TABS (THIS WAS MISSING)
    tab1, tab2 = st.tabs(["📷 Camera Scan", "⌨ Manual Entry"])

    # -------- CAMERA SCAN --------
    with tab1:

        camera = st.camera_input("Scan QR Code")

        if camera:
            file_bytes = np.asarray(bytearray(camera.read()), dtype=np.uint8)
            img = cv2.imdecode(file_bytes, 1)

            detector = cv2.QRCodeDetector()
            data, bbox, _ = detector.detectAndDecode(img)

            if data:
                c.execute("SELECT * FROM participants WHERE unique_id=? AND status!='Deleted'", (data,))
                person = c.fetchone()

                if person:
                    st.success("Participant Found ✅")
                    st.write("Name:", person[2])
                    st.write("College:", person[3])
                    st.write("Phone:", person[4])
                    st.write("Status:", person[5])

                    if person[5] != "Collected":
                        if st.button("Mark as Collected"):
                            c.execute("UPDATE participants SET status='Collected' WHERE unique_id=?", (data,))
                            conn.commit()
                            st.success("Marked as Collected")
                            st.rerun()
                else:
                    st.error("Invalid QR")

    # -------- MANUAL ENTRY --------
    with tab2:

        manual_id = st.text_input("Enter Unique ID")

        if manual_id:
            c.execute("SELECT * FROM participants WHERE unique_id=?", (manual_id,))
            person = c.fetchone()

            if person:
                st.subheader("Participant Details")
                st.write("**Name:**", person[2])
                st.write("**College:**", person[3])
                st.write("**Phone:**", person[4])
                st.write("**Current Status:**", person[5])

                if person[5] == "Collected":
                    st.warning("⚠ Already Collected")
                else:
                    if st.button("Mark as Collected (Manual)"):
                        c.execute("UPDATE participants SET status='Collected' WHERE unique_id=?", (manual_id,))
                        conn.commit()
                        st.success("Marked as Collected ✅")
                        st.rerun()
            else:
                st.error("ID Not Found ❌")
# ---------------- DOWNLOAD QR ----------------
elif menu == "Download QR":

    st.title("⬇ Download QR Codes")

    df = pd.read_sql_query("SELECT * FROM participants", conn)

    if df.empty:
        st.warning("No participants found ❗")
    else:

        st.subheader("🎯 Download Individual QR")

        selected_name = st.selectbox(
            "Select Participant",
            df["student_name"] + " - " + df["unique_id"]
        )

        if selected_name:
            selected_id = selected_name.split(" - ")[1]
            person = df[df["unique_id"] == selected_id].iloc[0]

            qr = qrcode.make(person["unique_id"])
            qr_img = qr.convert("RGB")

            width, height = qr_img.size
            new_img = Image.new("RGB", (width, height + 100), "white")
            new_img.paste(qr_img, (0,0))

            draw = ImageDraw.Draw(new_img)
            text = f"{person['student_name']}\n{person['college_name']}"
            draw.text((10, height + 10), text, fill="black")

            img_bytes = io.BytesIO()
            new_img.save(img_bytes, format="PNG")

            st.download_button(
                label="Download Selected QR",
                data=img_bytes.getvalue(),
                file_name=f"{person['student_name']}_QR.png",
                mime="image/png"
            )

        st.subheader("📦 Download All QR (ZIP)")

        if st.button("Generate ZIP File"):

            zip_buffer = io.BytesIO()

            with zipfile.ZipFile(zip_buffer, "w") as zf:
                for _, row in df.iterrows():

                    qr = qrcode.make(row["unique_id"])
                    qr_img = qr.convert("RGB")

                    width, height = qr_img.size
                    new_img = Image.new("RGB", (width, height + 100), "white")
                    new_img.paste(qr_img, (0,0))

                    draw = ImageDraw.Draw(new_img)
                    text = f"{row['student_name']}\n{row['college_name']}"
                    draw.text((10, height + 10), text, fill="black")

                    img_bytes = io.BytesIO()
                    new_img.save(img_bytes, format="PNG")

                    filename = f"{row['student_name']}_{row['unique_id']}.png"
                    zf.writestr(filename, img_bytes.getvalue())

            st.download_button(
                label="Download All QR ZIP",
                data=zip_buffer.getvalue(),
                file_name="All_QR_Codes.zip",
                mime="application/zip"
            )