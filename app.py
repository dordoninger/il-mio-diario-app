import streamlit as st
import pymongo
from datetime import datetime
from streamlit_quill import st_quill

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Il mio Diario", page_icon="📔", layout="centered")

# --- CSS PERSONALIZZATO (Per rendere l'app più carina) ---
st.markdown("""
<style>
    .stButton>button {
        width: 100%;
        background-color: #FF4B4B;
        color: white;
    }
    .nota-box {
        border: 1px solid #ddd;
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

# --- CONNESSIONE AL DATABASE ---
@st.cache_resource
def init_connection():
    try:
        return pymongo.MongoClient(st.secrets["mongo"]["connection_string"])
    except Exception as e:
        st.error(f"Errore DB: {e}")
        return None

client = init_connection()
if client is None: st.stop()
db = client.diario_db
collection = db.note

# --- INTERFACCIA ---
st.title("📔 Il mio Diario 2.0")

# --- AREA CREAZIONE (Ora con Editor Ricco) ---
with st.expander("✍️ Crea una nuova nota", expanded=True):
    titolo = st.text_input("Titolo")
    
    st.write("Scrivi qui sotto (usa la barra per grassetto, elenchi, ecc):")
    # Qui usiamo l'editor Quill invece della text_area
    # html=True permette di salvare la formattazione
    contenuto = st_quill(placeholder="Caro diario...", html=True, key="quill_editor")
    
    # Il bottone è fuori dal form perché Quill gestisce i dati in modo speciale
    if st.button("Salva Nota"):
        if titolo and contenuto:
            doc = {
                "tipo": "testo_ricco",
                "titolo": titolo,
                "contenuto": contenuto, # Qui salviamo il codice HTML (con grassetti e colori)
                "data": datetime.now(),
                "preferito": False
            }
            collection.insert_one(doc)
            st.success("Nota salvata!")
            import time
            time.sleep(1) # Aspetta un attimo per farti leggere il messaggio
            st.rerun()
        else:
            st.warning("Devi inserire almeno un titolo e del testo.")

st.divider()

# --- FILTRI E RICERCA (Bonus richiesto da te!) ---
col_ricerca, col_filtro = st.columns([3, 1])
with col_ricerca:
    search_query = st.text_input("🔍 Cerca nelle note...")

# Logica di ricerca
filtro_db = {}
if search_query:
    # Cerca nel titolo O nel contenuto (case insensitive)
    filtro_db = {
        "$or": [
            {"titolo": {"$regex": search_query, "$options": "i"}},
            {"contenuto": {"$regex": search_query, "$options": "i"}}
        ]
    }

# Recupero note
note = list(collection.find(filtro_db).sort("data", -1))

st.subheader(f"Le tue Note ({len(note)})")

for nota in note:
    data_fmt = nota["data"].strftime("%d/%m/%Y %H:%M")
    
    with st.expander(f"📄 {nota['titolo']} ({data_fmt})"):
        # Qui usiamo markdown con unsafe_allow_html per mostrare grassetti e colori
        st.markdown(nota['contenuto'], unsafe_allow_html=True)
        
        st.write("---")
        col_del, col_space = st.columns([1, 4])
        if col_del.button("Elimina 🗑️", key=str(nota["_id"])):
            collection.delete_one({"_id": nota["_id"]})
            st.rerun()
