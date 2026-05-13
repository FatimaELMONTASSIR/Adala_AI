"""
Interface Streamlit principale pour ADALA AI.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

load_dotenv(_ROOT / ".env")
load_dotenv()

import streamlit as st

st.set_page_config(
    page_title="ADALA AI",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)

def _appliquer_secrets_streamlit() -> None:
    """Copie les secrets Streamlit Cloud dans les variables d'environnement."""
    try:
        secrets = getattr(st, "secrets", None)
        if secrets is None:
            return
        for cle in secrets:
            val = secrets[cle]
            if cle not in os.environ or os.environ.get(cle, "") == "":
                os.environ[str(cle)] = str(val)
    except (FileNotFoundError, RuntimeError, KeyError, TypeError):
        return


_appliquer_secrets_streamlit()

from backend.rag.chain import ask_adala, texte_assistant_pour_historique

CODES_DISPONIBLES = [
    "Code du Travail",
    "Code Pénal",
    "Code de la Famille",
    "Code de Commerce",
    "Code des Obligations et Contrats",
    "Code de Procédure Civile",
]


def _initialiser_session() -> None:
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []


def _reinitialiser_conversation() -> None:
    st.session_state.messages = []
    st.session_state.chat_history = []


def _injecter_style_chatgpt() -> None:
    st.markdown(
        """
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
        <style>
        :root {
            --bg-app: #212121;
            --bg-sidebar: #171717;
            --bg-elevated: #2f2f2f;
            --bg-input: #2f2f2f;
            --border-subtle: #424242;
            --text-primary: #ececec;
            --text-muted: #a1a1aa;
            --accent: #10a37f;
            --chat-max: 48rem;
        }
        html, body, .stApp, [data-testid="stAppViewContainer"] {
            font-family: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif !important;
            background-color: var(--bg-app) !important;
            color: var(--text-primary) !important;
        }
        [data-testid="stHeader"] {
            background-color: var(--bg-app) !important;
            border-bottom: 1px solid var(--border-subtle);
        }
        [data-testid="stToolbar"] {
            background: transparent !important;
        }
        section[data-testid="stSidebar"] {
            background-color: var(--bg-sidebar) !important;
            border-right: 1px solid var(--border-subtle) !important;
        }
        section[data-testid="stSidebar"] .block-container {
            padding-top: 1.25rem;
        }
        section[data-testid="stSidebar"] h1,
        section[data-testid="stSidebar"] h2,
        section[data-testid="stSidebar"] h3,
        section[data-testid="stSidebar"] p,
        section[data-testid="stSidebar"] li,
        section[data-testid="stSidebar"] span,
        section[data-testid="stSidebar"] label {
            color: var(--text-primary) !important;
        }
        section[data-testid="stSidebar"] .stCaption,
        section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] {
            color: var(--text-muted) !important;
        }
        section[data-testid="stSidebar"] hr {
            border-color: var(--border-subtle) !important;
        }
        section[data-testid="stSidebar"] code {
            background: var(--bg-elevated) !important;
            color: #d4d4d8 !important;
            padding: 0.1rem 0.35rem;
            border-radius: 4px;
        }
        section[data-testid="stMain"] .block-container {
            max-width: var(--chat-max) !important;
            margin-left: auto !important;
            margin-right: auto !important;
            padding-left: 1rem !important;
            padding-right: 1rem !important;
            padding-top: 1rem !important;
            padding-bottom: 6rem !important;
        }
        [data-testid="stChatMessage"] {
            background-color: var(--bg-elevated) !important;
            border: 1px solid var(--border-subtle) !important;
            border-radius: 12px !important;
            padding: 0.75rem 1rem !important;
            margin-bottom: 0.75rem !important;
        }
        [data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] p,
        [data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] li {
            color: var(--text-primary) !important;
            line-height: 1.6 !important;
        }
        [data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] {
            font-size: 0.95rem !important;
        }
        [data-testid="stChatMessage"] label {
            color: var(--text-muted) !important;
            font-size: 0.75rem !important;
            text-transform: uppercase;
            letter-spacing: 0.04em;
        }
        [data-testid="stChatInput"] {
            background-color: var(--bg-input) !important;
            border: 1px solid var(--border-subtle) !important;
            border-radius: 9999px !important;
            box-shadow: 0 0 0 1px rgba(0,0,0,0.2) !important;
        }
        [data-testid="stChatInput"] textarea {
            color: var(--text-primary) !important;
        }
        [data-testid="stChatInputSubmitButton"] button {
            border-radius: 50% !important;
        }
        .streamlit-expanderHeader {
            color: var(--text-primary) !important;
            font-weight: 500 !important;
        }
        details.streamlit-expander {
            background-color: var(--bg-elevated) !important;
            border: 1px solid var(--border-subtle) !important;
            border-radius: 10px !important;
        }
        details.streamlit-expander summary {
            padding: 0.5rem 0.75rem !important;
        }
        details.streamlit-expander summary:hover {
            color: var(--accent) !important;
        }
        .stAlert {
            border-radius: 10px !important;
        }
        .adala-disclaimer {
            background-color: var(--bg-elevated);
            color: var(--text-muted);
            padding: 0.85rem 1rem;
            border-radius: 10px;
            border: 1px solid var(--border-subtle);
            margin-top: 1rem;
            font-size: 0.8125rem;
            line-height: 1.45;
            max-width: var(--chat-max);
            margin-left: auto;
            margin-right: auto;
        }
        @media (max-width: 768px) {
            section[data-testid="stMain"] .block-container {
                padding-left: 0.65rem !important;
                padding-right: 0.65rem !important;
            }
            [data-testid="stChatMessage"] {
                padding: 0.6rem 0.75rem !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:

    _initialiser_session()
    _injecter_style_chatgpt()

    with st.sidebar:
        st.markdown("### ADALA AI")
        st.caption("Assistant juridique marocain")
        st.divider()
        if st.button(
            "➕ Nouvelle conversation",
            type="primary",
            use_container_width=True,
        ):
            _reinitialiser_conversation()
            st.rerun()
        st.divider()
        st.markdown("**Corpus**")
        st.caption("Nommez vos PDF en conséquence (ex. `code_travail.pdf`).")
        for code in CODES_DISPONIBLES:
            st.markdown(f"- {code}")
        st.divider()
        _llm = (
            os.environ.get("ADALA_LLM", "").strip()
            or os.environ.get("LEXMAROC_LLM", "").strip()
            or "gemini"
        ).lower()
        if _llm not in ("gemini", "groq"):
            _llm = "gemini"
        st.caption(
            f"LLM : **{_llm}** · `ADALA_LLM` / `LEXMAROC_LLM`"
        )

    for msg in st.session_state.messages:
        role = msg.get("role", "user")
        with st.chat_message(role):
            st.markdown(msg.get("content", ""))
            if role == "assistant" and msg.get("detail"):
                with st.expander("Voir plus"):
                    st.markdown(msg["detail"])
            if role == "assistant" and msg.get("sources"):
                with st.expander("📋 Articles consultés"):
                    for src in msg["sources"]:
                        libelle = (
                            f"{src.get('code_name', '')} - Art. "
                            f"{src.get('article_number', '')}"
                        )
                        st.markdown(f"- **{libelle}**")

    prompt = st.chat_input("Posez votre question juridique…")
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            try:
                resultat = ask_adala(
                    prompt, list(st.session_state.chat_history)
                )
                reponse = resultat.get("answer_short") or resultat.get("answer", "")
                detail = resultat.get("answer_detail")
                sources = resultat.get("sources", [])
            except ValueError as err:
                st.error(f"Configuration manquante : {err}")
                reponse = (
                    "Impossible de contacter le service : vérifiez vos clés et "
                    "paramètres dans les secrets ou le fichier d'environnement."
                )
                detail = None
                sources = []
            except RuntimeError as err:
                st.error(str(err))
                reponse = (
                    "Une erreur technique est survenue. Consultez le message "
                    "ci-dessus ou réessayez plus tard."
                )
                detail = None
                sources = []
            except Exception as err:
                st.error(f"Erreur inattendue : {err}")
                reponse = (
                    "Une erreur inattendue est survenue. Veuillez réessayer "
                    "ultérieurement."
                )
                detail = None
                sources = []

            st.markdown(reponse)
            if detail:
                with st.expander("Voir plus"):
                    st.markdown(detail)
            if sources:
                with st.expander("📋 Articles consultés"):
                    for src in sources:
                        libelle = (
                            f"{src.get('code_name', '')} - Art. "
                            f"{src.get('article_number', '')}"
                        )
                        st.markdown(f"- **{libelle}**")

        st.session_state.chat_history.append(
            {"role": "user", "content": prompt}
        )
        st.session_state.chat_history.append(
            {
                "role": "assistant",
                "content": texte_assistant_pour_historique(reponse, detail),
            }
        )
        msg_assistant: dict = {
            "role": "assistant",
            "content": reponse,
            "sources": sources,
        }
        if detail:
            msg_assistant["detail"] = detail
        st.session_state.messages.append(msg_assistant)

    st.markdown(
        '<div class="adala-disclaimer">⚠️ ADALA AI est un outil d\'information. '
        "Il ne remplace pas les conseils d'un avocat.</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
