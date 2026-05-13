"""
Chaîne RAG : récupération d'articles, construction du contexte, appel LLM (Gemini ou Groq).
"""

from __future__ import annotations

import os
import re
from typing import Any

import google.generativeai as genai
from groq import Groq

from backend.rag.prompt import PHRASE_REFUS, SYSTEM_PROMPT
from backend.rag.retriever import retrieve


def texte_assistant_pour_historique(
    answer_short: str, answer_detail: str | None
) -> str:
    """Message assistant envoyé au modèle au tour suivant (résumé + détail si présent)."""
    court = (answer_short or "").strip()
    if answer_detail and answer_detail.strip():
        return (
            f"### Résumé\n{court}\n\n### Détail\n{answer_detail.strip()}"
        )
    return court


def _parser_resume_detail(brut: str) -> tuple[str, str | None]:
    """
    Extrait résumé et détail si le modèle a respecté les sections ### Résumé / ### Détail.
    Sinon retourne le texte entier comme résumé et pas de détail.
    """
    brut = (brut or "").strip()
    if not brut:
        return "", None
    if brut.strip() == PHRASE_REFUS:
        return brut, None

    m = re.search(r"(?ms)^#{1,3}\s*D[eé]tail\s*$", brut)
    if not m:
        return brut, None
    avant = brut[: m.start()].strip()
    apres = brut[m.end() :].strip()
    if not apres:
        return brut, None

    resume = re.sub(
        r"(?is)^#{1,3}\s*R[eé]sum[eé]\s*\n?",
        "",
        avant,
        count=1,
    ).strip()
    if not resume:
        resume = avant
    return resume, apres


def _format_context(sources: list[dict[str, Any]]) -> str:
    if not sources:
        return "(Aucun article pertinent n'a été trouvé dans le corpus.)"
    parts: list[str] = []
    for s in sources:
        header = f"[{s.get('code_name', '')} - Art. {s.get('article_number', '')}]"
        body = s.get("article_text", "")
        parts.append(f"{header}\n{body}")
    return "\n\n---\n\n".join(parts)


def _fournisseur_llm() -> str:
    """``gemini`` (défaut) ou ``groq`` (voir ``ADALA_LLM`` ou ``LEXMAROC_LLM``)."""
    v = (
        os.environ.get("ADALA_LLM", "").strip()
        or os.environ.get("LEXMAROC_LLM", "").strip()
        or "gemini"
    ).lower()
    if v in ("groq", "gemini"):
        return v
    return "gemini"


def _cle_gemini() -> str | None:
    """Clé API : GEMINI_API_KEY, puis GOOGLE_API_KEY (défaut Google AI Studio)."""
    return (
        os.environ.get("GEMINI_API_KEY", "").strip()
        or os.environ.get("GOOGLE_API_KEY", "").strip()
        or None
    )


def _cle_groq() -> str | None:
    return (os.environ.get("GROQ_API_KEY", "") or "").strip() or None


def _nom_modele_court(nom_api: str) -> str:
    """Transforme ``models/gemini-2.0-flash`` en ``gemini-2.0-flash``."""
    if nom_api.startswith("models/"):
        return nom_api[len("models/") :]
    return nom_api


def _selectionner_modele_gemini(cle: str, modele_env: str | None) -> str:
    """
    Choisit un identifiant de modèle valide pour ``generateContent``.

    Les noms courts (ex. ``gemini-1.5-flash``) changent selon les régions et
    versions d'API ; on interroge la liste des modèles exposés pour la clé.
    """
    genai.configure(api_key=cle)
    try:
        listed = list(genai.list_models())
    except Exception as exc:
        raise RuntimeError(
            "Impossible de lister les modèles Gemini (vérifiez la clé et le réseau) : "
            f"{exc}"
        ) from exc

    avec_generation: dict[str, str] = {}
    for entree in listed:
        methodes = getattr(entree, "supported_generation_methods", None) or []
        if "generateContent" not in methodes:
            continue
        court = _nom_modele_court(entree.name)
        avec_generation[court] = entree.name

    if not avec_generation:
        raise RuntimeError(
            "Aucun modèle Gemini compatible avec generateContent n'est disponible "
            "pour cette clé API."
        )

    pref = (modele_env or "").strip()
    if pref and pref in avec_generation:
        return pref

    ordre_fallback = (
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-1.5-flash",
        "gemini-1.5-flash-latest",
        "gemini-1.5-flash-002",
        "gemini-1.5-flash-001",
        "gemini-flash-latest",
    )
    for candidat in ordre_fallback:
        if candidat in avec_generation:
            return candidat

    for cle_nom in sorted(avec_generation.keys()):
        if "flash" in cle_nom.lower():
            return cle_nom

    return sorted(avec_generation.keys())[0]


def _historique_gemini(chat_history: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Convertit l'historique Streamlit au format attendu par Gemini (user / model)."""
    historique: list[dict[str, Any]] = []
    for tour in chat_history:
        role = tour.get("role", "")
        texte = (tour.get("content") or "").strip()
        if not texte:
            continue
        if role == "user":
            historique.append({"role": "user", "parts": [texte]})
        elif role == "assistant":
            historique.append({"role": "model", "parts": [texte]})
    return historique


def _messages_groq(
    chat_history: list[dict[str, str]], user_payload: str
) -> list[dict[str, str]]:
    """Historique + dernier message utilisateur (corpus + question) pour l'API Groq."""
    msgs: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    for tour in chat_history:
        role = tour.get("role", "")
        texte = (tour.get("content") or "").strip()
        if not texte:
            continue
        if role == "user":
            msgs.append({"role": "user", "content": texte})
        elif role == "assistant":
            msgs.append({"role": "assistant", "content": texte})
    msgs.append({"role": "user", "content": user_payload})
    return msgs


def _groq_temperature() -> float:
    try:
        return float(os.environ.get("GROQ_TEMPERATURE", "0.3"))
    except ValueError:
        return 0.3


def _groq_modele_defaut() -> str:
    return (os.environ.get("GROQ_MODEL", "") or "").strip() or "llama-3.3-70b-versatile"


def _completer_groq(
    client: Groq,
    modele: str,
    messages: list[dict[str, str]],
    max_tokens: int,
) -> str:
    resp = client.chat.completions.create(
        model=modele,
        messages=messages,
        max_tokens=max_tokens,
        temperature=_groq_temperature(),
    )
    choix = resp.choices[0].message
    return ((choix.content or "") if choix else "").strip()


def _construire_bloc_utilisateur(question: str, sources: list[dict[str, Any]]) -> str:
    context = _format_context(sources)
    consigne_retrieval = ""
    if sources:
        consigne_retrieval = (
            "\n\n[Consigne] Des extraits non vides ont été fournis ci-dessus. "
            "Tu dois répondre à partir de leur contenu (même partiel) avec citations. "
            f"N'utilise la phrase de refus « {PHRASE_REFUS} » uniquement si aucun extrait "
            "ne permet le moindre lien avec la question."
        )
    consigne_format = (
        "\n\n[Format] Réponds avec les sections ### Résumé puis ### Détail "
        "(voir instructions système). Pour la seule phrase de refus, aucune section."
    )
    return (
        "Voici les articles du corpus pouvant être pertinents :\n\n"
        f"{context}\n\n"
        "---\n\n"
        f"Question de l'utilisateur : {question.strip()}"
        f"{consigne_retrieval}"
        f"{consigne_format}"
    )


def _generer_avec_gemini(
    cle: str,
    modele_demande: str | None,
    max_tokens: int,
    chat_history: list[dict[str, str]],
    bloc_utilisateur: str,
) -> tuple[str, Any]:
    genai.configure(api_key=cle)
    modele = _selectionner_modele_gemini(cle, modele_demande)
    generation_config = {"max_output_tokens": max_tokens}
    modele_ia = genai.GenerativeModel(
        model_name=modele,
        system_instruction=SYSTEM_PROMPT,
        generation_config=generation_config,
    )
    historique = _historique_gemini(chat_history)
    chat = modele_ia.start_chat(history=historique)
    reponse = chat.send_message(bloc_utilisateur)
    try:
        texte = (reponse.text or "").strip()
    except ValueError:
        texte = (
            "La réponse du modèle est vide ou a été filtrée par les règles de "
            "sécurité. Reformulez votre question ou vérifiez le corpus."
        )
    return texte, chat


def _generer_avec_groq(
    cle: str,
    modele: str,
    max_tokens: int,
    chat_history: list[dict[str, str]],
    bloc_utilisateur: str,
) -> tuple[str, list[dict[str, str]]]:
    client = Groq(api_key=cle)
    messages = _messages_groq(chat_history, bloc_utilisateur)
    texte = _completer_groq(client, modele, messages, max_tokens)
    return texte, messages


def ask_adala(question: str, chat_history: list[dict[str, str]]) -> dict[str, Any]:
    """
    Pose une question au modèle en s'appuyant sur la recherche vectorielle.

    Retourne : answer / answer_short (résumé), answer_detail (optionnel), sources.
    Fournisseur : ``ADALA_LLM=gemini`` (défaut) ou ``groq`` (``LEXMAROC_LLM`` accepté).
    """
    fournisseur = _fournisseur_llm()
    max_tokens = int(os.environ.get("MAX_TOKENS", "2048"))

    try:
        sources = retrieve(question)
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(
            f"Impossible de récupérer les articles pertinents : {exc}"
        ) from exc

    bloc_utilisateur = _construire_bloc_utilisateur(question, sources)

    if fournisseur == "groq":
        cle_g = _cle_groq()
        if not cle_g:
            raise ValueError(
                "ADALA_LLM=groq (ou LEXMAROC_LLM=groq) : définissez GROQ_API_KEY "
                "(https://console.groq.com/keys)."
            )
        modele_g = _groq_modele_defaut()
        try:
            texte, messages = _generer_avec_groq(
                cle_g, modele_g, max_tokens, chat_history, bloc_utilisateur
            )
        except Exception as exc:
            raise RuntimeError(
                f"Erreur de l'API Groq lors de la génération de la réponse : {exc}"
            ) from exc
        texte = _corriger_refus_abusif_groq(
            cle_g, modele_g, max_tokens, messages, texte, sources
        )
    else:
        cle = _cle_gemini()
        if not cle:
            raise ValueError(
                "Aucune clé API Gemini : définissez GEMINI_API_KEY ou GOOGLE_API_KEY "
                "(ex. clé créée dans Google AI Studio), ou passez à Groq avec "
                "ADALA_LLM=groq (ou LEXMAROC_LLM) et GROQ_API_KEY."
            )
        modele_demande = os.environ.get("GEMINI_MODEL", "").strip() or None
        try:
            texte, chat = _generer_avec_gemini(
                cle, modele_demande, max_tokens, chat_history, bloc_utilisateur
            )
        except Exception as exc:
            raise RuntimeError(
                f"Erreur de l'API Gemini lors de la génération de la réponse : {exc}"
            ) from exc
        texte = _corriger_refus_abusif(chat, texte, sources)

    resume, detail = _parser_resume_detail(texte)
    return {
        "answer": resume,
        "answer_short": resume,
        "answer_detail": detail,
        "sources": sources,
    }


def _extraits_substantiels(sources: list[dict[str, Any]]) -> bool:
    """True si au moins un article contient un minimum de texte exploitable."""
    for s in sources:
        if len((s.get("article_text") or "").strip()) >= 40:
            return True
    return False


def _reponse_est_refus(texte: str) -> bool:
    t = texte.strip()
    return PHRASE_REFUS in t or t == PHRASE_REFUS


def _corriger_refus_abusif(
    chat: Any,
    texte: str,
    sources: list[dict[str, Any]],
) -> str:
    """
    Si le modèle renvoie la phrase de refus alors que des extraits substantiels
    ont été fournis, une seconde consigne réduit les refus erronés.
    """
    if not sources or not _extraits_substantiels(sources):
        return texte
    if not _reponse_est_refus(texte):
        return texte
    relance = (
        "Les extraits juridiques ci-dessus ont été fournis dans ton message précédent "
        "et contiennent du texte. Réponds maintenant en t'appuyant exclusivement sur ces "
        "extraits : résume ce qu'ils établissent concernant la question, avec citations "
        "(nom du code et numéro d'article). Utilise les sections ### Résumé et ### Détail. "
        f"N'écris pas la phrase : « {PHRASE_REFUS} »."
    )
    try:
        reponse2 = chat.send_message(relance)
        t2 = (reponse2.text or "").strip()
        if t2:
            return t2
    except Exception:
        pass
    return texte


def _corriger_refus_abusif_groq(
    cle: str,
    modele: str,
    max_tokens: int,
    messages: list[dict[str, str]],
    texte: str,
    sources: list[dict[str, Any]],
) -> str:
    if not sources or not _extraits_substantiels(sources):
        return texte
    if not _reponse_est_refus(texte):
        return texte
    relance = (
        "Les extraits juridiques ci-dessus ont été fournis dans ton message précédent "
        "et contiennent du texte. Réponds maintenant en t'appuyant exclusivement sur ces "
        "extraits : résume ce qu'ils établissent concernant la question, avec citations "
        "(nom du code et numéro d'article). Utilise les sections ### Résumé et ### Détail. "
        f"N'écris pas la phrase : « {PHRASE_REFUS} »."
    )
    msgs2 = messages + [
        {"role": "assistant", "content": texte},
        {"role": "user", "content": relance},
    ]
    client = Groq(api_key=cle)
    try:
        t2 = _completer_groq(client, modele, msgs2, max_tokens)
        if t2:
            return t2
    except Exception:
        pass
    return texte


# Compatibilité avec l'ancien nom d'API
ask_lexmaroc = ask_adala
