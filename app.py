import streamlit as st
import pymongo
from datetime import datetime
from streamlit_quill import st_quill
import time
import uuid

# --- 1. CONFIGURAZIONE ---
st.set_page_config(page_title="DBJ Notes", page_icon="📝", layout="wide")

# --- 2. CSS AVANZATO (Fix Rosso + Dimensioni) ---
st.markdown("""
<style>
    /* FIX BORDI ROSSI: Forza il colore grigio scuro/nero al focus */
    .stTextInput > div > div > input:focus {
        border-color: #333 !important;
        box-shadow: 0 0 0 1px #333 !important;
    }
    .stTextArea > div > div > textarea:focus {
        border-color: #333 !important;
        box-shadow: 0 0 0 1px #333 !important;
    }
    /* Rimuove bordo rosso anche dal box di ricerca se presente */
    [data-testid="stHeader"] {
        background-color: rgba(0,0,0,0);
    }

    /* TITOLO APP RIDIMENSIONATO */
    .minimal-title {
        font-family: 'Helvetica', sans-serif;
        font-weight: 800;
        font-size: 2.5rem; /* Molto più piccolo di prima */
        color: #1a1a1a;
        text-align: center;
        margin-bottom: 5px;
        margin-top: -10px;
    }

    /* Override dimensioni titoli di Streamlit (H2, H3) */
    h1, h2, h3 {
        font-family: 'Helvetica', sans-serif !important;
        font-weight: 600 !important;
    }
    h3 {
        font-size: 1.1rem !important; /* Titoli note più piccoli */
    }
    
    /* Stile per il bottone che sembra un titolo (Click to Edit) */
    .stButton button {
        border: none;
        background: transparent;
        color: #000;
        text-align: left;
        font-weight: bold;
        font-size: 18px;
        padding: 0;
    }
    .stButton button:hover {
        color: #4A90E2; /* Diventa blu quando ci passi sopra */
        background: transparent;
        border: none;
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

# --- 3. GESTIONE STATO ---
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

# --- TOOLBAR EDITOR ---
toolbar_full = [
    ['bold', 'italic', 'underline', 'strike'],
    [{ 'header': [1, 2, 3, False] }],
    [{ 'list': 'ordered'}, { 'list': 'bullet' }],
    [{ 'color': [] }, { 'background': [] }],
    [{ 'align': [] }],
    ['link', 'image', 'formula'],
    ['clean']
]

# --- DIALOGHI (POPUP) ---

# 1. Popup Modifica (Occupa spazio come richiesto)
@st.dialog("Modifica Nota", width="large")
def apri_popup_modifica(nota_id, titolo_vecchio, contenuto_vecchio):
    st.markdown("### Modifica contenuto")
    nuovo_titolo = st.text_input("Titolo", value=titolo_vecchio)
    # Editor grande
    nuovo_contenuto = st_quill(value=contenuto_vecchio, toolbar=toolbar_full, html=True, key=f"edit_{nota_id}")
    
    col_save, col_del = st.columns([4, 1])
    if col_save.button("💾 Salva Modifiche", type="primary"):
        collection.update_one(
            {"_id": nota_id},
            {"$set": {"titolo": nuovo_titolo, "contenuto": nuovo_contenuto, "data": datetime.now()}}
        )
        st.rerun()
    
    # Possibilità di eliminare direttamente dalla modifica
    if col_del.button("🗑️ Elimina"):
         collection.update_one({"_id": nota_id}, {"$set": {"deleted": True}})
         st.rerun()

# 2. Popup Cestino (Funziona come una cartella separata)
@st.dialog("Cestino 🗑️", width="large")
def apri_cestino():
    note_cestino = list(collection.find({"deleted": True}).sort("data", -1))
    
    col_head1, col_head2 = st.columns([3, 1])
    col_head1.write(f"Note nel cestino: {len(note_cestino)}")
    
    if note_cestino:
        if col_head2.button("🔥 Svuota tutto"):
            collection.delete_many({"deleted": True})
            st.rerun()
        
        st.divider()
        for nota in note_cestino:
            c1, c2, c3 = st.columns([4, 1, 1])
            c1.markdown(f"**{nota['titolo']}**")
            if c2.button("♻️", key=f"rest_{nota['_id']}", help="Ripristina"):
                collection.update_one({"_id": nota['_id']}, {"$set": {"deleted": False}})
                st.rerun()
            if c3.button("❌", key=f"kill_{nota['_id']}", help="Elimina per sempre"):
                collection.delete_one({"_id": nota['_id']})
                st.rerun()
    else:
        st.info("Il cestino è vuoto.")

# --- INTERFACCIA PRINCIPALE ---

st.markdown("<div class='minimal-title'>DBJ Notes</div>", unsafe_allow_html=True)

# --- BARRA SUPERIORE: CREA (Tendina) + CESTINO (Bottone) ---
col_crea, col_trash = st.columns([20, 1]) # Proporzione: Crea occupa quasi tutto, Cestino piccolo a destra

with col_crea:
    with st.expander("✍️ Crea nuova nota"):
        # Chiave dinamica per svuotare l'input
        titolo_input = st.text_input("Titolo", key=f"tit_{st.session_state.editor_key}")
        contenuto_input = st_quill(
            placeholder="Scrivi qui...",
            html=True,
            toolbar=toolbar_full,
            key=f"quill_{st.session_state.editor_key}"
        )
        if st.button("Salva Nota 💾"):
            if titolo_input and contenuto_input:
                collection.insert_one({
                    "titolo": titolo_input,
                    "contenuto": contenuto_input,
                    "data": datetime.now(),
                    "tipo": "testo_ricco",
                    "deleted": False
                })
                st.toast("Salvata!", icon="✅")
                st.session_state.editor_key = str(uuid.uuid4()) # Reset
                time.sleep(0.5)
                st.rerun()
            else:
                st.warning("Manca titolo o testo.")

with col_trash:
    # Il bottone cestino è allineato a destra
    st.write("") # Spaziatore per allineare verticalmente
    if st.button("🗑️", help="Apri Cestino"):
        apri_cestino()

st.divider()

# --- RICERCA ---
query = st.text_input("🔍 Cerca...", placeholder="Cerca parole chiave...", label_visibility="collapsed")

# --- GRIGLIA NOTE ---
filtro = {"deleted": {"$ne": True}}
if query:
    filtro = {"$and": [{"deleted": {"$ne": True}}, {"$or": [{"titolo": {"$regex": query, "$options": "i"}}, {"contenuto": {"$regex": query, "$options": "i"}}]}]}

note_attive = list(collection.find(filtro).sort("data", -1))

if not note_attive:
    st.info("Nessuna nota. Creane una sopra!")
else:
    cols = st.columns(3)
    for index, nota in enumerate(note_attive):
        with cols[index % 3]:
            with st.container(border=True):
                # TRUCCO: Usiamo un bottone che sembra un titolo per aprire la modifica
                # use_container_width=True rende il bottone largo quanto la card
                if st.button(f"📝 {nota['titolo']}", key=f"open_{nota['_id']}", use_container_width=True):
                    apri_popup_modifica(nota['_id'], nota['titolo'], nota['contenuto'])
                
                # Anteprima contenuto (piccola)
                st.markdown(nota['contenuto'][:100] + "..." if len(nota['contenuto']) > 100 else nota['contenuto'], unsafe_allow_html=True)
                
                # Data piccola in basso
                st.caption(nota['data'].strftime("%d/%m %H:%M"))
