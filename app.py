import streamlit as st
import pymongo
from datetime import datetime
from streamlit_quill import st_quill
import time

# --- 1. CONFIGURAZIONE ---
st.set_page_config(page_title="DBJ Notes", page_icon="📝", layout="wide")

# --- 2. CSS ESTETICO & FIX BORDI ROSSI ---
st.markdown("""
<style>
    /* Rimuove il bordo rosso di focus e mette un grigio elegante o nero */
    .stTextInput > div > div > input:focus {
        border-color: #4A90E2 !important;
        box-shadow: 0 0 0 1px #4A90E2 !important;
    }
    .stTextArea > div > div > textarea:focus {
        border-color: #4A90E2 !important;
        box-shadow: 0 0 0 1px #4A90E2 !important;
    }
    
    /* Stile Animazione Iniziale */
    @keyframes pulse {
        0% { transform: scale(1); opacity: 0.8; }
        50% { transform: scale(1.1); opacity: 1; }
        100% { transform: scale(1); opacity: 0.8; }
    }
    .splash-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        height: 60vh;
        animation: pulse 1.2s infinite;
    }
    
    /* Titolo Aesthetic */
    .aesthetic-title {
        font-family: 'Helvetica Neue', sans-serif;
        font-weight: 800;
        font-size: 3.5rem;
        background: -webkit-linear-gradient(120deg, #84fab0 0%, #8fd3f4 100%); /* Verde acqua / Azzurro */
        background: linear-gradient(120deg, #a18cd1 0%, #fbc2eb 100%); /* Viola / Rosa Pastello */
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        margin-bottom: 0px;
    }
    .subtitle {
        text-align: center;
        color: #666;
        font-size: 1.2rem;
        margin-bottom: 30px;
    }

    /* Card della Nota (Grid) */
    .note-card {
        background-color: white;
        border-radius: 15px;
        padding: 20px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.05);
        border: 1px solid #f0f0f0;
        transition: transform 0.2s;
        height: 100%;
    }
    .note-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 8px 25px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

# --- 3. ANIMAZIONE INIZIALE (1.2 sec) ---
if 'first_load' not in st.session_state:
    placeholder = st.empty()
    with placeholder.container():
        st.markdown("""
            <div class='splash-container'>
                <div style='font-size: 80px;'>📝✨</div>
                <h1 style='color: #333;'>DBJ Notes</h1>
            </div>
        """, unsafe_allow_html=True)
        time.sleep(1.2) # Durata richiesta
    placeholder.empty()
    st.session_state['first_load'] = True

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

# --- CONFIGURAZIONE TOOLBAR EDITOR (Completa come v2.0) ---
# Rimossi i tasti rotti, mantenuti colori, font, elenchi, immagini, formule
toolbar_full = [
    ['bold', 'italic', 'underline', 'strike'],        # formatting toggles
    ['blockquote', 'code-block'],
    [{ 'header': 1 }, { 'header': 2 }],               # custom button values
    [{ 'list': 'ordered'}, { 'list': 'bullet' }],
    [{ 'script': 'sub'}, { 'script': 'super' }],      # superscript/subscript
    [{ 'indent': '-1'}, { 'indent': '+1' }],          # outdent/indent
    [{ 'direction': 'rtl' }],                         # text direction
    [{ 'size': ['small', False, 'large', 'huge'] }],  # custom dropdown
    [{ 'header': [1, 2, 3, 4, 5, 6, False] }],
    [{ 'color': [] }, { 'background': [] }],          # dropdown with defaults from theme
    [{ 'font': [] }],
    [{ 'align': [] }],
    ['link', 'image', 'formula'],                     # link, image, formula (latex)
    ['clean']                                         # remove formatting
]

# --- FUNZIONE MODALE PER MODIFICA (La Magia) ---
# Questo crea una finestra popup separata per modificare
@st.dialog("Modifica Nota")
def apri_popup_modifica(nota_id, titolo_vecchio, contenuto_vecchio):
    st.write("Modifica qui sotto e salva.")
    nuovo_titolo = st.text_input("Titolo", value=titolo_vecchio)
    # Editor dentro il popup
    nuovo_contenuto = st_quill(value=contenuto_vecchio, toolbar=toolbar_full, html=True, key=f"quill_edit_{nota_id}")
    
    if st.button("💾 Salva Modifiche", key=f"save_btn_{nota_id}"):
        collection.update_one(
            {"_id": nota_id},
            {"$set": {
                "titolo": nuovo_titolo,
                "contenuto": nuovo_contenuto,
                "data": datetime.now() # Aggiorna data modifica
            }}
        )
        st.success("Modificata!")
        time.sleep(0.5)
        st.rerun()

# --- INTERFACCIA PRINCIPALE ---

# Titolo Aesthetic
st.markdown("<div class='aesthetic-title'>DBJ Notes</div>", unsafe_allow_html=True)
st.markdown("<div class='subtitle'>Il tuo spazio creativo 📝</div>", unsafe_allow_html=True)

st.divider()

# --- SEZIONE CREAZIONE (Sempre fissa e vuota dopo il save) ---
st.subheader("✨ Nuova Nota")

# Usiamo un form per garantire che si svuoti dopo l'invio
with st.container(border=True):
    # Nota: st_quill dentro un form a volte fa i capricci col clear, 
    # quindi usiamo la session state per forzare la pulizia manuale.
    
    if 'new_title' not in st.session_state: st.session_state.new_title = ""
    if 'new_content' not in st.session_state: st.session_state.new_content = ""

    titolo_input = st.text_input("Titolo Nota", value=st.session_state.new_title, key="input_titolo_create")
    contenuto_input = st_quill(
        placeholder="Scrivi qui... (Trascina immagini o usa la barra)",
        html=True,
        toolbar=toolbar_full,
        key="quill_create_main"
    )

    if st.button("Salva Nota 💾"):
        if titolo_input and contenuto_input:
            doc = {
                "titolo": titolo_input,
                "contenuto": contenuto_input,
                "data": datetime.now(),
                "tipo": "testo_ricco"
            }
            collection.insert_one(doc)
            st.toast("Nota Salvata con successo!", icon="✅")
            # Trucco per pulire i campi: Ricaricare la pagina resetta l'editor
            time.sleep(0.5)
            st.rerun()
        else:
            st.warning("Scrivi almeno un titolo e del testo.")

st.divider()

# --- SEZIONE VISUALIZZAZIONE (Solo Griglia) ---
c_search, _ = st.columns([2, 1])
query = c_search.text_input("🔍 Cerca...", placeholder="Cerca tra le note...")

filtro = {}
if query:
    filtro = {"$or": [{"titolo": {"$regex": query, "$options": "i"}}, {"contenuto": {"$regex": query, "$options": "i"}}]}

note = list(collection.find(filtro).sort("data", -1))

st.subheader(f"Le tue Note ({len(note)})")

if not note:
    st.info("Nessuna nota presente. Scrivine una sopra!")
else:
    # GRIGLIA A 3 COLONNE
    cols = st.columns(3)
    for index, nota in enumerate(note):
        col_corrente = cols[index % 3]
        
        with col_corrente:
            # Disegniamo la card
            with st.container(border=True):
                st.markdown(f"### {nota['titolo']}")
                # Anteprima del contenuto (renderizzato parzialmente)
                st.markdown(nota['contenuto'], unsafe_allow_html=True)
                
                st.write("---")
                b1, b2 = st.columns(2)
                
                # TASTO MODIFICA: Apre il Popup
                if b1.button("✏️ Edit", key=f"btn_edit_{nota['_id']}"):
                    apri_popup_modifica(nota['_id'], nota['titolo'], nota['contenuto'])
                
                # TASTO ELIMINA
                if b2.button("🗑️ Del", key=f"btn_del_{nota['_id']}"):
                    collection.delete_one({"_id": nota['_id']})
                    st.rerun()
