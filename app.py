import streamlit as st
import pymongo
from datetime import datetime, timedelta
from streamlit_quill import st_quill
import time
import uuid
import bson.binary
import json

# --- 1. CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="DBJ Notes", page_icon="📝", layout="wide")

# --- 2. GESTIONE STATO & PREFERENZE ---
if 'text_size' not in st.session_state: st.session_state.text_size = "16px" # Default

# --- 3. CSS DINAMICO ---
st.markdown(f"""
<style>
    /* TITOLO MINIMAL */
    .minimal-title {{
        font-family: 'Helvetica', sans-serif;
        font-weight: 800;
        font-size: 2.5rem;
        color: #1a1a1a;
        text-align: center;
        margin-top: -10px;
    }}

    /* EXPANDER STYLE */
    .streamlit-expanderHeader {{
        font-weight: bold;
        font-size: 1.1rem;
        color: #333;
        background-color: #fff;
        border-radius: 5px;
    }}
    .streamlit-expanderContent {{
        border-top: 1px solid #f0f0f0;
        font-size: {st.session_state.text_size}; /* Dimensione Dinamica */
    }}
    
    /* Contenuto Quill (Lettura) */
    .quill-read-content {{
        font-size: {st.session_state.text_size} !important;
    }}

    /* INPUTS FOCUS */
    .stTextInput > div > div > input:focus {{
        border-color: #333 !important;
        box-shadow: 0 0 0 1px #333 !important;
    }}
    
    /* ANIMAZIONE LOGO */
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

# --- 4. INIT & CONNESSIONE DB ---
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

# --- 5. FUNZIONI UTILITÀ (Backup) ---
def converti_note_per_json(note_list):
    # Converte i dati MongoDB (ObjectId, DateTime) in stringhe per il JSON
    export_list = []
    for nota in note_list:
        nota_export = nota.copy()
        nota_export['_id'] = str(nota['_id'])
        nota_export['data'] = nota['data'].strftime("%Y-%m-%d %H:%M:%S")
        if 'file_data' in nota_export: del nota_export['file_data'] # Non esportiamo i binari nel JSON testo
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

# --- 7. DIALOGHI (POPUP) ---

# Popup Impostazioni (COMPLETO)
@st.dialog("Impostazioni ⚙️")
def apri_impostazioni():
    st.subheader("🛠️ Gestione Dati")
    
    # 1. BACKUP
    st.write("**Backup Note**")
    tutte_le_note = list(collection.find({}))
    json_dati = converti_note_per_json(tutte_le_note)
    st.download_button(
        label="⬇️ Scarica Backup Completo (.json)",
        data=json_dati,
        file_name=f"backup_dbjnotes_{datetime.now().strftime('%Y%m%d')}.json",
        mime="application/json"
    )
    
    st.divider()
    
    # 2. DIMENSIONE TESTO
    st.write("**Accessibilità**")
    size_opt = st.select_slider("Dimensione Testo Note", options=["14px", "16px", "18px", "20px", "24px"], value=st.session_state.text_size)
    if size_opt != st.session_state.text_size:
        st.session_state.text_size = size_opt
        st.rerun()
        
    st.divider()
    
    # 3. PULIZIA AUTOMATICA
    st.write("**Manutenzione**")
    if st.button("🧹 Elimina dal cestino note più vecchie di 30 giorni"):
        data_limite = datetime.now() - timedelta(days=30)
        result = collection.delete_many({
            "deleted": True,
            "data": {"$lt": data_limite}
        })
        st.success(f"Eliminate {result.deleted_count} note vecchie.")

# Popup Modifica
@st.dialog("Modifica Nota", width="large")
def apri_popup_modifica(nota_id, titolo_vecchio, contenuto_vecchio):
    st.markdown("### Modifica contenuto")
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

# --- BARRA STRUMENTI ---
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
                    "pinned": False, # Campo per il Fissaggio in alto
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

# --- GRIGLIA NOTE ---
filtro = {"deleted": {"$ne": True}}
if query:
    filtro = {"$and": [{"deleted": {"$ne": True}}, {"$or": [{"titolo": {"$regex": query, "$options": "i"}}, {"contenuto": {"$regex": query, "$options": "i"}}]}]}

# ORDINAMENTO: Prima le Pinned (True > False), poi per Data (Recente > Vecchia)
note_attive = list(collection.find(filtro).sort([("pinned", -1), ("data", -1)]))

if not note_attive:
    st.info("Nessuna nota.")
else:
    cols = st.columns(3)
    for index, nota in enumerate(note_attive):
        with cols[index % 3]:
            # Gestione Icone Titolo
            icona_clip = "📎 " if nota.get("file_name") else ""
            is_pinned = nota.get("pinned", False)
            icona_pin = "📌 " if is_pinned else ""
            
            # Tendina Nota
            with st.expander(f"{icona_pin}{icona_clip}📄 {nota['titolo']}"):
                
                # TASTO FISSAGGIO (PIN) IN EVIDENZA
                col_pin, _ = st.columns([1, 3])
                label_pin = "Sblocca" if is_pinned else "📌 Fissa in alto"
                if col_pin.button(label_pin, key=f"pin_{nota['_id']}", help="Metti in cima alla lista"):
                    new_state = not is_pinned
                    collection.update_one({"_id": nota['_id']}, {"$set": {"pinned": new_state}})
                    st.rerun()

                # Contenuto (con classe CSS per dimensione font)
                st.markdown(f"<div class='quill-read-content'>{nota['contenuto']}</div>", unsafe_allow_html=True)
                
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
