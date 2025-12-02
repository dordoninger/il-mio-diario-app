import streamlit as st
import pymongo
from datetime import datetime, timedelta
from streamlit_quill import st_quill
import time
import uuid
import bson.binary
import json

# --- 1. CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="DOR NOTES", page_icon="📄", layout="wide")

# --- 2. GESTIONE STATO & PREFERENZE ---
if 'text_size' not in st.session_state: st.session_state.text_size = "16px"

# --- 3. CSS ESTETICO (DOR NOTES STYLE) ---
st.markdown(f"""
<style>
    /* TITOLO DOR NOTES (Fine, Elegante, Spaziato) */
    .dor-title {{
        font-family: 'Helvetica Neue', 'Helvetica', 'Arial', sans-serif;
        font-weight: 300; /* Molto fine (Thin) */
        font-size: 2.2rem; /* Più piccolo */
        color: #000000;
        text-align: left; /* Allineato a sinistra per bilanciare i bottoni */
        letter-spacing: 4px; /* Spaziatura aesthetic */
        text-transform: uppercase;
        margin-top: 10px;
        margin-bottom: 0px;
    }}

    /* EXPANDER STYLE (Tendine) */
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
    
    /* Contenuto Lettura */
    .quill-read-content {{
        font-size: {st.session_state.text_size} !important;
        font-family: 'Georgia', serif; /* Font lettura più piacevole */
        line-height: 1.6;
    }}

    /* INPUTS FOCUS (Nero minimal) */
    .stTextInput > div > div > input:focus {{
        border-color: #000 !important;
        box-shadow: 0 0 0 1px #000 !important;
    }}
    
    /* ANIMAZIONE LOGO */
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
        animation: fade-in 1.5s ease-out;
        margin-top: 30vh;
    }}
    
    /* Allineamento Bottoni Header */
    div[data-testid="column"] {{
        display: flex;
        align-items: center; /* Centra verticalmente col titolo */
    }}
</style>
""", unsafe_allow_html=True)

# --- 4. INIT & CONNESSIONE DB ---
if 'first_load' not in st.session_state:
    placeholder = st.empty()
    with placeholder.container():
        # Nuova animazione elegante testuale
        st.markdown("<div class='splash-text'>DOR NOTES</div>", unsafe_allow_html=True)
        time.sleep(1.5)
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

# --- 5. FUNZIONI UTILITÀ ---
def converti_note_per_json(note_list):
    export_list = []
    for nota in note_list:
        nota_export = nota.copy()
        nota_export['_id'] = str(nota['_id'])
        nota_export['data'] = nota['data'].strftime("%Y-%m-%d %H:%M:%S")
        if 'file_data' in nota_export: del nota_export['file_data']
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

# --- 7. DIALOGHI (TUTTO IN ITALIANO) ---

# Popup Impostazioni
@st.dialog("Impostazioni")
def apri_impostazioni():
    st.write("**Backup Note**")
    tutte_le_note = list(collection.find({}))
    json_dati = converti_note_per_json(tutte_le_note)
    st.download_button(
        label="Scarica Backup (.json)",
        data=json_dati,
        file_name=f"backup_dornotes_{datetime.now().strftime('%Y%m%d')}.json",
        mime="application/json"
    )
    
    st.divider()
    
    st.write("**Accessibilità**")
    size_opt = st.select_slider("Dimensione Testo", options=["14px", "16px", "18px", "20px", "24px"], value=st.session_state.text_size)
    if size_opt != st.session_state.text_size:
        st.session_state.text_size = size_opt
        st.rerun()
        
    st.divider()
    
    st.write("**Manutenzione**")
    if st.button("Pulisci Cestino (>30 gg)"):
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
    
    if st.button("Salva Modifiche", type="primary"):
        collection.update_one(
            {"_id": nota_id},
            {"$set": {"titolo": nuovo_titolo, "contenuto": nuovo_contenuto, "data": datetime.now()}}
        )
        st.rerun()

# Popup Cestino
@st.dialog("Cestino", width="large")
def apri_cestino():
    note_cestino = list(collection.find({"deleted": True}).sort("data", -1))
    col1, col2 = st.columns([3, 1])
    col1.write(f"Note nel cestino: {len(note_cestino)}")
    if note_cestino:
        if col2.button("Svuota tutto"):
            collection.delete_many({"deleted": True})
            st.rerun()
        st.divider()
        for nota in note_cestino:
            c1, c2, c3 = st.columns([4, 1, 1])
            c1.markdown(f"**{nota['titolo']}**")
            if c2.button("♻️ Ripristina", key=f"rest_{nota['_id']}"):
                collection.update_one({"_id": nota['_id']}, {"$set": {"deleted": False}})
                st.rerun()
            if c3.button("❌ Elimina", key=f"kill_{nota['_id']}"):
                collection.delete_one({"_id": nota['_id']})
                st.rerun()
    else:
        st.info("Il cestino è vuoto.")

# Popup Conferma Eliminazione
@st.dialog("⚠️ Conferma")
def conferma_eliminazione(nota_id):
    st.write("Spostare questa nota nel cestino?")
    c1, c2 = st.columns(2)
    if c1.button("Sì, elimina", type="primary"):
        collection.update_one({"_id": nota_id}, {"$set": {"deleted": True}})
        st.rerun()
    if c2.button("Annulla"):
        st.rerun()

# --- INTERFACCIA PRINCIPALE ---

# 1. HEADER (TITOLO A SINISTRA, BOTTONI A DESTRA)
head_col1, head_col2, head_col3 = st.columns([6, 1, 1]) # Proporzioni

with head_col1:
    st.markdown("<div class='dor-title'>DOR NOTES</div>", unsafe_allow_html=True)

with head_col2:
    if st.button("⚙️:gear:", help="Impostazioni"):
        apri_impostazioni()

with head_col3:
    if st.button("🗑️", help="Cestino"):
        apri_cestino()

st.markdown("---") # Linea divisoria sottile subito sotto l'header

# 2. SEZIONE CREA (SOLO CREAZIONE)
with st.expander("Crea nuova nota"):
    titolo_input = st.text_input("Titolo", key=f"tit_{st.session_state.editor_key}")
    contenuto_input = st_quill(
        placeholder="Scrivi qui i tuoi pensieri...",
        html=True,
        toolbar=toolbar_config,
        key=f"quill_{st.session_state.editor_key}"
    )
    uploaded_file = st.file_uploader("Carica File", type=['pdf', 'docx', 'txt', 'mp3', 'wav', 'jpg', 'png'], key=f"file_{st.session_state.editor_key}")
    
    if st.button("Salva Nota"):
        if titolo_input and contenuto_input:
            doc = {
                "titolo": titolo_input,
                "contenuto": contenuto_input,
                "data": datetime.now(),
                "tipo": "testo_ricco",
                "deleted": False,
                "pinned": False,
                "file_name": uploaded_file.name if uploaded_file else None,
                "file_data": bson.binary.Binary(uploaded_file.getvalue()) if uploaded_file else None
            }
            collection.insert_one(doc)
            st.toast("Nota salvata!", icon="✅")
            st.session_state.editor_key = str(uuid.uuid4())
            time.sleep(0.2)
            st.rerun()
        else:
            st.warning("Inserisci titolo e contenuto.")

st.write("") # Spazio

# 3. RICERCA E GRIGLIA
query = st.text_input("🔍", placeholder="Cerca tra le note...", label_visibility="collapsed")

filtro = {"deleted": {"$ne": True}}
if query:
    filtro = {"$and": [{"deleted": {"$ne": True}}, {"$or": [{"titolo": {"$regex": query, "$options": "i"}}, {"contenuto": {"$regex": query, "$options": "i"}}]}]}

# Ordinamento: Pinned prima, poi Data
note_attive = list(collection.find(filtro).sort([("pinned", -1), ("data", -1)]))

if not note_attive:
    st.info("Nessuna nota presente.")
else:
    cols = st.columns(3)
    for index, nota in enumerate(note_attive):
        with cols[index % 3]:
            # Gestione Icone
            icona_clip = "📎 " if nota.get("file_name") else ""
            is_pinned = nota.get("pinned", False)
            icona_pin = "📌 " if is_pinned else ""
            
            # Tendina
            with st.expander(f"{icona_pin}{icona_clip} {nota['titolo']}"):
                
                # Contenuto
                st.markdown(f"<div class='quill-read-content'>{nota['contenuto']}</div>", unsafe_allow_html=True)
                
                # File Allegato
                if nota.get("file_name"):
                    st.markdown("---")
                    st.caption(f"Allegato: {nota['file_name']}")
                    st.download_button("Scarica", data=nota["file_data"], file_name=nota["file_name"])
                
                st.markdown("---")
                
                # PULSANTI (TRADOTTI E RIORDINATI)
                c_mod, c_pin, c_del = st.columns(3)
                
                if c_mod.button("Modifica", key=f"mod_{nota['_id']}"):
                    apri_popup_modifica(nota['_id'], nota['titolo'], nota['contenuto'])
                
                # Logica Pin/Unpin tradotta
                label_pin = "Sblocca" if is_pinned else "Fissa"
                if c_pin.button(label_pin, key=f"pin_{nota['_id']}"):
                     new_state = not is_pinned
                     collection.update_one({"_id": nota['_id']}, {"$set": {"pinned": new_state}})
                     st.rerun()

                if c_del.button("Elimina", key=f"del_{nota['_id']}"):
                    conferma_eliminazione(nota['_id'])
