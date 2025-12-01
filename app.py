import streamlit as st
import pymongo
from datetime import datetime
from streamlit_quill import st_quill
import time
import uuid # Ci serve per generare chiavi univoche e "resettare" l'editor

# --- 1. CONFIGURAZIONE ---
st.set_page_config(page_title="DBJ Notes", page_icon="📝", layout="wide")

# --- 2. CSS & DESIGN PULITO ---
st.markdown("""
<style>
    /* Input e Textarea: Bordo nero/grigio scuro quando attivi */
    .stTextInput > div > div > input:focus {
        border-color: #333 !important;
        box-shadow: 0 0 0 1px #333 !important;
    }
    
    /* Titolo Minimal Black */
    .minimal-title {
        font-family: 'Arial', sans-serif; /* Font semplice e pulito */
        font-weight: 900;
        font-size: 4rem;
        color: #000000; /* Nero assoluto */
        text-align: center;
        letter-spacing: -2px; /* Lettere vicine per look moderno */
        margin-bottom: 10px;
        margin-top: -20px;
    }

    /* Card della Nota */
    .note-card {
        border: 1px solid #e0e0e0;
        border-radius: 12px;
        padding: 15px;
        background: white;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }

    /* Animazione Pulsazione (senza stelline) */
    @keyframes pulse-logo {
        0% { transform: scale(1); opacity: 0.5; }
        50% { transform: scale(1.1); opacity: 1; }
        100% { transform: scale(1); opacity: 0.5; }
    }
    .splash-logo {
        font-size: 80px;
        text-align: center;
        animation: pulse-logo 1.2s infinite;
        margin-top: 15vh;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. ANIMAZIONE INIZIALE (1.2 sec, niente stelline) ---
if 'first_load' not in st.session_state:
    placeholder = st.empty()
    with placeholder.container():
        st.markdown("<div class='splash-logo'>📝</div>", unsafe_allow_html=True)
        st.markdown("<h1 style='text-align: center; color: black;'>DBJ Notes</h1>", unsafe_allow_html=True)
        time.sleep(1.2)
    placeholder.empty()
    st.session_state['first_load'] = True

# --- 4. GESTIONE STATO PER RESET EDITOR ---
# Questo serve per svuotare "veramente" l'editor dopo il salvataggio
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
    ['blockquote', 'code-block'],
    [{ 'header': 1 }, { 'header': 2 }],
    [{ 'list': 'ordered'}, { 'list': 'bullet' }],
    [{ 'script': 'sub'}, { 'script': 'super' }],
    [{ 'indent': '-1'}, { 'indent': '+1' }],
    [{ 'direction': 'rtl' }],
    [{ 'size': ['small', False, 'large', 'huge'] }],
    [{ 'header': [1, 2, 3, 4, 5, 6, False] }],
    [{ 'color': [] }, { 'background': [] }],
    [{ 'font': [] }],
    [{ 'align': [] }],
    ['link', 'image', 'formula'],
    ['clean']
]

# --- DIALOGHI (POPUP) ---

# 1. Popup Modifica
@st.dialog("Modifica Nota")
def apri_popup_modifica(nota_id, titolo_vecchio, contenuto_vecchio):
    nuovo_titolo = st.text_input("Titolo", value=titolo_vecchio)
    nuovo_contenuto = st_quill(value=contenuto_vecchio, toolbar=toolbar_full, html=True, key=f"edit_{nota_id}")
    
    if st.button("💾 Salva Modifiche"):
        collection.update_one(
            {"_id": nota_id},
            {"$set": {"titolo": nuovo_titolo, "contenuto": nuovo_contenuto, "data": datetime.now()}}
        )
        st.rerun()

# 2. Popup Conferma Eliminazione (Sposta nel Cestino)
@st.dialog("⚠️ Attenzione")
def conferma_eliminazione(nota_id):
    st.write("Vuoi davvero eliminare questa nota? Finirà nel cestino.")
    col_si, col_no = st.columns(2)
    if col_si.button("Sì, elimina", type="primary"):
        # Soft Delete: non cancelliamo, ma mettiamo un flag "deleted": True
        collection.update_one({"_id": nota_id}, {"$set": {"deleted": True}})
        st.rerun()
    if col_no.button("No, annulla"):
        st.rerun()

# --- INTERFACCIA ---

# Titolo Nero Minimal
st.markdown("<div class='minimal-title'>DBJ Notes</div>", unsafe_allow_html=True)
st.divider()

# --- SEZIONE CREAZIONE (Auto-svuotante) ---
st.subheader("Nuova Nota")

with st.container(border=True):
    # Usiamo st.session_state.editor_key come chiave. 
    # Quando salviamo, cambiamo questa chiave e l'editor rinasce vuoto.
    titolo_input = st.text_input("Titolo Nota", key=f"tit_{st.session_state.editor_key}")
    contenuto_input = st_quill(
        placeholder="Scrivi qui...",
        html=True,
        toolbar=toolbar_full,
        key=f"quill_{st.session_state.editor_key}"
    )

    if st.button("Salva Nota 💾"):
        if titolo_input and contenuto_input:
            doc = {
                "titolo": titolo_input,
                "contenuto": contenuto_input,
                "data": datetime.now(),
                "tipo": "testo_ricco",
                "deleted": False # Importante per il cestino
            }
            collection.insert_one(doc)
            st.toast("Nota Salvata!", icon="✅")
            
            # IL TRUCCO DEL RESET: Generiamo una nuova chiave univoca
            st.session_state.editor_key = str(uuid.uuid4())
            time.sleep(0.5)
            st.rerun()
        else:
            st.warning("Scrivi titolo e contenuto per salvare.")

st.divider()

# --- SEZIONE VISUALIZZAZIONE (Solo note NON cancellate) ---
c_search, _ = st.columns([2, 1])
query = c_search.text_input("🔍 Cerca...", placeholder="Cerca...")

# Filtro base: note che NON hanno deleted=True
filtro = {"deleted": {"$ne": True}}

if query:
    # Aggiunge la ricerca al filtro base
    filtro = {
        "$and": [
            {"deleted": {"$ne": True}},
            {"$or": [{"titolo": {"$regex": query, "$options": "i"}}, {"contenuto": {"$regex": query, "$options": "i"}}]}
        ]
    }

note_attive = list(collection.find(filtro).sort("data", -1))

if not note_attive:
    st.info("Nessuna nota presente.")
else:
    cols = st.columns(3)
    for index, nota in enumerate(note_attive):
        with cols[index % 3]:
            with st.container(border=True):
                st.markdown(f"### {nota['titolo']}")
                st.markdown(nota['contenuto'], unsafe_allow_html=True)
                st.write("---")
                b1, b2 = st.columns(2)
                
                if b1.button("✏️ Modifica", key=f"ed_btn_{nota['_id']}"):
                    apri_popup_modifica(nota['_id'], nota['titolo'], nota['contenuto'])
                
                # Apre il popup di conferma invece di cancellare subito
                if b2.button("🗑️ Elimina", key=f"del_btn_{nota['_id']}"):
                    conferma_eliminazione(nota['_id'])

# --- CESTINO (Espandibile in fondo) ---
st.write("")
st.write("")
with st.expander("🗑️ Cestino (Note eliminate)"):
    # Recuperiamo solo le note con deleted=True
    note_cestino = list(collection.find({"deleted": True}).sort("data", -1))
    
    if not note_cestino:
        st.write("Il cestino è vuoto.")
    else:
        if st.button("🔥 Svuota Cestino Definitivamente", type="primary"):
            collection.delete_many({"deleted": True})
            st.rerun()
            
        st.write(f"Ci sono {len(note_cestino)} note nel cestino.")
        for nota in note_cestino:
            c1, c2, c3 = st.columns([4, 1, 1])
            c1.write(f"📄 **{nota['titolo']}**")
            
            # Tasto Ripristina
            if c2.button("♻️", key=f"rest_{nota['_id']}", help="Ripristina"):
                collection.update_one({"_id": nota['_id']}, {"$set": {"deleted": False}})
                st.rerun()
                
            # Tasto Elimina per sempre (singolo)
            if c3.button("❌", key=f"perm_del_{nota['_id']}", help="Elimina per sempre"):
                collection.delete_one({"_id": nota['_id']})
                st.rerun()
