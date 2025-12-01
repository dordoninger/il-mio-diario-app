import streamlit as st
import pymongo
from datetime import datetime

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Il mio Diario", page_icon="📔", layout="centered")

# --- CONNESSIONE AL DATABASE (MONGODB) ---
# Questa funzione serve a collegarsi senza rallentare l'app ogni volta
@st.cache_resource
def init_connection():
    try:
        # Legge la stringa che hai messo nei "Secrets" di Streamlit
        return pymongo.MongoClient(st.secrets["mongo"]["connection_string"])
    except Exception as e:
        st.error(f"Errore di connessione al Database: {e}")
        return None

client = init_connection()

# Se la connessione fallisce, fermiamo tutto
if client is None:
    st.stop()

# Definiamo il "Cassetto" (Database) e la "Cartella" (Collection) dove salvare le note
db = client.diario_db
collection = db.note

# --- INTERFACCIA UTENTE ---
st.title("📔 Il mio Diario Personale")

# --- AREA CREAZIONE NUOVA NOTA ---
with st.expander("✍️ Crea una nuova nota", expanded=False):
    with st.form("nuova_nota_form"):
        titolo = st.text_input("Titolo della nota")
        # Area di testo semplice per ora
        contenuto = st.text_area("Scrivi qui i tuoi pensieri...", height=150)
        
        # Tasto per salvare
        submitted = st.form_submit_button("Salva Nota")
        
        if submitted and titolo and contenuto:
            # Creiamo il pacchetto dati da spedire a MongoDB
            documento_nota = {
                "tipo": "testo",  # Prepariamoci per il futuro (disegni, audio, etc.)
                "titolo": titolo,
                "contenuto": contenuto,
                "data": datetime.now(),
                "preferito": False
            }
            # Inviamo al database
            collection.insert_one(documento_nota)
            st.success("Nota salvata con successo!")
            # Ricarichiamo la pagina per vedere la nuova nota
            st.rerun()

st.divider() # Una linea divisoria

# --- AREA VISUALIZZAZIONE NOTE ---
st.subheader("Le tue Note")

# Recuperiamo tutte le note dal database, dalla più recente alla più vecchia
note_salvate = list(collection.find().sort("data", -1))

if len(note_salvate) == 0:
    st.info("Non hai ancora scritto nulla. Crea la tua prima nota sopra!")
else:
    # Mostriamo le note
    for nota in note_salvate:
        # Formattiamo la data in modo leggibile (es. 12/03/2025 10:30)
        data_fmt = nota["data"].strftime("%d/%m/%Y %H:%M")
        icona = "📄"
        
        # Usiamo un "expander" per ogni nota (si apre cliccandoci)
        with st.expander(f"{icona} {nota['titolo']} - {data_fmt}"):
            st.write(nota['contenuto'])
            
            # Tasto per cancellare la nota (opzionale ma utile)
            col1, col2 = st.columns([1, 5])
            with col1:
                if st.button("Elimina", key=str(nota["_id"])):
                    collection.delete_one({"_id": nota["_id"]})
                    st.rerun()
