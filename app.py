import streamlit as st
import pymongo
from datetime import datetime, timedelta
from streamlit_quill import st_quill
import time
import uuid
import bson.binary
import json
import re

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(page_title="DOR NOTES", page_icon="📄", layout="wide")

# --- 2. STATE MANAGEMENT ---
if 'text_size' not in st.session_state: st.session_state.text_size = "16px"
# Trigger to force updates
if 'edit_trigger' not in st.session_state: st.session_state.edit_trigger = 0

# --- 3. CSS AESTHETIC (FIXED: NO RED BORDERS) ---
st.markdown(f"""
<style>
    /* TITLE STYLE */
    .dor-title {{
        font-family: 'Helvetica Neue', 'Helvetica', 'Arial', sans-serif;
        font-weight: 300;
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
    
    /* READ CONTENT STYLE */
    .quill-read-content {{
        font-size: {st.session_state.text_size} !important;
        font-family: 'Georgia', serif;
        line-height: 1.6;
    }}
    
    /* Force Link Color in Read Mode */
    .quill-read-content a {{
        color: #1E90FF !important;
        text-decoration: underline !important;
        cursor: pointer !important;
    }}

    /* --- BLACK BORDER FORCE FIX (BUG 1 SOLVED) --- */
    
    /* 1. Input Fields (Title & Search) */
    div[data-baseweb="input"] {{
        border-color: #e0e0e0 !important;
        border-radius: 5px !important;
    }}
    
    /* Focus State - Dark Grey instead of Red */
    div[data-baseweb="input"]:focus-within {{
        border: 1px solid #333333 !important; 
        box-shadow: none !important;          
    }}

    /* 2. Text Area */
    div[data-baseweb="textarea"] {{
        border-color: #e0e0e0 !important;
        border-radius: 5px !important;
    }}
    div[data-baseweb="textarea"]:focus-within {{
        border: 1px solid #333333 !important;
        box-shadow: none !important;
    }}

    /* 3. Generic Focus Ring Removal */
    input:focus {{
        outline: none !important;
    }}

    /* ANIMATION */
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
        animation: fade-in 2.0s ease-out;
        margin-top: 30vh;
    }}
    
    div[data-testid="column"] {{
        display: flex;
        align-items: center;
    }}
</style>
""", unsafe_allow_html=True)

# --- 4. INIT & DB ---
if 'first_load' not in st.session_state:
    placeholder = st.empty()
    with placeholder.container():
        st.markdown("<div class='splash-text'>DOR NOTES</div>", unsafe_allow_html=True)
        time.sleep(2.0)
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

# --- 5. UTILS ---
def convert_notes_to_json(note_list):
    export_list = []
    for nota in note_list:
        nota_export = nota.copy()
        nota_export['_id'] = str(nota['_id'])
        nota_export['data'] = nota['data'].strftime("%Y-%m-%d %H:%M:%S")
        if 'file_data' in nota_export: del nota_export['file_data']
        export_list.append(nota_export)
    return json.dumps(export_list, indent=4)

def sanitize_links(html_content):
    # BUG 2 SOLVED: Injects style and target directly into HTML
    if not html_content: return ""
    pattern = r'<a href="([^"]*)"'
    replacement = r'<a href="\1" target="_blank" style="color: #1E90FF !important; text-decoration: underline !important; cursor: pointer;" rel="noopener noreferrer"'
    return re.sub(pattern, replacement, html_content)

# --- 6. TOOLBAR CONFIG ---
toolbar_config = [
    ['bold', 'italic', 'underline', 'strike'],
    [{ 'header': [1, 2, 3, False] }],
    [{ 'list': 'ordered'}, { 'list': 'bullet' }],
    [{ 'script': 'sub'}, { 'script': 'super' }], 
    [{ 'color': [] }, { 'background': [] }],
    [{ 'font': [] }],
    [{ 'align': [] }],
    ['image', 'formula'],
    ['link'],
]

# --- 7. POPUPS (DIALOGS) ---

@st.dialog("Settings")
def open_settings():
    st.write("**Data Backup**")
    all_notes = list(collection.find({}))
    json_data = convert_notes_to_json(all_notes)
    st.download_button("Download Backup (.json)", data=json_data, file_name=f"backup_{datetime.now().strftime('%Y%m%d')}.json", mime="application/json")
    st.divider()
    st.write("**Accessibility**")
    size_opt = st.select_slider("Text Size", options=["14px", "16px", "18px", "20px", "24px"], value=st.session_state.text_size)
    if size_opt != st.session_state.text_size:
        st.session_state.text_size = size_opt
        st.rerun()
    st.divider()
    st.write("**Maintenance**")
    if st.toggle("Auto-delete items older than 30 days"):
        limit = datetime.now() - timedelta(days=30)
        res = collection.delete_many({"deleted": True, "data": {"$lt": limit}})
        if res.deleted_count > 0: st.success(f"Cleaned {res.deleted_count} items.")

# BUG 3 SOLVED: Function accepts ONLY ID to prevent "Nested Dialogs" error
@st.dialog("Edit Note", width="large")
def open_edit_popup(note_id):
    # Fetch data internally to ensure stability
    note = collection.find_one({"_id": note_id})
    
    if not note:
        st.error("Note not found.")
        if st.button("Close"): st.rerun()
        return

    old_title = note.get('titolo', '')
    old_content = note.get('contenuto', '')
    old_filename = note.get('file_name', None)

    st.markdown("### Edit Content")
    
    col_safe, col_clean = st.columns([1, 1])
    with col_safe:
        # BUG 3 Fix: Safe Mode to edit raw HTML formula code
        mode = st.radio("Mode", ["Visual Editor", "Safe Mode (Raw HTML)"], horizontal=True, label_visibility="collapsed")
    
    current_content = old_content

    # BUG 3 Fix: Emergency Button to strip formulas if crashed
    with col_clean:
        if st.button("🚑 Repair Note (Text Only)", help="Click if editor crashes. Converts formulas to text."):
            clean_text = re.sub(
                r'<span class="ql-formula" data-value="(.*?)">.*?</span>', 
                r' **(Formula: \1)** ', 
                old_content
            )
            collection.update_one({"_id": note_id}, {"$set": {"contenuto": clean_text}})
            st.rerun()

    # FORM
    with st.form(key=f"edit_form_{note_id}"):
        new_title = st.text_input("Title", value=old_title)
        
        if mode == "Safe Mode (Raw HTML)":
            st.info("Edit `data-value=\"...\"` to change formulas manually.")
            new_content = st.text_area("Raw HTML", value=current_content, height=300)
        else:
            # Quill Editor
            unique_key = f"quill_edit_{note_id}_{int(time.time())}"
            new_content = st_quill(value=current_content, toolbar=toolbar_config, html=True, key=unique_key)
        
        st.divider()
        st.markdown("### Attachments")
        
        new_file = st.file_uploader("Replace File", type=['pdf', 'docx', 'txt', 'mp3', 'wav', 'jpg', 'png'])
        
        submitted = st.form_submit_button("Save Changes", type="primary")
        
        if submitted:
            update_data = {
                "titolo": new_title, 
                "contenuto": new_content, 
                "data": datetime.now()
            }
            if new_file:
                update_data["file_name"] = new_file.name
                update_data["file_data"] = bson.binary.Binary(new_file.getvalue())
            
            collection.update_one({"_id": note_id}, {"$set": update_data})
            st.rerun()

    if old_filename:
        st.caption(f"Attachment: {old_filename}")
        if st.button("Remove file", key=f"rm_file_{note_id}"):
            collection.update_one({"_id": note_id}, {"$set": {"file_name": None, "file_data": None}})
            st.rerun()

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
            with st.expander(f"🗑️ {note['titolo']}"):
                safe_content = sanitize_links(note['contenuto'])
                st.markdown(f"<div class='quill-read-content'>{safe_content}</div>", unsafe_allow_html=True)
                c1, c2 = st.columns(2)
                if c1.button("♻️ Restore", key=f"r_{note['_id']}"):
                    collection.update_one({"_id": note['_id']}, {"$set": {"deleted": False}})
                    st.rerun()
                if c2.button("❌ Delete", key=f"k_{note['_id']}"):
                    collection.delete_one({"_id": note['_id']})
                    st.rerun()
    else:
        st.info("Trash is empty.")

@st.dialog("Confirmation")
def confirm_deletion(note_id):
    st.write("Move to trash?")
    c1, c2 = st.columns(2)
    if c1.button("Yes", type="primary"):
        collection.update_one({"_id": note_id}, {"$set": {"deleted": True}})
        st.rerun()
    if c2.button("Cancel"): st.rerun()

# --- MAIN ---

head_col1, head_col2, head_col3 = st.columns([6, 1, 1])
with head_col1: st.markdown("<div class='dor-title'>DOR NOTES</div>", unsafe_allow_html=True)
with head_col2: 
    if st.button("⚙️", help="Settings"): open_settings()
with head_col3: 
    if st.button("🗑️", help="Trash"): open_trash()

st.markdown("---") 

with st.expander("Create New Note"):
    with st.form("create_note_form", clear_on_submit=True):
        title_input = st.text_input("Title")
        
        content_input = st_quill(
            placeholder="Write your thoughts here...",
            html=True,
            toolbar=toolbar_config,
            key="quill_create_final"
        )
        uploaded_file = st.file_uploader("Attachment", type=['pdf', 'docx', 'txt', 'mp3', 'wav', 'jpg', 'png'])
        
        submitted_create = st.form_submit_button("Save Note")
        
        if submitted_create:
            if title_input and content_input:
                doc = {
                    "titolo": title_input,
                    "contenuto": content_input,
                    "data": datetime.now(),
                    "tipo": "testo_ricco",
                    "deleted": False, "pinned": False,
                    "file_name": uploaded_file.name if uploaded_file else None,
                    "file_data": bson.binary.Binary(uploaded_file.getvalue()) if uploaded_file else None
                }
                collection.insert_one(doc)
                st.toast("Saved!", icon="✅")
                time.sleep(0.5)
                st.rerun()
            else:
                st.warning("Title and content required.")

st.write("")
query = st.text_input("🔍", placeholder="Search...", label_visibility="collapsed")
filter_query = {"deleted": {"$ne": True}}
if query:
    filter_query = {"$and": [{"deleted": {"$ne": True}}, {"$or": [{"titolo": {"$regex": query, "$options": "i"}}, {"contenuto": {"$regex": query, "$options": "i"}}]}]}

active_notes = list(collection.find(filter_query).sort([("pinned", -1), ("data", -1)]))

if not active_notes:
    st.info("No notes found.")
else:
    cols = st.columns(3)
    for index, note in enumerate(active_notes):
        with cols[index % 3]:
            icon_clip = "🖇️" if note.get("file_name") else ""
            is_pinned = note.get("pinned", False)
            icon_pin = "📌 " if is_pinned else ""
            
            with st.expander(f"{icon_pin}{icon_clip} {note['titolo']}"):
                safe_content = sanitize_links(note['contenuto'])
                st.markdown(f"<div class='quill-read-content'>{safe_content}</div>", unsafe_allow_html=True)
                
                if note.get("file_name"):
                    fname = note["file_name"].lower()
                    fdata = note["file_data"]
                    st.markdown("---")
                    st.caption(f"Attachment: {note['file_name']}")
                    
                    if fname.endswith(('.png', '.jpg', '.jpeg', '.gif')):
                        st.image(fdata)
                    elif fname.endswith(('.mp3', '.wav', '.ogg')):
                        st.audio(fdata)
                    
                    st.download_button("Download File", data=fdata, file_name=note["file_name"])
                
                st.markdown("---")
                c_mod, c_pin, c_del = st.columns(3)
                
                # UPDATED CALL FOR BUG 3 FIX:
                if c_mod.button("Edit", key=f"mod_{note['_id']}"):
                    open_edit_popup(note['_id'])
                
                label_pin = "Unpin" if is_pinned else "Pin"
                if c_pin.button(label_pin, key=f"pin_{note['_id']}"):
                     collection.update_one({"_id": note['_id']}, {"$set": {"pinned": not is_pinned}})
                     st.rerun()

                if c_del.button("Delete", key=f"del_{note['_id']}"):
                    confirm_deletion(note['_id'])
