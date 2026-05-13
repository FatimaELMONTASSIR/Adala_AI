"""
Interface Streamlit principale pour LexMaroc.
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
    page_title="LexMaroc",
    page_icon="⚖️",
    layout="centered",
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

from backend.rag.chain import ask_lexmaroc, texte_assistant_pour_historique

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


def main() -> None:
    
    _initialiser_session()

    st.markdown(
        """
        <style>
        .lexmaroc-banner {
            background-color: #fff3cd;
            color: #664d03;
            padding: 0.75rem 1rem;
            border-radius: 0.5rem;
            border: 1px solid #ffecb5;
            margin-top: 1rem;
            font-size: 0.95rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("# LEXMAROC")
    st.caption("Assistant Juridique Marocain")

    with st.sidebar:
        st.subheader("Codes juridiques")
        st.markdown(
            "Corpus indicatif (nommez vos PDF en conséquence, "
            "par ex. `code_travail.pdf`) :"
        )
        for code in CODES_DISPONIBLES:
            st.markdown(f"- {code}")
        st.divider()
        if st.button("🔄 Nouvelle conversation", use_container_width=True):
            _reinitialiser_conversation()
            st.rerun()
        st.divider()
        _llm = (os.environ.get("LEXMAROC_LLM", "") or "gemini").strip().lower()
        if _llm not in ("gemini", "groq"):
            _llm = "gemini"
        st.caption(f"Fournisseur LLM : **{_llm}** (`LEXMAROC_LLM`)")

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
                resultat = ask_lexmaroc(
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
        '<div class="lexmaroc-banner">⚠️ LexMaroc est un outil d\'information. '
        "Il ne remplace pas les conseils d'un avocat.</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
