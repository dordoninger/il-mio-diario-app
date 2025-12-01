import streamlit as st
import pymongo
from datetime import datetime
from streamlit_quill import st_quill
import time
import uuid
import bson.binary

# --- 1. CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="DBJ Notes", page_icon="📝", layout="wide")

# --- 2. GESTIONE STATO IMPOSTAZIONI (Default) ---
if 'settings_bg_color' not in st.session_state: st.session_state.settings_bg_color = "#f0f2f6" # Grigio chiaro default
if 'settings_note_color' not in st.session_state: st.session_state.settings_note_color = "#ffffff" # Bianco default
if 'settings_text_color' not in st.session_state: st.session_state.settings_text_color = "#000000" # Nero default

# --- 3. CSS DINAMICO (Applica i colori scelti) ---
st.markdown(f"""
<style>
    /* Applica colore di sfondo all'intera app */
    .stApp {{
        background-color: {st.session_state.settings_bg_color};
    }}
    
    /* Stile per le note (Expander) */
    .streamlit-expanderContent {{
        background-color: {st.session_state.settings_note_color};
        color: {st.session_state.settings_text_color};
        border-radius: 0 0 10px 10px;
    }}
    .streamlit-expanderHeader {{
        background-color: {st.session_state.settings_note_color};
        color: {st.session_state.settings_text_color} !important;
        border-radius: 10px;
        font-weight: bold;
    }}
    
    /* Titolo Minimal */
    .minimal-title {{
        font-family: 'Helvetica', sans-serif;
        font-weight: 800;
        font-size: 2.5rem;
        color: {st.session_state.settings_text_color};
        text-align: center;
        margin-top: -10px;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.1);
    }}

    /* Focus Inputs */
    .stTextInput > div > div > input:focus {{
        border-color: #333 !important;
        box-shadow: 0 0 0 1px #333 !important;
    }}
    
    /* Animazione Logo */
    @keyframes pulse-logo {{
        0% {{ transform: scale(1); opacity: 0.6; }}
        50% {{ transform: scale(1.05); opacity: 1; }}
        100% {{ transform: scale(1); opacity: 0.6; }}
    }}
    .splash-logo {{
        font-size: 60px;
        text-align: center;
        animation: pulse-logo 1.2s infinite;
        margin-top: 20vh;
    }}
</style>
""", unsafe_allow_html=True)

# --- 4. INIT E CONNESSIONE DB ---
if 'first_load' not in st.session_state:
    placeholder = st.empty()
    with placeholder.container():
        st.markdown("<div class='splash-logo'>📝</div>", unsafe_allow_html=True)
        st.markdown(f"<h1 style='text-align: center; font-size: 2rem; color: #333;'>DBJ Notes</h1>", unsafe_allow_html=True)
        time.sleep(1.2)
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

# --- 5. TOOLBAR EDITOR (Aggiornata con Apici/Pedici/Latex) ---
toolbar_config = [
    ['bold', 'italic', 'underline', 'strike'],
    [{ 'header': [1, 2, 3, False] }],
    [{ 'list': 'ordered'}, { 'list': 'bullet' }],
    [{ 'script': 'sub'}, { 'script': 'super' }], # <--- ECCO APICI E PEDICI
    [{ 'color': [] }, { 'background': [] }],
    [{ 'align': [] }],
    ['image', 'formula'], # <--- ECCO LA FORMULA LATEX
]

# --- 6. DIALOGHI (POPUP) ---

# Popup Impostazioni
@st.dialog("Impostazioni ⚙️")
def apri_impostazioni():
    st.subheader("Personalizzazione Colori")
    
    # Selettori Colore
    col_bg = st.color_picker("Sfondo Pagina", value=st.session_state.settings_bg_color)
    col_note = st.color_picker("Sfondo Note", value=st.session_state.settings_note_color)
    col_text = st.color_picker("Colore Testo Principale", value=st.session_state.settings_text_color)
    
    st.divider()
    st.write("Preset veloci:")
    c1, c2 = st.columns(2)
    if c1.button("☀️ Tema Chiaro"):
        st.session_state.settings_bg_color = "#f0f2f6"
        st.session_state.settings_note_color = "#ffffff"
        st.session_state.settings_text_color = "#000000"
        st.rerun()
    if c2.button("🌙 Tema Scuro"):
        st.session_state.settings_bg_color = "#1e1e1e"
        st.session_state.settings_note_color = "#2d2d2d"
        st.session_state.settings_text_color = "#e0e0e0"
        st.rerun()
        
    if st.button("💾 Applica Personalizzati", type="primary"):
        st.session_state.settings_bg_color = col_bg
        st.session_state.settings_note_color = col_note
        st.session_state.settings_text_color = col_text
        st.rerun()

# Popup Modifica
@st.dialog("Modifica Nota", width="large")
def apri_popup_modifica(nota_id, titolo_vecchio, contenuto_vecchio):
    st.markdown("### Modifica testo")
    nuovo_titolo = st.text_input("Titolo", value=titolo_vecchio)
    nuovo_contenuto = st_quill(value=contenuto_vecchio, toolbar=toolbar_config, html=True, key=f"edit_{nota_id}")
    
    if st.button("💾 Salva Modifiche", type="primary"):
        collection.update_one(
            {"_id": nota_id},
            {"$set": {"titolo": nuovo_titolo, "contenuto": nuovo_contenuto, "data": datetime.now()}}
        )
        st.rerun()

# Popup Cestino
@st.dialog("Cestino 🗑️", width="large")
def apri_cestino():
    note_cestino = list(collection.find({"deleted": True}).sort("data", -1))
    col1, col2 = st.columns([3, 1])
    col1.write(f"Note eliminate: {len(note_cestino)}")
    if note_cestino:
        if col2.button("🔥 Svuota tutto"):
            collection.delete_many({"deleted": True})
            st.rerun()
        st.divider()
        for nota in note_cestino:
            c1, c2, c3 = st.columns([4, 1, 1])
            c1.markdown(f"**{nota['titolo']}**")
            if c2.button("♻️", key=f"rest_{nota['_id']}"):
                collection.update_one({"_id": nota['_id']}, {"$set": {"deleted": False}})
                st.rerun()
            if c3.button("❌", key=f"kill_{nota['_id']}"):
                collection.delete_one({"_id": nota['_id']})
                st.rerun()
    else:
        st.info("Vuoto.")

# Popup Conferma Eliminazione
@st.dialog("⚠️ Conferma Eliminazione")
def conferma_eliminazione(nota_id):
    st.write("Spostare nel cestino?")
    c1, c2 = st.columns(2)
    if c1.button("Sì, elimina", type="primary"):
        collection.update_one({"_id": nota_id}, {"$set": {"deleted": True}})
        st.rerun()
    if c2.button("Annulla"):
        st.rerun()

# --- INTERFACCIA PRINCIPALE ---

st.markdown("<div class='minimal-title'>DBJ Notes</div>", unsafe_allow_html=True)

# --- BARRA STRUMENTI: CREA | CESTINO | IMPOSTAZIONI ---
# Layout: Colonna grande per crea, due piccole per le icone
col_crea, col_trash, col_settings = st.columns([20, 1, 1])

with col_crea:
    with st.expander("✍️ Crea nuova nota"):
        titolo_input = st.text_input("Titolo", key=f"tit_{st.session_state.editor_key}")
        contenuto_input = st_quill(
            placeholder="Scrivi qui...",
            html=True,
            toolbar=toolbar_config,
            key=f"quill_{st.session_state.editor_key}"
        )
        st.markdown("---")
        st.markdown("**📎 Allegati**")
        uploaded_file = st.file_uploader("File", type=['pdf', 'docx', 'txt', 'mp3', 'wav', 'jpg', 'png'], key=f"file_{st.session_state.editor_key}")
        
        if st.button("Salva Nota 💾"):
            if titolo_input and contenuto_input:
                doc = {
                    "titolo": titolo_input,
                    "contenuto": contenuto_input,
                    "data": datetime.now(),
                    "tipo": "testo_ricco",
                    "deleted": False,
                    "file_name": uploaded_file.name if uploaded_file else None,
                    "file_data": bson.binary.Binary(uploaded_file.getvalue()) if uploaded_file else None
                }
                collection.insert_one(doc)
                st.toast("Salvata!", icon="✅")
                st.session_state.editor_key = str(uuid.uuid4())
                time.sleep(0.5)
                st.rerun()
            else:
                st.warning("Manca titolo o testo.")

with col_trash:
    st.write("")
    if st.button("🗑️", help="Cestino"):
        apri_cestino()

with col_settings:
    st.write("")
    if st.button("⚙️", help="Impostazioni"):
        apri_impostazioni()

st.divider()

# --- RICERCA ---
query = st.text_input("🔍", placeholder="Cerca nota...", label_visibility="collapsed")

# --- GRIGLIA NOTE (TENDINE) ---
filtro = {"deleted": {"$ne": True}}
if query:
    filtro = {"$and": [{"deleted": {"$ne": True}}, {"$or": [{"titolo": {"$regex": query, "$options": "i"}}, {"contenuto": {"$regex": query, "$options": "i"}}]}]}

note_attive = list(collection.find(filtro).sort("data", -1))

if not note_attive:
    st.info("Nessuna nota.")
else:
    cols = st.columns(3)
    for index, nota in enumerate(note_attive):
        with cols[index % 3]:
            # Icona graffetta se c'è file
            icona = "📎 " if note_attive[index].get("file_name") else ""
            
            with st.expander(f"{icona}📄 {nota['titolo']}"):
                st.markdown(nota['contenuto'], unsafe_allow_html=True)
                
                if nota.get("file_name"):
                    st.markdown("---")
                    st.caption(f"File: {nota['file_name']}")
                    st.download_button("⬇️ Scarica", data=nota["file_data"], file_name=nota["file_name"])
                
                st.markdown("---")
                b1, b2 = st.columns(2)
                if b1.button("✏️ Modifica", key=f"mod_{nota['_id']}"):
                    apri_popup_modifica(nota['_id'], nota['titolo'], nota['contenuto'])
                if b2.button("🗑️ Elimina", key=f"del_{nota['_id']}"):
                    conferma_eliminazione(nota['_id'])
