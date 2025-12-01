import streamlit as st
import pymongo
from datetime import datetime
from streamlit_quill import st_quill
import time
import uuid
import bson.binary # Per gestire i file nel database

# --- 1. CONFIGURAZIONE ---
st.set_page_config(page_title="DBJ Notes", page_icon="📝", layout="wide")

# --- 2. CSS AVANZATO (Design & Fix) ---
st.markdown("""
<style>
    /* Focus Inputs: Grigio Scuro/Nero */
    .stTextInput > div > div > input:focus {
        border-color: #333 !important;
        box-shadow: 0 0 0 1px #333 !important;
    }
    .stTextArea > div > div > textarea:focus {
        border-color: #333 !important;
        box-shadow: 0 0 0 1px #333 !important;
    }
    
    /* Titolo Minimal */
    .minimal-title {
        font-family: 'Helvetica', sans-serif;
        font-weight: 800;
        font-size: 2.5rem;
        color: #1a1a1a;
        text-align: center;
        margin-top: -10px;
    }

    /* Expander style personalizzato */
    .streamlit-expanderHeader {
        font-weight: bold;
        font-size: 1.1rem;
        color: #333;
    }

    /* Animazione Logo */
    @keyframes pulse-logo {
        0% { transform: scale(1); opacity: 0.6; }
        50% { transform: scale(1.05); opacity: 1; }
        100% { transform: scale(1); opacity: 0.6; }
    }
    .splash-logo {
        font-size: 60px;
        text-align: center;
        animation: pulse-logo 1.2s infinite;
        margin-top: 20vh;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. ANIMAZIONE & STATO ---
if 'first_load' not in st.session_state:
    placeholder = st.empty()
    with placeholder.container():
        st.markdown("<div class='splash-logo'>📝</div>", unsafe_allow_html=True)
        st.markdown("<h1 style='text-align: center; font-size: 2rem;'>DBJ Notes</h1>", unsafe_allow_html=True)
        time.sleep(1.2)
    placeholder.empty()
    st.session_state['first_load'] = True

if 'editor_key' not in st.session_state:
    st.session_state.editor_key = str(uuid.uuid4())

# --- CONNESSIONE DB ---
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

# --- TOOLBAR EDITOR (Pulita: No Link, No Tx) ---
toolbar_config = [
    ['bold', 'italic', 'underline', 'strike'],
    [{ 'header': [1, 2, 3, False] }],
    [{ 'list': 'ordered'}, { 'list': 'bullet' }],
    [{ 'color': [] }, { 'background': [] }],
    [{ 'align': [] }],
    ['image', 'formula'], # Manteniamo immagine per il drag&drop visivo
]

# --- DIALOGHI (POPUP) ---

# 1. Popup Modifica
@st.dialog("Modifica Nota", width="large")
def apri_popup_modifica(nota_id, titolo_vecchio, contenuto_vecchio):
    st.markdown("### Modifica testo")
    nuovo_titolo = st.text_input("Titolo", value=titolo_vecchio)
    nuovo_contenuto = st_quill(value=contenuto_vecchio, toolbar=toolbar_config, html=True, key=f"edit_{nota_id}")
    
    # Nota: La modifica degli allegati è complessa, per ora permettiamo di modificare testo e titolo
    if st.button("💾 Salva Modifiche", type="primary"):
        collection.update_one(
            {"_id": nota_id},
            {"$set": {"titolo": nuovo_titolo, "contenuto": nuovo_contenuto, "data": datetime.now()}}
        )
        st.rerun()

# 2. Popup Conferma Eliminazione (RIPRISTINATO)
@st.dialog("⚠️ Conferma Eliminazione")
def conferma_eliminazione(nota_id):
    st.write("Vuoi davvero spostare questa nota nel cestino?")
    col_si, col_no = st.columns(2)
    if col_si.button("Sì, elimina", type="primary"):
        collection.update_one({"_id": nota_id}, {"$set": {"deleted": True}})
        st.rerun()
    if col_no.button("Annulla"):
        st.rerun()

# 3. Popup Cestino
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
        st.info("Cestino vuoto.")

# --- INTERFACCIA PRINCIPALE ---

st.markdown("<div class='minimal-title'>DBJ Notes</div>", unsafe_allow_html=True)

# --- BARRA SUPERIORE ---
col_crea, col_trash = st.columns([20, 1])

with col_crea:
    with st.expander("✍️ Crea nuova nota"):
        # Input Titolo
        titolo_input = st.text_input("Titolo", key=f"tit_{st.session_state.editor_key}")
        
        # Editor Testo
        contenuto_input = st_quill(
            placeholder="Scrivi qui...",
            html=True,
            toolbar=toolbar_config,
            key=f"quill_{st.session_state.editor_key}"
        )
        
        # AREA ALLEGATI (Nuova feature richiesta)
        st.markdown("---")
        st.markdown("**📎 Allegati (PDF, Audio, Word)**")
        uploaded_file = st.file_uploader("Carica un file", type=['pdf', 'docx', 'txt', 'mp3', 'wav', 'jpg', 'png'], key=f"file_{st.session_state.editor_key}")
        
        if st.button("Salva Nota 💾"):
            if titolo_input and contenuto_input:
                # Creazione documento
                doc = {
                    "titolo": titolo_input,
                    "contenuto": contenuto_input,
                    "data": datetime.now(),
                    "tipo": "testo_ricco",
                    "deleted": False,
                    "file_name": None,
                    "file_data": None
                }
                
                # Gestione salvataggio file (se presente)
                if uploaded_file is not None:
                    doc["file_name"] = uploaded_file.name
                    # Convertiamo in binario per MongoDB
                    doc["file_data"] = bson.binary.Binary(uploaded_file.getvalue())
                
                collection.insert_one(doc)
                st.toast("Salvata!", icon="✅")
                st.session_state.editor_key = str(uuid.uuid4()) # Reset completo
                time.sleep(0.5)
                st.rerun()
            else:
                st.warning("Titolo e contenuto sono obbligatori.")

with col_trash:
    st.write("")
    if st.button("🗑️", help="Cestino"):
        apri_cestino()

st.divider()

# --- RICERCA ---
query = st.text_input("🔍 Cerca...", label_visibility="collapsed", placeholder="Cerca nota...")

# --- GRIGLIA DI TENDINE ---
filtro = {"deleted": {"$ne": True}}
if query:
    filtro = {"$and": [{"deleted": {"$ne": True}}, {"$or": [{"titolo": {"$regex": query, "$options": "i"}}, {"contenuto": {"$regex": query, "$options": "i"}}]}]}

note_attive = list(collection.find(filtro).sort("data", -1))

if not note_attive:
    st.info("Nessuna nota attiva.")
else:
    cols = st.columns(3) # Griglia a 3 colonne
    for index, nota in enumerate(note_attive):
        with cols[index % 3]:
            # Qui usiamo un EXPANDER per ogni nota (Tendina)
            # L'etichetta dell'expander è il titolo della nota
            icona_clip = "📎 " if "file_name" in nota and nota["file_name"] else ""
            
            with st.expander(f"{icona_clip}📄 {nota['titolo']}"):
                
                # 1. Mostra il contenuto completo
                st.markdown(nota['contenuto'], unsafe_allow_html=True)
                
                # 2. Se c'è un allegato, mostra il bottone download
                if "file_name" in nota and nota["file_name"]:
                    st.markdown("---")
                    st.caption(f"Allegato: {nota['file_name']}")
                    st.download_button(
                        label="⬇️ Scarica File",
                        data=nota["file_data"],
                        file_name=nota["file_name"]
                    )
                
                st.markdown("---")
                # 3. Pulsanti Azione (Modifica / Elimina)
                b1, b2 = st.columns(2)
                
                if b1.button("✏️ Modifica", key=f"mod_{nota['_id']}"):
                    apri_popup_modifica(nota['_id'], nota['titolo'], nota['contenuto'])
                
                if b2.button("🗑️ Elimina", key=f"del_{nota['_id']}"):
                    # Apre il popup di conferma
                    conferma_eliminazione(nota['_id'])
