import streamlit as st
import pymongo
from datetime import datetime, timedelta, date
import calendar
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
if 'create_key' not in st.session_state: st.session_state.create_key = str(uuid.uuid4())

# States for Calendar
if 'cal_edit_id' not in st.session_state: st.session_state.cal_edit_id = None
if 'cal_copy_id' not in st.session_state: st.session_state.cal_copy_id = None
if 'cal_create_date' not in st.session_state: st.session_state.cal_create_date = None
if 'cal_year' not in st.session_state: st.session_state.cal_year = datetime.now().year
if 'cal_month' not in st.session_state: st.session_state.cal_month = datetime.now().month

# Settings Defaults
if 'grid_cols' not in st.session_state: st.session_state.grid_cols = 4
if 'auto_clean_enabled' not in st.session_state: st.session_state.auto_clean_enabled = True
if 'reset_counter' not in st.session_state: st.session_state.reset_counter = 0

# Canvas Defaults
if 'canvas_w' not in st.session_state: st.session_state.canvas_w = 600
if 'canvas_h' not in st.session_state: st.session_state.canvas_h = 400

# --- 3. JAVASCRIPT SWIPE ---
swipe_js = """
<script>
    var doc = window.parent.document;
    doc.addEventListener('touchstart', handleTouchStart, false);
    doc.addEventListener('touchmove', handleTouchMove, false);

    var xDown = null;
    var yDown = null;

    function handleTouchStart(evt) {
        const firstTouch = evt.touches[0];
        xDown = firstTouch.clientX;
        yDown = firstTouch.clientY;
    };

    function handleTouchMove(evt) {
        if (!xDown || !yDown) { return; }
        var xUp = evt.touches[0].clientX;
        var yUp = evt.touches[0].clientY;
        var xDiff = xDown - xUp;
        var yDiff = yDown - yUp;

        if (Math.abs(xDiff) > Math.abs(yDiff)) { 
            var tabs = doc.querySelectorAll('button[data-baseweb="tab"]');
            if (tabs.length >= 2) {
                if (xDiff > 0) { tabs[1].click(); } else { tabs[0].click(); }
            }
        }
        xDown = null;
        yDown = null;
    };
</script>
"""
st.components.v1.html(swipe_js, height=0)

# --- 4. CSS AESTHETIC & MOBILE OPTIMIZATION ---
st.markdown(f"""
<style>
    /* --- ANIMATION --- */
    @keyframes tracking-in-contract {{
        0% {{ letter-spacing: 15px; opacity: 0; }}
        40% {{ opacity: 0.6; }}
        100% {{ letter-spacing: 4px; opacity: 1; }}
    }}
    .splash-text {{
        font-family: 'Helvetica Neue', sans-serif; font-weight: 300; font-size: 3rem;
        color: black; text-align: center; text-transform: uppercase; margin-top: 35vh;
        animation: tracking-in-contract 1.5s cubic-bezier(0.215, 0.610, 0.355, 1.000) both;
    }}

    /* --- GLOBAL STYLES --- */
    .dor-title {{
        font-family: 'Helvetica Neue', 'Helvetica', 'Arial', sans-serif; font-weight: 300;
        font-size: 2.2rem; color: #000; margin: 0; white-space: nowrap; line-height: 1.2;
    }}

    .section-header {{
        font-family: 'Helvetica Neue', 'Helvetica', 'Arial', sans-serif; font-weight: 300;
        font-size: 1.4rem; color: #000; margin-top: 30px; margin-bottom: 15px;
        border-bottom: 2px solid #888; padding-bottom: 8px; letter-spacing: 2px; text-transform: uppercase;
    }}

    /* EXPANDER */
    .streamlit-expander {{ border-radius: 12px !important; border: 1px solid #e0e0e0 !important; box-shadow: 0 2px 5px rgba(0,0,0,0.03); background-color: white; margin-bottom: 10px; }}
    .streamlit-expanderHeader {{ font-weight: 600; font-size: 1.0rem; background-color: #fff; border-radius: 12px 12px 0 0; padding: 0.5rem !important; }}
    .streamlit-expanderContent {{ border-top: 1px solid #f8f8f8; font-size: {st.session_state.text_size}; padding-top: 10px; border-radius: 0 0 12px 12px; }}
    
    .quill-read-content {{ font-size: {st.session_state.text_size} !important; font-family: 'Georgia', serif; line-height: 1.6; }}
    .quill-read-content a {{ color: #1E90FF !important; text-decoration: underline !important; cursor: pointer !important; }}

    .dor-badge {{ display: inline-block; background-color: #f0f0f0; color: #333; border: 1px solid #ddd; padding: 2px 8px; border-radius: 12px; font-size: 0.75rem; font-weight: 600; letter-spacing: 0.5px; text-transform: uppercase; }}

    /* INPUTS & BUTTONS */
    div[data-baseweb="input"], div[data-baseweb="textarea"], div[data-baseweb="select"] > div, div[data-testid="stNumberInput"] > div > div {{ border-color: #e0e0e0 !important; border-radius: 8px !important; }}
    div[data-baseweb="input"]:focus-within, div[data-baseweb="textarea"]:focus-within, div[data-baseweb="select"] > div:focus-within, div[data-testid="stNumberInput"] > div > div:focus-within {{ border-color: #000000 !important; box-shadow: 0 0 0 1px #000000 !important; }}
    input:focus {{ outline: none !important; border-color: #000000 !important; }}

    .stButton button {{ padding: 0.2rem 0.5rem !important; font-size: 0.9rem !important; width: 100%; }}

    /* CALENDAR NOTE */
    .cal-note-container {{ padding: 8px 0; margin-bottom: 5px; border-bottom: 1px solid #eee; }}
    .cal-note-container:last-child {{ border-bottom: none; }}

    /* --- FILE UPLOADER CLEANUP (Make button visible, hide box) --- */
    [data-testid="stFileUploader"] section {{
        padding: 0 !important; border: none !important; background-color: transparent !important; min-height: 0px !important;
    }}
    [data-testid="stFileUploader"] section > div {{
        padding: 0 !important;
        display: block !important; /* Ensure button is shown */
    }}
    /* Hide texts and icon */
    [data-testid="stFileUploader"] div[data-testid="stMarkdownContainer"], 
    [data-testid="stFileUploader"] svg, 
    [data-testid="stFileUploader"] small {{ display: none !important; }}
    
    /* Button Style */
    [data-testid="stFileUploader"] button {{
        margin-top: 0px !important;
        border: 1px solid #e0e0e0 !important;
        display: inline-flex !important;
    }}

    /* --- MOBILE SPECIFIC OPTIMIZATIONS --- */
    @media only screen and (max-width: 600px) {{
        
        .block-container {{ padding-top: 2rem !important; padding-left: 0.5rem !important; padding-right: 0.5rem !important; }}

        /* HEADER: Force Row */
        [data-testid="stHorizontalBlock"]:has(.dor-title) {{
            display: flex !important; flex-wrap: nowrap !important; align-items: center !important; gap: 5px !important;
        }}
        [data-testid="stHorizontalBlock"]:has(.dor-title) > div:nth-child(1) {{ flex: 8 !important; min-width: 0 !important; }}
        [data-testid="stHorizontalBlock"]:has(.dor-title) > div:nth-child(2),
        [data-testid="stHorizontalBlock"]:has(.dor-title) > div:nth-child(3) {{ flex: 0 0 auto !important; width: 40px !important; min-width: 40px !important; }}

        .dor-title {{ font-size: 1.5rem !important; }}
        
        /* --- BUTTONS IN ROW FIX --- */
        /* Force columns containing small action buttons to stay in a row */
        /* This selector targets the row of buttons in Expander (Dashboard) and Calendar */
        div[data-testid="column"]:has(button[kind="secondary"]) {{
            width: auto !important;
            flex: 0 1 auto !important;
            min-width: 0 !important;
            padding: 0 2px !important;
        }}
        
        /* Force the parent container to layout horizontally */
        [data-testid="stHorizontalBlock"] {{
             flex-wrap: nowrap !important;
        }}
        
        /* Adjust button text/padding for mobile */
        .stButton button {{
            padding: 0.2rem 0.1rem !important;
            font-size: 0.8rem !important;
        }}
    }}
</style>
""", unsafe_allow_html=True)

# --- 5. INIT & DB ---
if 'first_load' not in st.session_state:
    splash = st.empty()
    with splash.container():
        st.markdown("<div class='splash-text'>DOR NOTES</div>", unsafe_allow_html=True)
        time.sleep(1.5)
    splash.empty()
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

# --- 6. UTILS ---
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
        if 'drawing_json' in nota_export: del nota_export['drawing_json']
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

def flatten_formulas_to_text(html_content):
    if not html_content: return ""
    pattern = r'<span class="ql-formula"[^>]*?data-value="(?P<formula>.+?)"[^>]*?>.*?</span>'
    return re.sub(pattern, r' $$\g<formula>$$ ', html_content, flags=re.DOTALL)

def render_badges(labels_list):
    if not labels_list: return ""
    html = ""
    for label in labels_list:
        html += f"<span class='dor-badge'>{label}</span>"
    return html

def hex_to_rgba(hex_color, opacity):
    hex_color = hex_color.lstrip('#')
    return f"rgba({int(hex_color[0:2], 16)}, {int(hex_color[2:4], 16)}, {int(hex_color[4:6], 16)}, {opacity})"

# --- 7. TOOLBAR & FORM LOGIC ---
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

def logic_save_note(title, labels_str, content, file, note_type, drawing_res, date_ref=None, is_recur=False, end_year=None):
    has_content = False
    if title and title.strip(): has_content = True
    if content and content.strip(): has_content = True
    if file: has_content = True
    if drawing_res and drawing_res.image_data is not None: has_content = True
    
    if has_content:
        labels_list = [tag.strip() for tag in labels_str.split(",") if tag.strip()]
        last_note = collection.find_one(sort=[("custom_order", -1)])
        new_order = (last_note["custom_order"] + 1) if last_note and "custom_order" in last_note else 0
        
        doc = {
            "titolo": title,
            "labels": labels_list,
            "data": datetime.now(),
            "custom_order": new_order,
            "tipo": "testo_ricco" if note_type == "Text" else "disegno",
            "deleted": False, "pinned": False,
            "calendar_date": date_ref
        }
        
        if date_ref and is_recur:
            doc["recurrence"] = "yearly"
            dt_obj = datetime.strptime(date_ref, "%Y-%m-%d")
            doc["cal_month"] = dt_obj.month
            doc["cal_day"] = dt_obj.day
            if end_year: doc["recur_end_year"] = end_year

        if note_type == "Text":
            doc["contenuto"] = content
            doc["file_name"] = file.name if file else None
            doc["file_data"] = bson.binary.Binary(file.getvalue()) if file else None
        else:
            doc["contenuto"] = "Drawing"
            img = Image.fromarray(drawing_res.image_data.astype('uint8'), 'RGBA')
            buf = io.BytesIO()
            img.save(buf, format='PNG')
            val_bytes = buf.getvalue()
            if len(val_bytes) > 0:
                doc["file_data"] = bson.binary.Binary(val_bytes)
                doc["file_name"] = "drawing.png"
                doc["drawing_json"] = json.dumps(drawing_res.json_data)
            else:
                return False

        collection.insert_one(doc)
        return True
    return False

def render_create_note_form(key_suffix, date_ref=None):
    recur_val = False
    stop_year_val = None
    if date_ref:
        col_type, col_recur = st.columns([2, 2])
        with col_type:
            note_type = st.radio("Type:", ["Text", "Drawing"], horizontal=True, key=f"nt_{key_suffix}")
        with col_recur:
            recur_val = st.checkbox("Repeat every year (Annual)", key=f"rec_{key_suffix}")
            if recur_val:
                stop_year_val = st.number_input("Stop after year", min_value=2025, max_value=2124, value=None, key=f"sy_{key_suffix}")
    else:
        note_type = st.radio("Type:", ["Text", "Drawing"], horizontal=True, key=f"nt_{key_suffix}")

    if note_type == "Text":
        with st.form(f"form_{key_suffix}", clear_on_submit=True):
            c_tit, c_lab = st.columns([2, 1])
            with c_tit: title = st.text_input("Title (Optional)")
            with c_lab: labels = st.text_input("Labels")
            content = st_quill(placeholder="Write here...", html=True, toolbar=toolbar_config)
            
            # COMPACT FILE UPLOAD ROW
            c_file, c_btn = st.columns([2, 1])
            with c_file:
                f_up = st.file_uploader("File", type=['pdf', 'docx', 'txt', 'mp3', 'wav', 'jpg', 'png'], label_visibility="collapsed")
            with c_btn:
                submitted = st.form_submit_button("Save Note")
            
            if submitted:
                if logic_save_note(title, labels, content, f_up, "Text", None, date_ref, recur_val, stop_year_val):
                    st.toast("Saved!", icon="✅")
                    if not date_ref:
                        st.session_state.create_key = str(uuid.uuid4())
                        st.session_state.reset_counter += 1
                    else:
                        st.session_state.cal_create_date = None
                    st.rerun()
                else:
                    st.warning("Empty note not saved.")
    else:
        c_t, c_l = st.columns([2, 1])
        with c_t: title = st.text_input("Title (Optional)", key=f"dt_{key_suffix}")
        with c_l: labels = st.text_input("Labels", key=f"dl_{key_suffix}")
        
        c_w, c_h, c_preset = st.columns([2, 2, 1])
        cw = c_w.slider("Width", 200, 1000, st.session_state.canvas_w, key=f"cw_{key_suffix}")
        ch = c_h.slider("Height", 200, 1000, st.session_state.canvas_h, key=f"ch_{key_suffix}")
        with c_preset:
            st.write("") 
            st.write("") 
            if st.button("📱 Phone", key=f"mb_{key_suffix}"):
                st.session_state.canvas_w = 340
                st.session_state.canvas_h = 500
                st.rerun()

        c1, c2, c3 = st.columns([1, 2, 1])
        with c1:
            st.markdown("<b>Set colour</b>", unsafe_allow_html=True)
            bc = st.color_picker("Color", "#000000", key=f"cc_{key_suffix}", label_visibility="collapsed")
        with c2:
            tl = st.radio("Tool", ["Pen", "Pencil", "Highlighter", "Eraser"], horizontal=True, key=f"tt_{key_suffix}")
        with c3:
            sw = st.slider("Width", 1, 30, 2, key=f"ss_{key_suffix}")
        if tl == "Eraser": bc = "#ffffff"
        fc = bc
        if tl == "Pencil": fc = hex_to_rgba(bc, 0.7); sw = 2 if sw > 5 else sw
        elif tl == "Highlighter": fc = hex_to_rgba(bc, 0.4); sw = 15 if sw < 10 else sw
        elif tl == "Eraser": sw = 20 if sw < 10 else sw
        
        ckey = f"cv_{cw}_{ch}_{key_suffix}"
        res = st_canvas(fill_color="rgba(0,0,0,0)", stroke_width=sw, stroke_color=fc, background_color="#FFF", update_streamlit=True, height=ch, width=cw, drawing_mode="freedraw", key=ckey)
        
        if st.button("Save Drawing", key=f"bs_{key_suffix}"):
            if logic_save_note(title, labels, None, None, "Drawing", res, date_ref, recur_val, stop_year_val):
                st.toast("Saved!", icon="✅")
                if not date_ref:
                    st.session_state.create_key = str(uuid.uuid4())
                    st.session_state.reset_counter += 1
                else:
                    st.session_state.cal_create_date = None
                st.rerun()
            else:
                st.warning("Empty drawing not saved.")

# --- 8. POPUPS ---

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
    st.write("**Statistics**")
    all_notes_stat = list(collection.find({}))
    total_count = len(all_notes_stat)
    dash_count = len([n for n in all_notes_stat if not n.get('calendar_date') and not n.get('deleted')])
    cal_count = len([n for n in all_notes_stat if n.get('calendar_date') and not n.get('deleted')])
    trash_count = len([n for n in all_notes_stat if n.get('deleted')])
    
    total_size_bytes = 0
    for n in all_notes_stat:
        total_size_bytes += len(str(n))
        if n.get("file_data"): total_size_bytes += len(n["file_data"])
    
    size_mb = total_size_bytes / (1024 * 1024)
    percentage = (size_mb / 512) * 100 
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Notes", total_count)
    c2.metric("Dashboard", dash_count)
    c3.metric("Calendar", cal_count)
    st.metric("Trash", trash_count)
    st.write(f"**Storage Used:** {size_mb:.2f} MB / 512 MB")
    st.progress(min(percentage / 100, 1.0))

    st.divider()
    st.write("**Data**")
    json_data = convert_notes_to_json(all_notes_stat)
    st.download_button("Download Backup (.json)", data=json_data, file_name=f"backup_{datetime.now().strftime('%Y%m%d')}.json", mime="application/json")
    
    uploaded_backup = st.file_uploader("Upload Backup (.json)", type=["json"])
    if uploaded_backup is not None:
        if st.button("Confirm Restore (Adds to DB)"):
            try:
                data = json.load(uploaded_backup)
                if isinstance(data, list):
                    for note in data:
                        if '_id' in note: del note['_id']
                        if 'data' in note and isinstance(note['data'], str):
                            try: note['data'] = datetime.strptime(note['data'], "%Y-%m-%d %H:%M:%S")
                            except: note['data'] = datetime.now()
                    if data:
                        collection.insert_many(data)
                        st.success(f"Restored {len(data)} notes!")
                        time.sleep(1)
                        st.rerun()
            except Exception as e:
                st.error(f"Error restoring: {e}")

    st.write("**Maintenance**")
    is_auto = st.toggle("Auto-delete items older than 30 days", value=st.session_state.auto_clean_enabled)
    if is_auto != st.session_state.auto_clean_enabled:
        st.session_state.auto_clean_enabled = is_auto
        if is_auto:
            limit = datetime.now() - timedelta(days=30)
            res = collection.delete_many({"deleted": True, "data": {"$lt": limit}})
            st.toast(f"Auto-cleaned {res.deleted_count} items")

@st.dialog("Edit Note", width="large")
def open_edit_popup(note_id, old_title, old_content, old_filename, old_labels, note_type, drawing_data=None, date_ref=None, is_default=False):
    st.markdown("### Edit Content")
    labels_str = ", ".join(old_labels) if old_labels else ""
    
    with st.form(key=f"edit_form_{note_id}"):
        c_t, c_l = st.columns([2, 1])
        with c_t: new_title = st.text_input("Title", value=old_title)
        with c_l: new_labels_str = st.text_input("Labels", value=labels_str)
        
        new_date_str = None
        if date_ref and not is_default:
            try:
                curr_date = datetime.strptime(date_ref, "%Y-%m-%d").date()
                new_date = st.date_input("Date (Move)", value=curr_date)
                new_date_str = str(new_date)
            except: pass

        safe_content = flatten_formulas_to_text(old_content)
        canvas_result = None
        new_file = None
        new_content = safe_content
        
        if note_type == "disegno":
            c_col, c_tool, c_width = st.columns([1, 2, 1])
            with c_col:
                st.markdown("<b>Set colour</b>", unsafe_allow_html=True)
                base_color = st.color_picker("Color", "#000000", key=f"d_c_{note_id}", label_visibility="collapsed")
            with c_tool:
                tool = st.radio("Tool", ["Pen", "Pencil", "Highlighter", "Eraser"], horizontal=True, key=f"d_t_{note_id}")
            with c_width:
                stroke_width = st.slider("Width", 1, 30, 2, key=f"d_w_{note_id}")
            if tool == "Eraser": base_color = "#ffffff"
            final_color = base_color
            if tool == "Pencil": final_color = hex_to_rgba(base_color, 0.7); stroke_width = 2 if stroke_width > 5 else stroke_width
            elif tool == "Highlighter": final_color = hex_to_rgba(base_color, 0.4); stroke_width = 15 if stroke_width < 10 else stroke_width
            elif tool == "Eraser": stroke_width = 20 if stroke_width < 10 else stroke_width
            
            init_draw = json.loads(drawing_data) if drawing_data else None
            canvas_result = st_canvas(fill_color="rgba(0,0,0,0)", stroke_width=stroke_width, stroke_color=final_color, background_color="#FFFFFF", initial_drawing=init_draw, update_streamlit=True, height=450, drawing_mode="freedraw", key=f"canvas_edit_{note_id}")
        else:
            unique_key = f"quill_edit_{note_id}_{st.session_state.edit_trigger}"
            new_content = st_quill(value=safe_content, toolbar=toolbar_config, html=True, key=unique_key)
            st.divider()
            # COMPACT UPLOAD IN EDIT
            c_file, c_space = st.columns([2, 1])
            with c_file:
                new_file = st.file_uploader("Replace File", type=['pdf', 'docx', 'txt', 'mp3', 'wav', 'jpg', 'png'], label_visibility="collapsed")

        if st.form_submit_button("Save Changes", type="primary"):
            labels_list = [tag.strip() for tag in new_labels_str.split(",") if tag.strip()]
            update_data = {"titolo": new_title, "labels": labels_list, "data": datetime.now()}
            
            if new_date_str: update_data["calendar_date"] = new_date_str

            if note_type == "disegno":
                if canvas_result.image_data is not None:
                    update_data["drawing_json"] = json.dumps(canvas_result.json_data)
                    img = Image.fromarray(canvas_result.image_data.astype('uint8'), 'RGBA')
                    buf = io.BytesIO()
                    img.save(buf, format='PNG')
                    val_bytes = buf.getvalue()
                    if len(val_bytes) > 0:
                        update_data["file_data"] = bson.binary.Binary(val_bytes)
                        update_data["file_name"] = "drawing.png"
            else:
                update_data["contenuto"] = new_content
                if new_file:
                    update_data["file_name"] = new_file.name
                    update_data["file_data"] = bson.binary.Binary(new_file.getvalue())
            
            collection.update_one({"_id": note_id}, {"$set": update_data})
            st.session_state.edit_trigger += 1 
            st.session_state.cal_edit_id = None
            st.session_state.cal_copy_id = None
            st.rerun()

    if old_filename and note_type != "disegno":
        st.info(f"Current file: **{old_filename}**")
        if st.button("Remove file", key=f"rm_file_{note_id}"):
            collection.update_one({"_id": note_id}, {"$set": {"file_name": None, "file_data": None}})
            st.rerun()

@st.dialog("Move Note", width="large")
def open_move_popup(current_note_id):
    st.write("Select the note you want to swap positions with:")
    candidates = list(collection.find({"deleted": {"$ne": True}, "_id": {"$ne": current_note_id}, "calendar_date": None}).sort("custom_order", 1))
    if not candidates: st.warning("No notes available."); return
    options = {n["_id"]: f"{'📌' if n.get('pinned') else '📄'} {n['titolo']}" for n in candidates}
    selected_target_id = st.selectbox("Swap with:", options.keys(), format_func=lambda x: options[x])
    
    c_swap, c_insert = st.columns(2)
    if c_swap.button("Swap Positions ⇄", use_container_width=True):
        n1 = collection.find_one({"_id": current_note_id})
        n2 = collection.find_one({"_id": selected_target_id})
        collection.update_one({"_id": current_note_id}, {"$set": {"custom_order": n2["custom_order"], "pinned": n2["pinned"]}})
        collection.update_one({"_id": selected_target_id}, {"$set": {"custom_order": n1["custom_order"], "pinned": n1["pinned"]}})
        st.rerun()
    if c_insert.button("Insert Before ⬆", use_container_width=True):
        n2 = collection.find_one({"_id": selected_target_id})
        t_order = n2["custom_order"]
        collection.update_one({"_id": current_note_id}, {"$set": {"custom_order": t_order, "pinned": n2["pinned"]}})
        collection.update_many({"custom_order": {"$gte": t_order}, "_id": {"$ne": current_note_id}, "calendar_date": None}, {"$inc": {"custom_order": 1}})
        st.rerun()

@st.dialog("Trash", width="large")
def open_trash():
    t_dash, t_cal = st.tabs(["Dashboard", "Calendar"])
    with t_dash:
        trash_notes = list(collection.find({"deleted": True, "calendar_date": None}).sort("data", -1))
        st.caption(f"{len(trash_notes)} deleted notes")
        if not trash_notes: st.info("Empty")
        else:
            if st.button("Empty Dashboard Trash"): collection.delete_many({"deleted": True, "calendar_date": None}); st.rerun()
            for note in trash_notes:
                with st.expander(f"🗑 {note.get('titolo') or 'Untitled'}"):
                    if note.get("tipo") == "disegno" and note.get("file_data"):
                        try: st.image(Image.open(io.BytesIO(note["file_data"])))
                        except: pass
                    else:
                        st.markdown(f"<div class='quill-read-content'>{process_content_for_display(note['contenuto'])}</div>", unsafe_allow_html=True)
                    c1, c2 = st.columns(2)
                    if c1.button("↺ Restore", key=f"rd_{note['_id']}"): collection.update_one({"_id": note['_id']}, {"$set": {"deleted": False}}); st.rerun()
                    if c2.button("✕ Delete", key=f"kd_{note['_id']}"): collection.delete_one({"_id": note['_id']}); st.rerun()
    with t_cal:
        trash_cal = list(collection.find({"deleted": True, "calendar_date": {"$ne": None}}).sort("data", -1))
        st.caption(f"{len(trash_cal)} deleted notes")
        if not trash_cal: st.info("Empty")
        else:
            if st.button("Empty Calendar Trash"): collection.delete_many({"deleted": True, "calendar_date": {"$ne": None}}); st.rerun()
            for note in trash_cal:
                date_label = note['calendar_date'] if note.get('calendar_date') else "Unknown"
                with st.expander(f"🗑 {date_label} - {note.get('titolo') or 'Untitled'}"):
                    if note.get("tipo") == "disegno" and note.get("file_data"):
                        try: st.image(Image.open(io.BytesIO(note["file_data"])))
                        except: pass
                    else:
                        st.markdown(f"<div class='quill-read-content'>{process_content_for_display(note['contenuto'])}</div>", unsafe_allow_html=True)
                    c1, c2 = st.columns(2)
                    if c1.button("↺ Restore", key=f"rc_{note['_id']}"): collection.update_one({"_id": note['_id']}, {"$set": {"deleted": False}}); st.rerun()
                    if c2.button("✕ Delete", key=f"kc_{note['_id']}"): collection.delete_one({"_id": note['_id']}); st.rerun()

@st.dialog("Confirmation")
def confirm_deletion(note_id):
    st.write("Move to trash?")
    c1, c2 = st.columns(2)
    if c1.button("Yes", type="primary"): collection.update_one({"_id": note_id}, {"$set": {"deleted": True}}); st.rerun()
    if c2.button("Cancel"): st.rerun()

# --- MAIN LAYOUT ---

head_col1, head_col2, head_col3 = st.columns([8, 1, 1])
with head_col1: st.markdown("<div class='dor-title'>DOR NOTES</div>", unsafe_allow_html=True)
with head_col2: 
    st.markdown("<div style='height: 15px;'></div>", unsafe_allow_html=True)
    if st.button("⚙", help="Settings"): open_settings()
with head_col3: 
    st.markdown("<div style='height: 15px;'></div>", unsafe_allow_html=True)
    if st.button("🗑", help="Trash"): open_trash()

st.markdown("---") 

# --- TABS ---
tab_dash, tab_cal = st.tabs(["DASHBOARD", "CALENDAR"])

# ================= DASHBOARD TAB =================
with tab_dash:
    expander_label = f"+ Create New Note{'\u200b' * st.session_state.reset_counter}"
    with st.expander(expander_label, expanded=False):
        render_create_note_form("dash_create") 

    st.write("")
    query = st.text_input("🔍", placeholder="Search in the Dashboard...", label_visibility="collapsed", key="dash_search")

    filter_query = {"deleted": {"$ne": True}, "calendar_date": None}
    if query:
        filter_query["$and"] = [
            {"deleted": {"$ne": True}},
            {"calendar_date": None},
            {"$or": [
                {"titolo": {"$regex": query, "$options": "i"}},
                {"contenuto": {"$regex": query, "$options": "i"}},
                {"labels": {"$regex": query, "$options": "i"}}
            ]}
        ]

    all_notes = list(collection.find(filter_query).sort("custom_order", 1)) 
    pinned_notes = [n for n in all_notes if n.get("pinned", False)]
    other_notes = [n for n in all_notes if not n.get("pinned", False)]

    def render_dash_grid(note_list):
        if not note_list: return
        num_cols = st.session_state.grid_cols
        cols = st.columns(num_cols)
        for index, note in enumerate(note_list):
            with cols[index % num_cols]: 
                icon_clip = "🖇️ " if note.get("file_name") else ""
                if note.get("tipo") == "disegno": icon_clip = "🎨 "
                labels = note.get("labels", [])
                icon_label = "🏷️ " if labels else ""
                
                title_disp = note['titolo'] if note['titolo'] else ""
                
                full_title = f"{icon_label}{icon_clip}{title_disp}"
                
                with st.expander(full_title):
                    if labels: st.markdown(render_badges(labels), unsafe_allow_html=True)
                    if note.get("tipo") == "disegno" and note.get("file_data") and len(note["file_data"]) > 0:
                        try: st.image(Image.open(io.BytesIO(note["file_data"])))
                        except: pass
                    else:
                        st.markdown(f"<div class='quill-read-content'>{process_content_for_display(note['contenuto'])}</div>", unsafe_allow_html=True)
                    
                    if note.get("file_name") and note.get("tipo") != "disegno":
                        st.markdown("---")
                        st.caption(f"File: {note['file_name']}")
                        st.download_button("Download", data=note["file_data"], file_name=note["file_name"], key=f"dl_{note['_id']}")
                    
                    st.markdown("---")
                    # DASHBOARD ACTIONS (4 IN A ROW - Mobile CSS Applied)
                    c1, c2, c3, c4 = st.columns(4)
                    
                    if c1.button("✎", key=f"m_{note['_id']}"):
                        draw_data = note.get("drawing_json", None)
                        open_edit_popup(note['_id'], note['titolo'], note['contenuto'], note.get("file_name"), labels, note.get("tipo"), draw_data)
                    
                    label_pin = "⚲"
                    if c2.button(label_pin, key=f"p_{note['_id']}"):
                         collection.update_one({"_id": note['_id']}, {"$set": {"pinned": not note.get("pinned", False)}})
                         st.rerun()
                    if c3.button("⇄", key=f"mv_{note['_id']}"): open_move_popup(note['_id'])
                    if c4.button("🗑", key=f"d_{note['_id']}"): confirm_deletion(note['_id'])

    if not all_notes: st.info("No dashboard notes.")
    else:
        if pinned_notes:
            st.markdown("<div class='section-header'>Pinned Notes</div>", unsafe_allow_html=True) 
            render_dash_grid(pinned_notes)
            st.write("") 
            st.markdown("<div class='section-header'>All Notes</div>", unsafe_allow_html=True) 
        render_dash_grid(other_notes)

# ================= CALENDAR TAB =================
with tab_cal:
    
    # SEARCH IN CALENDAR
    cal_query = st.text_input("🔍", placeholder="Search in the Calendar...", label_visibility="collapsed", key="cal_search")
    
    # MOBILE OPTIMIZED NAV: Row 1 (Month/Year), Row 2 (Prev/Next)
    c_sel_m, c_sel_y = st.columns(2)
    with c_sel_m:
        month_names = list(calendar.month_name)[1:]
        sel_month_name = st.selectbox("Month", month_names, index=st.session_state.cal_month-1, label_visibility="collapsed")
        new_month_idx = month_names.index(sel_month_name) + 1
        if new_month_idx != st.session_state.cal_month:
            st.session_state.cal_month = new_month_idx
            st.rerun()
    with c_sel_y:
        years = list(range(2025, 2125))
        try: y_idx = years.index(st.session_state.cal_year)
        except: y_idx = 0
        sel_year = st.selectbox("Year", years, index=y_idx, label_visibility="collapsed")
        if sel_year != st.session_state.cal_year:
            st.session_state.cal_year = sel_year
            st.rerun()
            
    c_prev, c_next = st.columns(2)
    with c_prev:
        if st.button("◀ Prev", use_container_width=True):
            st.session_state.cal_month -= 1
            if st.session_state.cal_month == 0:
                st.session_state.cal_month = 12
                st.session_state.cal_year -= 1
            st.rerun()
    with c_next:
        if st.button("Next ▶", use_container_width=True):
            st.session_state.cal_month += 1
            if st.session_state.cal_month == 13:
                st.session_state.cal_month = 1
                st.session_state.cal_year += 1
            st.rerun()

    st.markdown("<hr style='margin: 15px 0; border-top: 2px solid #888; opacity: 1;'>", unsafe_allow_html=True)

    num_days = calendar.monthrange(st.session_state.cal_year, st.session_state.cal_month)[1]
    
    start_date_str = f"{st.session_state.cal_year}-{st.session_state.cal_month:02d}-01"
    end_date_str = f"{st.session_state.cal_year}-{st.session_state.cal_month:02d}-{num_days}"
    
    q_reg = {"calendar_date": {"$gte": start_date_str, "$lte": end_date_str}, "deleted": {"$ne": True}}
    q_rec = {"deleted": {"$ne": True}, "recurrence": "yearly", "cal_month": st.session_state.cal_month, "$or": [{"recur_end_year": None}, {"recur_end_year": {"$gt": st.session_state.cal_year}}]}
    
    if cal_query:
        search_filter = {"$or": [
            {"titolo": {"$regex": cal_query, "$options": "i"}},
            {"contenuto": {"$regex": cal_query, "$options": "i"}},
            {"labels": {"$regex": cal_query, "$options": "i"}}
        ]}
        q_reg.update(search_filter)
        q_rec.update(search_filter)

    month_notes_reg = list(collection.find(q_reg))
    month_notes_rec = list(collection.find(q_rec))
    
    valid_recurring = []
    reg_ids = {str(n["_id"]) for n in month_notes_reg}
    for n in month_notes_rec:
        orig_date = datetime.strptime(n["calendar_date"], "%Y-%m-%d")
        if st.session_state.cal_year > orig_date.year: valid_recurring.append(n)
        elif str(n["_id"]) not in reg_ids: valid_recurring.append(n)

    all_cal_notes = month_notes_reg + valid_recurring
    
    notes_by_day = {}
    for n in all_cal_notes:
        if n.get("recurrence") == "yearly" and st.session_state.cal_year > datetime.strptime(n["calendar_date"], "%Y-%m-%d").year:
             d = f"{st.session_state.cal_year}-{st.session_state.cal_month:02d}-{n['cal_day']:02d}"
        else:
             d = n["calendar_date"]
        if d not in notes_by_day: notes_by_day[d] = []
        notes_by_day[d].append(n)
    
    for day in range(1, num_days + 1):
        date_str = f"{st.session_state.cal_year}-{st.session_state.cal_month:02d}-{day:02d}"
        dt = date(st.session_state.cal_year, st.session_state.cal_month, day)
        day_name = dt.strftime("%A, %d %B %Y")
        
        has_default = False
        if date_str in notes_by_day:
            for n in notes_by_day[date_str]:
                if n.get('titolo') == "Compiti del giorno" and n.get('is_default'):
                    has_default = True
                    break
        
        if not has_default and not cal_query: 
            def_doc = {
                "titolo": "Compiti del giorno",
                "contenuto": "",
                "labels": [],
                "data": datetime.now(),
                "custom_order": -1,
                "tipo": "testo_ricco",
                "deleted": False, "pinned": False,
                "calendar_date": date_str,
                "is_default": True
            }
            collection.insert_one(def_doc)
            if date_str not in notes_by_day: notes_by_day[date_str] = []
            notes_by_day[date_str].insert(0, def_doc)

        notes_today = notes_by_day.get(date_str, [])
        if cal_query and not notes_today: continue

        st.markdown(f"<div class='section-header'>{day_name}</div>", unsafe_allow_html=True) 
        
        notes_today.sort(key=lambda x: x.get('custom_order', 0))
        
        if notes_today:
            for note in notes_today:
                with st.container():
                    st.markdown(f"<div class='cal-note-container'>", unsafe_allow_html=True)
                    
                    title_txt = note.get('titolo') if note.get('titolo') else ""
                    icon_art = "🎨 " if note.get('tipo') == "disegno" else ""
                    
                    extra_icons = ""
                    if note.get("labels"): extra_icons += "🏷️ "
                    if note.get("file_name") and note.get("tipo") != "disegno": extra_icons += "🖇️ "
                    
                    st.markdown(f"**{extra_icons}{icon_art}{title_txt}**")
                    
                    if note.get("labels"): st.markdown(render_badges(note["labels"]), unsafe_allow_html=True)
                    if note.get("recurrence") == "yearly": st.caption("🔄 Annual")

                    if note.get("tipo") == "disegno" and note.get("file_data") and len(note["file_data"]) > 0:
                        try: st.image(Image.open(io.BytesIO(note["file_data"])))
                        except: pass
                    else:
                        st.markdown(f"<div class='quill-read-content'>{process_content_for_display(note['contenuto'])}</div>", unsafe_allow_html=True)
                    
                    if note.get("file_name") and note.get("tipo") != "disegno":
                        st.download_button("Download", data=note["file_data"], file_name=note["file_name"], key=f"dlc_{note['_id']}")
                    
                    # CALENDAR ACTIONS (Compact)
                    c1, c2, c3, c_space = st.columns([1, 1, 1, 6])
                    
                    if c1.button("✎", key=f"ced_{note['_id']}"): # Only Icon
                        draw_data = note.get("drawing_json", None)
                        open_edit_popup(note['_id'], note['titolo'], note['contenuto'], note.get("file_name"), note.get("labels", []), note.get("tipo"), draw_data, date_ref=date_str, is_default=note.get('is_default', False))
                    
                    if c2.button("❐", key=f"ccp_{note['_id']}"): # Only Icon
                        st.session_state.cal_copy_id = note['_id']
                        st.rerun()

                    if not note.get('is_default'):
                        if c3.button("🗑", key=f"cdel_{note['_id']}"): # Only Icon
                            confirm_deletion(note['_id'])
                    
                    if st.session_state.cal_copy_id == note['_id']:
                        with st.container():
                            st.info("Copy to:")
                            col_d, col_b = st.columns([2, 1])
                            copy_dest_date = col_d.date_input("Target", value=dt, key=f"cdi_{note['_id']}")
                            if col_b.button("Confirm", key=f"cb_{note['_id']}"):
                                new_doc = note.copy()
                                del new_doc['_id']
                                new_doc['calendar_date'] = str(copy_dest_date)
                                new_doc['data'] = datetime.now()
                                if new_doc.get('is_default'):
                                    new_doc['is_default'] = False
                                    new_doc['titolo'] = f"Copy of {new_doc['titolo']}"
                                collection.insert_one(new_doc)
                                st.session_state.cal_copy_id = None
                                st.success("Copied!")
                                time.sleep(0.5)
                                st.rerun()

                    st.markdown("</div>", unsafe_allow_html=True)
        
        c_add, c_empty = st.columns([1, 4])
        if st.session_state.cal_create_date == date_str:
            with st.container():
                st.markdown(f"**New Note for {day:02d}**")
                render_create_note_form(f"ic_{date_str}", date_str)
                if st.button("Cancel", key=f"cc_{date_str}"):
                    st.session_state.cal_create_date = None
                    st.rerun()
        else:
            with c_add:
                if st.button("+ Add Note", key=f"add_{date_str}"):
                    st.session_state.cal_create_date = date_str
                    st.rerun()
        
        st.markdown("<hr style='margin: 15px 0; border-top: 2px solid #888; opacity: 1;'>", unsafe_allow_html=True)
