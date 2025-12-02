import streamlit as st
import pymongo
from datetime import datetime, timedelta
from streamlit_quill import st_quill
import time
import uuid
import bson.binary
import json

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(page_title="DOR NOTES", page_icon="📄", layout="wide")

# --- 2. STATE MANAGEMENT ---
if 'text_size' not in st.session_state: st.session_state.text_size = "16px"
if 'auto_clean_enabled' not in st.session_state: st.session_state.auto_clean_enabled = False

# --- 3. CSS AESTHETIC (DOR NOTES STYLE) ---
st.markdown(f"""
<style>
    /* TITLE DOR NOTES (Thin, Elegant, Spaced) */
    .dor-title {{
        font-family: 'Helvetica Neue', 'Helvetica', 'Arial', sans-serif;
        font-weight: 300; /* Thin */
        font-size: 2.2rem;
        color: #000000;
        text-align: left;
        letter-spacing: 4px;
        text-transform: uppercase;
        margin-top: 10px;
        margin-bottom: 0px;
    }}

    /* EXPANDER STYLE */
    .streamlit-expanderHeader {{
        font-weight: 600;
        font-size: 1.0rem;
        color: #333;
        background-color: #fff;
        border-radius: 5px;
        border: 1px solid #f0f0f0;
    }}
    .streamlit-expanderContent {{
        border-top: none;
        font-size: {st.session_state.text_size};
        padding-top: 10px;
    }}
    
    /* Read Content */
    .quill-read-content {{
        font-size: {st.session_state.text_size} !important;
        font-family: 'Georgia', serif;
        line-height: 1.6;
    }}

    /* INPUTS FOCUS (Minimal Black) */
    .stTextInput > div > div > input:focus {{
        border-color: #000 !important;
        box-shadow: 0 0 0 1px #000 !important;
    }}
    
    /* LOGO ANIMATION */
    @keyframes fade-in {{
        0% {{ opacity: 0; letter-spacing: 0px; }}
        100% {{ opacity: 1; letter-spacing: 8px; }}
    }}
    .splash-text {{
        font-family: 'Helvetica Neue', sans-serif;
        font-weight: 300;
        font-size: 3rem;
        color: black;
        text-align: center;
        text-transform: uppercase;
        animation: fade-in 1.5s ease-out;
        margin-top: 30vh;
    }}
    
    /* Header Buttons Alignment */
    div[data-testid="column"] {{
        display: flex;
        align-items: center;
    }}
</style>
""", unsafe_allow_html=True)

# --- 4. INIT & DB CONNECTION ---
if 'first_load' not in st.session_state:
    placeholder = st.empty()
    with placeholder.container():
        st.markdown("<div class='splash-text'>DOR NOTES</div>", unsafe_allow_html=True)
        time.sleep(1.5)
    placeholder.empty()
    st.session_state['first_load'] = True

if 'editor_key' not in st.session_state:
    st.session_state.editor_key = str(uuid.uuid4())

@st.cache_resource
def init_connection():
    try:
        return pymongo.MongoClient(st.secrets["mongo"]["connection_string"])
    except Exception:
        return None

client = init_connection()
if client is None: st.stop()
db = client.diario_db
collection = db.note

# --- 5. UTILITY FUNCTIONS ---
def convert_notes_to_json(note_list):
    export_list = []
    for nota in note_list:
        nota_export = nota.copy()
        nota_export['_id'] = str(nota['_id'])
        nota_export['data'] = nota['data'].strftime("%Y-%m-%d %H:%M:%S")
        if 'file_data' in nota_export: del nota_export['file_data']
        export_list.append(nota_export)
    return json.dumps(export_list, indent=4)

# --- 6. TOOLBAR EDITOR ---
toolbar_config = [
    ['bold', 'italic', 'underline', 'strike'],
    [{ 'header': [1, 2, 3, False] }],
    [{ 'list': 'ordered'}, { 'list': 'bullet' }],
    [{ 'script': 'sub'}, { 'script': 'super' }], 
    [{ 'color': [] }, { 'background': [] }],
    [{ 'font': [] }],
    [{ 'align': [] }],
    ['image', 'formula'],
]

# --- 7. DIALOGS (POPUPS) ---

# Settings Popup
@st.dialog("Settings")
def open_settings():
    st.write("**Data Backup**")
    all_notes = list(collection.find({}))
    json_data = convert_notes_to_json(all_notes)
    st.download_button(
        label="Download Backup (.json)",
        data=json_data,
        file_name=f"backup_dornotes_{datetime.now().strftime('%Y%m%d')}.json",
        mime="application/json"
    )
    
    st.divider()
    
    st.write("**Accessibility**")
    size_opt = st.select_slider("Text Size", options=["14px", "16px", "18px", "20px", "24px"], value=st.session_state.text_size)
    if size_opt != st.session_state.text_size:
        st.session_state.text_size = size_opt
        st.rerun()
        
    st.divider()
    
    st.write("**Maintenance**")
    # TOGGLE FOR AUTO-CLEAN
    is_active = st.toggle("Auto-delete items older than 30 days", value=st.session_state.auto_clean_enabled)
    
    if is_active:
        st.session_state.auto_clean_enabled = True
        # Run the cleanup immediately if toggled ON
        limit_date = datetime.now() - timedelta(days=30)
        result = collection.delete_many({
            "deleted": True,
            "data": {"$lt": limit_date}
        })
        if result.deleted_count > 0:
            st.success(f"Cleaned {result.deleted_count} old notes.")
        else:
            st.caption("No old items found to clean.")
    else:
        st.session_state.auto_clean_enabled = False

# Edit Popup
@st.dialog("Edit Note", width="large")
def open_edit_popup(note_id, old_title, old_content):
    st.markdown("### Edit Content")
    new_title = st.text_input("Title", value=old_title)
    new_content = st_quill(value=old_content, toolbar=toolbar_config, html=True, key=f"edit_{note_id}")
    
    if st.button("Save Changes", type="primary"):
        collection.update_one(
            {"_id": note_id},
            {"$set": {"titolo": new_title, "contenuto": new_content, "data": datetime.now()}}
        )
        st.rerun()

# Trash Popup (Updated with Reading ability)
@st.dialog("Trash", width="large")
def open_trash():
    trash_notes = list(collection.find({"deleted": True}).sort("data", -1))
    col1, col2 = st.columns([3, 1])
    col1.write(f"Notes in trash: {len(trash_notes)}")
    
    if trash_notes:
        if col2.button("Empty Trash"):
            collection.delete_many({"deleted": True})
            st.rerun()
        
        st.divider()
        
        for note in trash_notes:
            # We use an expander here to allow reading the note content
            with st.expander(f"🗑️ {note['titolo']}"):
                # Show Content
                st.markdown(f"<div class='quill-read-content'>{note['contenuto']}</div>", unsafe_allow_html=True)
                
                st.markdown("---")
                
                # Restore / Delete Forever Buttons
                c1, c2 = st.columns(2)
                if c1.button("♻️ Restore", key=f"rest_{note['_id']}"):
                    collection.update_one({"_id": note['_id']}, {"$set": {"deleted": False}})
                    st.rerun()
                if c2.button("❌ Delete Forever", key=f"kill_{note['_id']}"):
                    collection.delete_one({"_id": note['_id']})
                    st.rerun()
    else:
        st.info("Trash is empty.")

# Delete Confirmation Popup
@st.dialog("⚠️ Confirmation")
def confirm_deletion(note_id):
    st.write("Move this note to trash?")
    c1, c2 = st.columns(2)
    if c1.button("Yes, delete", type="primary"):
        collection.update_one({"_id": note_id}, {"$set": {"deleted": True}})
        st.rerun()
    if c2.button("Cancel"):
        st.rerun()

# --- MAIN INTERFACE ---

# 1. HEADER
head_col1, head_col2, head_col3 = st.columns([6, 1, 1])

with head_col1:
    st.markdown("<div class='dor-title'>DOR NOTES</div>", unsafe_allow_html=True)

with head_col2:
    if st.button("⚙️", help="Settings"):
        open_settings()

with head_col3:
    if st.button("🗑️", help="Trash"):
        open_trash()

st.markdown("---") 

# 2. CREATE SECTION
with st.expander("Create New Note"):
    title_input = st.text_input("Title", key=f"tit_{st.session_state.editor_key}")
    content_input = st_quill(
        placeholder="Write your thoughts here...",
        html=True,
        toolbar=toolbar_config,
        key=f"quill_{st.session_state.editor_key}"
    )
    uploaded_file = st.file_uploader("Upload File", type=['pdf', 'docx', 'txt', 'mp3', 'wav', 'jpg', 'png'], key=f"file_{st.session_state.editor_key}")
    
    if st.button("Save Note"):
        if title_input and content_input:
            doc = {
                "titolo": title_input,
                "contenuto": content_input,
                "data": datetime.now(),
                "tipo": "testo_ricco",
                "deleted": False,
                "pinned": False,
                "file_name": uploaded_file.name if uploaded_file else None,
                "file_data": bson.binary.Binary(uploaded_file.getvalue()) if uploaded_file else None
            }
            collection.insert_one(doc)
            st.toast("Note saved!", icon="✅")
            st.session_state.editor_key = str(uuid.uuid4())
            time.sleep(0.2)
            st.rerun()
        else:
            st.warning("Please enter title and content.")

st.write("") # Spacer

# 3. SEARCH & GRID
query = st.text_input("🔍", placeholder="Search notes...", label_visibility="collapsed")

filter_query = {"deleted": {"$ne": True}}
if query:
    filter_query = {"$and": [{"deleted": {"$ne": True}}, {"$or": [{"titolo": {"$regex": query, "$options": "i"}}, {"contenuto": {"$regex": query, "$options": "i"}}]}]}

# Sort: Pinned first, then Date
active_notes = list(collection.find(filter_query).sort([("pinned", -1), ("data", -1)]))

if not active_notes:
    st.info("No notes found.")
else:
    cols = st.columns(3)
    for index, note in enumerate(active_notes):
        with cols[index % 3]:
            # Icons
            icon_clip = "🖇️" if note.get("file_name") else ""
            is_pinned = note.get("pinned", False)
            icon_pin = "📌 " if is_pinned else ""
            
            # Expander (Note Card)
            with st.expander(f"{icon_pin}{icon_clip} {note['titolo']}"):
                
                # Content
                st.markdown(f"<div class='quill-read-content'>{note['contenuto']}</div>", unsafe_allow_html=True)
                
                # Attachment
                if note.get("file_name"):
                    st.markdown("---")
                    st.caption(f"Attachment: {note['file_name']}")
                    st.download_button("Download", data=note["file_data"], file_name=note["file_name"])
                
                st.markdown("---")
                
                # BUTTONS
                c_mod, c_pin, c_del = st.columns(3)
                
                if c_mod.button("Edit", key=f"mod_{note['_id']}"):
                    open_edit_popup(note['_id'], note['titolo'], note['contenuto'])
                
                label_pin = "Unpin" if is_pinned else "Pin"
                if c_pin.button(label_pin, key=f"pin_{note['_id']}"):
                     new_state = not is_pinned
                     collection.update_one({"_id": note['_id']}, {"$set": {"pinned": new_state}})
                     st.rerun()

                if c_del.button("Delete", key=f"del_{note['_id']}"):
                    confirm_deletion(note['_id'])
