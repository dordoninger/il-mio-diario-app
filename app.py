import streamlit as st
import pymongo
from datetime import datetime
from streamlit_quill import st_quill
import time

# --- 1. CONFIGURAZIONE E NOME APP ---
st.set_page_config(page_title="DBJ Notes", page_icon="📓", layout="wide")

# --- 2. CSS PERSONALIZZATO (Colori, Bordi, Sfondi) ---
# Qui gestiamo il bordo nero e lo sfondo personalizzabile
bg_color = "#f0f2f6" # Colore di sfondo base (grigio chiaro elegante)
card_color = "#ffffff" # Colore delle note

st.markdown(f"""
<style>
    /* Bordo nero quando scrivi (invece che rosso) */
    .stTextInput input:focus, .stTextArea textarea:focus {{
        border-color: #000000 !important;
        box-shadow: 0 0 0 1px #000000 !important;
    }}
    /* Rimuove bordo rosso da Quill se c'è */
    iframe {{
        border: 1px solid #ddd !important;
    }}
    
    /* Stile per i "Quadrotti" delle note */
    .nota-card {{
        background-color: {card_color};
        padding: 20px;
        border-radius: 15px;
        border: 1px solid #e0e0e0;
        box-shadow: 2px 2px 10px rgba(0,0,0,0.05);
        margin-bottom: 20px;
        height: 100%;
    }}
    
    /* Titolo App */
    .main-title {{
        font-size: 3em;
        font-weight: bold;
        background: -webkit-linear-gradient(45deg, #FF4B4B, #000000);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }}
</style>
""", unsafe_allow_html=True)

# --- 3. SPLASH SCREEN (Animazione iniziale) ---
if 'first_load' not in st.session_state:
    placeholder = st.empty()
    with placeholder.container():
        st.markdown("<h1 style='text-align: center; margin-top: 200px;'>📓 DBJ Notes</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center;'>Caricamento...</p>", unsafe_allow_html=True)
        time.sleep(0.8) # Durata animazione
    placeholder.empty()
    st.session_state['first_load'] = True

# --- CONNESSIONE DATABASE ---
@st.cache_resource
def init_connection():
    try:
        return pymongo.MongoClient(st.secrets["mongo"]["connection_string"])
    except Exception as e:
        return None

client = init_connection()
if client is None:
    st.error("Errore di connessione al Database. Controlla i Secrets.")
    st.stop()

db = client.diario_db
collection = db.note

# --- GESTIONE STATO (Per Modifica e Pulizia) ---
if 'form_titolo' not in st.session_state: st.session_state.form_titolo = ""
if 'form_contenuto' not in st.session_state: st.session_state.form_contenuto = ""
if 'edit_mode' not in st.session_state: st.session_state.edit_mode = False # Siamo in modifica?
if 'edit_id' not in st.session_state: st.session_state.edit_id = None # Quale nota stiamo modificando?

# --- INTERFACCIA PRINCIPALE ---
st.markdown("<h1 class='main-title'>DBJ Notes</h1>", unsafe_allow_html=True)

# --- AREA CREAZIONE / MODIFICA (Collapsible) ---
label_creazione = "✍️ Modifica Nota" if st.session_state.edit_mode else "✍️ Crea Nuova Nota"
# Se siamo in modifica, apriamo l'expander automaticamente, altrimenti chiuso
is_expanded = True if st.session_state.edit_mode else False

with st.expander(label_creazione, expanded=is_expanded):
    # Selettore colore nota (Bonus richiesto)
    col_opt1, col_opt2 = st.columns([1,1])
    
    # Input Titolo
    titolo = st.text_input("Titolo", value=st.session_state.form_titolo)
    
    # Configurazione Toolbar Quill (Rimosso tasti rotti, aggiunto Formule e Header)
    # Tasti: Bold, Italic, Underline, Strike | Header | List | Formula | Clean
    toolbar_config = [
        ['bold', 'italic', 'underline', 'strike'],
        [{'header': 1}, {'header': 2}],
        [{'list': 'ordered'}, {'list': 'bullet'}],
        ['formula'], # Abilita LaTeX
        ['clean'] # Rimuove formattazione
    ]
    
    # Input Contenuto (Quill)
    # Nota: inserire immagini si fa trascinandole dentro o col copia-incolla
    contenuto = st_quill(
        value=st.session_state.form_contenuto,
        placeholder="Scrivi qui...",
        html=True,
        toolbar=toolbar_config,
        key="quill_editor_main"
    )

    # Pulsanti Azione
    col_save, col_cancel = st.columns([1, 5])
    
    msg_bottone = "💾 Salva Modifiche" if st.session_state.edit_mode else "💾 Salva Nuova Nota"
    
    if col_save.button(msg_bottone):
        if titolo and contenuto:
            documento = {
                "titolo": titolo,
                "contenuto": contenuto,
                "data": datetime.now(),
                "tipo": "testo_ricco"
            }
            
            if st.session_state.edit_mode:
                # AGGIORNAMENTO (Update)
                collection.update_one({"_id": st.session_state.edit_id}, {"$set": documento})
                st.success("Nota modificata!")
            else:
                # NUOVO INSERIMENTO (Insert)
                collection.insert_one(documento)
                st.success("Nota creata!")
            
            # Reset del form dopo il salvataggio
            st.session_state.form_titolo = ""
            st.session_state.form_contenuto = ""
            st.session_state.edit_mode = False
            st.session_state.edit_id = None
            time.sleep(0.5)
            st.rerun()
        else:
            st.warning("Inserisci almeno titolo e contenuto.")

    if st.session_state.edit_mode:
        if col_cancel.button("Annulla Modifica"):
            st.session_state.form_titolo = ""
            st.session_state.form_contenuto = ""
            st.session_state.edit_mode = False
            st.session_state.edit_id = None
            st.rerun()

st.divider()

# --- OPZIONI VISUALIZZAZIONE ---
col_search, col_layout = st.columns([3, 1])
with col_search:
    search_query = st.text_input("🔍 Cerca...", label_visibility="collapsed", placeholder="Cerca nelle note...")
with col_layout:
    layout_mode = st.radio("Layout", ["Elenco", "Griglia"], horizontal=True, label_visibility="collapsed")

# --- RECUPERO NOTE ---
filtro = {}
if search_query:
    filtro = {"$or": [{"titolo": {"$regex": search_query, "$options": "i"}}, {"contenuto": {"$regex": search_query, "$options": "i"}}]}

note = list(collection.find(filtro).sort("data", -1))

# --- VISUALIZZAZIONE ---
if not note:
    st.info("Nessuna nota trovata.")
else:
    if layout_mode == "Elenco":
        # MODO ELENCO (Classico expander)
        for nota in note:
            with st.expander(f"{nota['titolo']}"):
                st.markdown(nota['contenuto'], unsafe_allow_html=True)
                c1, c2 = st.columns([1, 10])
                if c1.button("✏️", key=f"edit_{nota['_id']}"):
                    st.session_state.form_titolo = nota['titolo']
                    st.session_state.form_contenuto = nota['contenuto']
                    st.session_state.edit_mode = True
                    st.session_state.edit_id = nota['_id']
                    st.rerun()
                if c2.button("🗑️", key=f"del_{nota['_id']}"):
                    collection.delete_one({"_id": nota['_id']})
                    st.rerun()

    else:
        # MODO GRIGLIA (Quadretti)
        cols = st.columns(3) # 3 Colonne per riga
        for i, nota in enumerate(note):
            col = cols[i % 3] # Distribuisce le note nelle colonne 0, 1, 2
            with col:
                # Creiamo un "container" visivo per il quadrotto
                with st.container(border=True):
                    st.markdown(f"### {nota['titolo']}")
                    # Anteprima contenuto (troncato se troppo lungo)
                    # Rimuoviamo tag HTML per l'anteprima pulita è difficile qui, mostriamo render
                    st.markdown(nota['contenuto'], unsafe_allow_html=True)
                    st.divider()
                    
                    b1, b2 = st.columns(2)
                    if b1.button("✏️ Modifica", key=f"grid_edit_{nota['_id']}"):
                        st.session_state.form_titolo = nota['titolo']
                        st.session_state.form_contenuto = nota['contenuto']
                        st.session_state.edit_mode = True
                        st.session_state.edit_id = nota['_id']
                        st.rerun()
                    
                    if b2.button("🗑️ Elimina", key=f"grid_del_{nota['_id']}"):
                        collection.delete_one({"_id": nota['_id']})
                        st.rerun()
