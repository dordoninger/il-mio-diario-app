import streamlit as st
import pymongo
from datetime import datetime, timedelta
from streamlit_quill import st_quill
from streamlit_drawable_canvas import st_canvas
from PIL import Image
import io
import time
import uuid
import bson.binary
import json
import re

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(page_title="DOR NOTES", page_icon="📄", layout="wide")

# --- 2. STATE MANAGEMENT ---
if 'text_size' not in st.session_state: st.session_state.text_size = "16px"
if 'edit_trigger' not in st.session_state: st.session_state.edit_trigger = 0
if 'reset_counter' not in st.session_state: st.session_state.reset_counter = 0
if 'create_key' not in st.session_state: st.session_state.create_key = str(uuid.uuid4())

# GRID COLUMNS SETTING
if 'grid_cols' not in st.session_state: st.session_state.grid_cols = 4

# --- 3. CSS AESTHETIC ---
st.markdown(f"""
<style>
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
    .streamlit-expander {{
        border-radius: 12px !important;
        border: 1px solid #e0e0e0 !important;
        box-shadow: 0 2px 5px rgba(0,0,0,0.03);
        background-color: white;
        margin-bottom: 10px;
    }}
    .streamlit-expanderHeader {{
        font-weight: 600;
        font-size: 1.0rem;
        color: #333;
        background-color: #fff;
        border-radius: 12px 12px 0 0;
        padding-top: 0.5rem !important;
        padding-bottom: 0.5rem !important;
    }}
    .streamlit-expanderContent {{
        border-top: 1px solid #f8f8f8;
        font-size: {st.session_state.text_size};
        padding-top: 10px;
        border-radius: 0 0 12px 12px;
    }}
    .quill-read-content {{
        font-size: {st.session_state.text_size} !important;
        font-family: 'Georgia', serif;
        line-height: 1.6;
    }}
    .quill-read-content a {{
        color: #1E90FF !important;
        text-decoration: underline !important;
        cursor: pointer !important;
    }}
    .dor-badge {{
        display: inline-block;
        background-color: #f0f0f0;
        color: #333;
        border: 1px solid #ddd;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-family: 'Helvetica', sans-serif;
        margin-right: 5px;
        margin-bottom: 5px;
        font-weight: 600;
        letter-spacing: 0.5px;
        text-transform: uppercase;
    }}
    div[data-baseweb="input"] {{ border-color: #e0e0e0 !important; border-radius: 8px !important; }}
    div[data-baseweb="input"]:focus-within {{ border: 1px solid #333333 !important; box-shadow: none !important; }}
    div[data-baseweb="textarea"] {{ border-color: #e0e0e0 !important; border-radius: 8px !important; }}
    div[data-baseweb="textarea"]:focus-within {{ border: 1px solid #333333 !important; box-shadow: none !important; }}
    input:focus {{ outline: none !important; }}
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
    div[data-testid="column"] {{ display: flex; align-items: center; }}
    .pinned-header {{
        font-family: 'Helvetica Neue', 'Helvetica', 'Arial', sans-serif;
        font-weight: 300;
        font-size: 1.1rem;
        color: #000;
        margin-top: 20px;
        margin-bottom: 10px;
        border-bottom: 1px solid #eee;
        padding-bottom: 5px;
        letter-spacing: 1px;
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

# --- 5. LOGIC & UTILS ---
def ensure_custom_order():
    count_missing = collection.count_documents({"custom_order": {"$exists": False}})
    if count_missing > 0:
        all_notes = list(collection.find().sort("data", 1))
        for index, note in enumerate(all_notes):
            collection.update_one({"_id": note["_id"]}, {"$set": {"custom_order": index}})

ensure_custom_order()

def convert_notes_to_json(note_list):
    export_list = []
    for nota in note_list:
        nota_export = nota.copy()
        nota_export['_id'] = str(nota['_id'])
        nota_export['data'] = nota['data'].strftime("%Y-%m-%d %H:%M:%S")
        if 'file_data' in nota_export: del nota_export['file_data']
        if 'drawing_json' in nota_export: del nota_export['drawing_json'] # Exclude heavy vector data
        export_list.append(nota_export)
    return json.dumps(export_list, indent=4)

def process_content_for_display(html_content):
    if not html_content: return ""
    html_content = re.sub(r'<a href="(.*?)"', r'<a href="\1" target="_blank" style="color: #1E90FF !important; text-decoration: underline !important; cursor: pointer;" rel="noopener noreferrer"', html_content)
    html_content = html_content.replace('<span class="ql-ui" contenteditable="false"></span>', '')
    html_content = re.sub(r'<li data-list="unchecked">(.*?)</li>', r'<div style="display: flex; align-items: flex-start; margin-bottom: 4px; margin-left: 5px;"><span style="margin-right: 10px; font-size: 1.2em; color: #555; line-height: 1.2;">&#9744;</span><span>\1</span></div>', html_content, flags=re.DOTALL)
    html_content = re.sub(r'<li data-list="checked">(.*?)</li>', r'<div style="display: flex; align-items: flex-start; margin-bottom: 4px; margin-left: 5px; color: #888; text-decoration: line-through;"><span style="margin-right: 10px; font-size: 1.2em; color: #333; text-decoration: none; line-height: 1.2;">&#9745;</span><span>\1</span></div>', html_content, flags=re.DOTALL)
    html_content = html_content.replace('<ul>', '').replace('</ul>', '')
    return html_content

def render_badges(labels_list):
    if not labels_list: return ""
    html = ""
    for label in labels_list:
        html += f"<span class='dor-badge'>{label}</span>"
    return html

def hex_to_rgba(hex_color, opacity):
    hex_color = hex_color.lstrip('#')
    return f"rgba({int(hex_color[0:2], 16)}, {int(hex_color[2:4], 16)}, {int(hex_color[4:6], 16)}, {opacity})"

# --- 6. TOOLBAR CONFIG ---
toolbar_config = [
    ['bold', 'italic', 'underline', 'strike'],
    [{ 'header': [1, 2, 3, False] }],
    [{ 'list': 'ordered'}, { 'list': 'bullet'}, { 'list': 'check' }],
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
    st.write("**Appearance**")
    cols_opt = st.slider("Grid Columns", min_value=1, max_value=5, value=st.session_state.grid_cols)
    if cols_opt != st.session_state.grid_cols:
        st.session_state.grid_cols = cols_opt
        st.rerun()
    size_opt = st.select_slider("Text Size", options=["14px", "16px", "18px", "20px", "24px"], value=st.session_state.text_size)
    if size_opt != st.session_state.text_size:
        st.session_state.text_size = size_opt
        st.rerun()
    st.divider()
    st.write("**Data**")
    all_notes = list(collection.find({}))
    json_data = convert_notes_to_json(all_notes)
    st.download_button("Download Backup (.json)", data=json_data, file_name=f"backup_{datetime.now().strftime('%Y%m%d')}.json", mime="application/json")
    st.write("**Maintenance**")
    if st.toggle("Auto-delete items older than 30 days"):
        limit = datetime.now() - timedelta(days=30)
        res = collection.delete_many({"deleted": True, "data": {"$lt": limit}})
        if res.deleted_count > 0: st.success(f"Cleaned {res.deleted_count} items.")

@st.dialog("Edit Note", width="large")
def open_edit_popup(note_id, old_title, old_content, old_filename, old_labels, note_type, drawing_data=None):
    st.markdown("### Edit Content")
    labels_str = ", ".join(old_labels) if old_labels else ""
    
    with st.form(key=f"edit_form_{note_id}"):
        new_title = st.text_input("Title", value=old_title)
        new_labels_str = st.text_input("Labels", value=labels_str)
        
        # --- EDIT LOGIC SPLIT BY TYPE ---
        new_content = old_content # Default
        new_drawing_json = drawing_data # Default
        new_image_bytes = None
        
        if note_type == "disegno":
            # DRAWING TOOLS
            t_col, w_col = st.columns([2, 1])
            with t_col:
                tool = st.radio("Tool", ["🖊️ Pen", "🖍️ Highlighter", "🧼 Eraser"], horizontal=True)
            with w_col:
                stroke_width = st.slider("Width", 1, 30, 3)
            
            # Determine Color/Opacity based on Tool
            base_color = st.color_picker("Color", "#000000") if tool != "🧼 Eraser" else "#ffffff"
            
            final_color = base_color
            if tool == "🖍️ Highlighter":
                final_color = hex_to_rgba(base_color, 0.3)
                if stroke_width < 10: stroke_width = 15 # Default thicker for highlighter
            if tool == "🧼 Eraser":
                if stroke_width < 10: stroke_width = 20 # Default thicker for eraser

            # Initial Drawing Logic:
            # If we have JSON (vector data), use it (Fully Editable).
            # If not (old notes), create empty canvas (Image will be in background if loaded properly, 
            # but st_canvas handles background separately. For simplicity, we start fresh or overlay).
            init_draw = json.loads(drawing_data) if drawing_data else None
            
            canvas_result = st_canvas(
                fill_color="rgba(0,0,0,0)",
                stroke_width=stroke_width,
                stroke_color=final_color,
                background_color="#FFFFFF",
                initial_drawing=init_draw,
                update_streamlit=True,
                height=400,
                drawing_mode="freedraw",
                key=f"canvas_edit_{note_id}",
            )
        else:
            # TEXT TOOLS
            unique_key = f"quill_edit_{note_id}_{st.session_state.edit_trigger}"
            new_content = st_quill(value=old_content, toolbar=toolbar_config, html=True, key=unique_key)
        
        st.divider()
        if note_type != "disegno":
            st.markdown("### Attachments")
            new_file = st.file_uploader("Replace File", type=['pdf', 'docx', 'txt', 'mp3', 'wav', 'jpg', 'png'])
        else:
            new_file = None # Drawing replaces file logic

        submitted = st.form_submit_button("Save Changes", type="primary")
        
        if submitted:
            labels_list = [tag.strip() for tag in new_labels_str.split(",") if tag.strip()]
            update_data = {
                "titolo": new_title, 
                "labels": labels_list,
                "data": datetime.now() 
            }
            
            if note_type == "disegno":
                if canvas_result.image_data is not None:
                    # Save Vector Data
                    update_data["drawing_json"] = json.dumps(canvas_result.json_data)
                    # Save Rendered Image
                    img = Image.fromarray(canvas_result.image_data.astype('uint8'), 'RGBA')
                    buf = io.BytesIO()
                    img.save(buf, format='PNG')
                    update_data["file_data"] = bson.binary.Binary(buf.getvalue())
                    update_data["file_name"] = "drawing.png"
            else:
                update_data["contenuto"] = new_content
                if new_file:
                    update_data["file_name"] = new_file.name
                    update_data["file_data"] = bson.binary.Binary(new_file.getvalue())
            
            collection.update_one({"_id": note_id}, {"$set": update_data})
            st.session_state.edit_trigger += 1 
            st.rerun()

    if old_filename and note_type != "disegno":
        st.info(f"Current file: **{old_filename}**")
        if st.button("Remove file", key=f"rm_file_{note_id}"):
            collection.update_one({"_id": note_id}, {"$set": {"file_name": None, "file_data": None}})
            st.rerun()

@st.dialog("Move Note", width="large")
def open_move_popup(current_note_id):
    st.write("Select the note you want to swap positions with:")
    candidates = list(collection.find({
        "deleted": {"$ne": True},
        "_id": {"$ne": current_note_id}
    }).sort("custom_order", 1))
    
    if not candidates:
        st.warning("No other notes available.")
        return

    def get_label(n):
        status = "📌" if n.get("pinned", False) else "📄"
        return f"{status} {n['titolo']}"

    options = {n["_id"]: get_label(n) for n in candidates}
    selected_target_id = st.selectbox("Swap with:", options.keys(), format_func=lambda x: options[x])
    
    if st.button("Confirm Swap ⇄", type="primary"):
        current_note = collection.find_one({"_id": current_note_id})
        target_note = collection.find_one({"_id": selected_target_id})
        if current_note and target_note:
            order_curr = current_note.get("custom_order", 0)
            pinned_curr = current_note.get("pinned", False)
            order_targ = target_note.get("custom_order", 0)
            pinned_targ = target_note.get("pinned", False)
            collection.update_one({"_id": current_note_id}, {"$set": {"custom_order": order_targ, "pinned": pinned_targ}})
            collection.update_one({"_id": selected_target_id}, {"$set": {"custom_order": order_curr, "pinned": pinned_curr}})
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
            with st.expander(f"🗑 {note['titolo']}"):
                if note.get("tipo") == "disegno" and note.get("file_data"):
                    st.image(note["file_data"])
                else:
                    safe_content = process_content_for_display(note['contenuto'])
                    st.markdown(f"<div class='quill-read-content'>{safe_content}</div>", unsafe_allow_html=True)
                c1, c2 = st.columns(2)
                if c1.button("↺ Restore", key=f"r_{note['_id']}"):
                    collection.update_one({"_id": note['_id']}, {"$set": {"deleted": False}})
                    st.rerun()
                if c2.button("✕ Delete", key=f"k_{note['_id']}"):
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

# --- MAIN LAYOUT ---

head_col1, head_col2, head_col3 = st.columns([9.0, 0.5, 0.5])
with head_col1: st.markdown("<div class='dor-title'>DOR NOTES</div>", unsafe_allow_html=True)
with head_col2: 
    st.markdown("<div style='height: 15px;'></div>", unsafe_allow_html=True)
    if st.button("⚙", help="Settings"): open_settings()
with head_col3: 
    st.markdown("<div style='height: 15px;'></div>", unsafe_allow_html=True)
    if st.button("🗑", help="Trash"): open_trash()

st.markdown("---") 

# --- CREATE NOTE ---
expander_label = f"Create New Note{'\u200b' * st.session_state.reset_counter}"
with st.expander(expander_label, expanded=False):
    
    note_type = st.radio("Type:", ["📝 Text", "🎨 Drawing"], horizontal=True)
    
    if note_type == "📝 Text":
        with st.form("create_note_form", clear_on_submit=True):
            title_input = st.text_input("Title")
            labels_input = st.text_input("Labels (comma separated)")
            content_input = st_quill(placeholder="Write here...", html=True, toolbar=toolbar_config, key=f"quill_create_{st.session_state.create_key}")
            uploaded_file = st.file_uploader("Attachment", type=['pdf', 'docx', 'txt', 'mp3', 'wav', 'jpg', 'png'])
            submitted_create = st.form_submit_button("Save Note")
            
            if submitted_create:
                if title_input and content_input:
                    labels_list = [tag.strip() for tag in labels_input.split(",") if tag.strip()]
                    last_note = collection.find_one(sort=[("custom_order", -1)])
                    new_order = (last_note["custom_order"] + 1) if last_note and "custom_order" in last_note else 0
                    
                    doc = {
                        "titolo": title_input,
                        "contenuto": content_input,
                        "labels": labels_list,
                        "data": datetime.now(),
                        "custom_order": new_order,
                        "tipo": "testo_ricco",
                        "deleted": False, "pinned": False,
                        "file_name": uploaded_file.name if uploaded_file else None,
                        "file_data": bson.binary.Binary(uploaded_file.getvalue()) if uploaded_file else None
                    }
                    collection.insert_one(doc)
                    st.toast("Saved!", icon="✅")
                    st.session_state.create_key = str(uuid.uuid4())
                    st.session_state.reset_counter += 1
                    st.rerun()
                else:
                    st.warning("Title and content required.")
    
    else: # DRAWING
        title_input = st.text_input("Title", key="draw_title")
        labels_input = st.text_input("Labels", key="draw_labels")
        
        # DRAWING TOOLS
        c1, c2 = st.columns([2, 1])
        with c1:
            tool = st.radio("Tool", ["🖊️ Pen", "🖍️ Highlighter", "🧼 Eraser"], horizontal=True, key="draw_tool")
        with c2:
            stroke_width = st.slider("Width", 1, 30, 3, key="draw_width")
        
        base_color = st.color_picker("Color", "#000000", key="draw_color") if tool != "🧼 Eraser" else "#ffffff"
        
        final_color = base_color
        if tool == "🖍️ Highlighter":
            final_color = hex_to_rgba(base_color, 0.3)
            if stroke_width < 10: stroke_width = 15
        if tool == "🧼 Eraser":
            if stroke_width < 10: stroke_width = 20

        canvas_result = st_canvas(
            fill_color="rgba(0,0,0,0)",
            stroke_width=stroke_width,
            stroke_color=final_color,
            background_color="#FFFFFF",
            update_streamlit=True,
            height=400,
            drawing_mode="freedraw",
            key="canvas_create",
        )
        
        if st.button("Save Drawing"):
            if title_input and canvas_result.image_data is not None:
                labels_list = [tag.strip() for tag in labels_input.split(",") if tag.strip()]
                last_note = collection.find_one(sort=[("custom_order", -1)])
                new_order = (last_note["custom_order"] + 1) if last_note and "custom_order" in last_note else 0
                
                img = Image.fromarray(canvas_result.image_data.astype('uint8'), 'RGBA')
                buf = io.BytesIO()
                img.save(buf, format='PNG')
                
                doc = {
                    "titolo": title_input,
                    "contenuto": "Drawing",
                    "labels": labels_list,
                    "data": datetime.now(),
                    "custom_order": new_order,
                    "tipo": "disegno",
                    "deleted": False, "pinned": False,
                    "file_name": "drawing.png",
                    "file_data": bson.binary.Binary(buf.getvalue()),
                    "drawing_json": json.dumps(canvas_result.json_data) # SAVE VECTOR DATA
                }
                collection.insert_one(doc)
                st.toast("Saved!", icon="✅")
                st.session_state.reset_counter += 1
                st.rerun()
            else:
                st.warning("Draw something and title it.")

st.write("")
query = st.text_input("🔍", placeholder="Search...", label_visibility="collapsed")

filter_query = {"deleted": {"$ne": True}}
if query:
    filter_query = {
        "$and": [
            {"deleted": {"$ne": True}},
            {"$or": [
                {"titolo": {"$regex": query, "$options": "i"}},
                {"contenuto": {"$regex": query, "$options": "i"}},
                {"labels": {"$regex": query, "$options": "i"}}
            ]}
        ]
    }

all_notes = list(collection.find(filter_query).sort("custom_order", 1)) 

pinned_notes = [n for n in all_notes if n.get("pinned", False)]
other_notes = [n for n in all_notes if not n.get("pinned", False)]

def render_notes_grid(note_list):
    if not note_list: return
    num_cols = st.session_state.grid_cols
    cols = st.columns(num_cols)
    for index, note in enumerate(note_list):
        with cols[index % num_cols]: 
            icon_clip = "🖇️ " if note.get("file_name") else ""
            if note.get("tipo") == "disegno": icon_clip = "🎨 "
            
            labels = note.get("labels", [])
            icon_label = "🏷️ " if labels else ""
            is_pinned = note.get("pinned", False)
            icon_pin = "" 
            full_title = f"{icon_pin}{icon_label}{icon_clip}{note['titolo']}"
            
            with st.expander(full_title):
                if labels:
                    st.markdown(render_badges(labels), unsafe_allow_html=True)
                    st.write("")
                
                # CONTENT
                if note.get("tipo") == "disegno" and note.get("file_data"):
                    st.image(note["file_data"])
                else:
                    safe_content = process_content_for_display(note['contenuto'])
                    st.markdown(f"<div class='quill-read-content'>{safe_content}</div>", unsafe_allow_html=True)
                
                if note.get("file_name") and note.get("tipo") != "disegno":
                    st.markdown("---")
                    st.caption(f"Attachment: {note['file_name']}")
                    st.download_button("Download", data=note["file_data"], file_name=note["file_name"])
                
                st.markdown("---")
                
                c_mod, c_pin, c_move, c_del = st.columns(4)
                
                if c_mod.button("✎", key=f"mod_{note['_id']}", help="Edit"):
                    # Pass JSON data if it exists
                    draw_data = note.get("drawing_json", None)
                    open_edit_popup(note['_id'], note['titolo'], note['contenuto'], note.get("file_name"), labels, note.get("tipo"), draw_data)
                
                label_pin = "⚲"
                if c_pin.button(label_pin, key=f"pin_{note['_id']}", help="Pin"):
                     collection.update_one({"_id": note['_id']}, {"$set": {"pinned": not is_pinned}})
                     st.rerun()

                if c_move.button("⇄", key=f"mv_{note['_id']}", help="Move"):
                    open_move_popup(note['_id'])

                if c_del.button("🗑", key=f"del_{note['_id']}", help="Delete"):
                    confirm_deletion(note['_id'])

if not all_notes:
    st.info("No notes found.")
else:
    if pinned_notes:
        st.markdown("<div class='pinned-header'>Pinned Notes</div>", unsafe_allow_html=True)
        render_notes_grid(pinned_notes)
        st.write("") 
        st.markdown("<div class='pinned-header'>All Notes</div>", unsafe_allow_html=True)
    
    render_notes_grid(other_notes)
