from __future__ import annotations

import json
import os
from typing import Any, Optional

try:
    from langchain.embeddings import OpenAIEmbeddings
    from langchain.schema import Document
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    from langchain.vectorstores import FAISS
except ImportError:
    OpenAIEmbeddings = None
    RecursiveCharacterTextSplitter = None
    FAISS = None
    Document = Any

VECTOR_DB_PATH = "vector_store"


def load_knowledge_documents() -> list[Document]:
    pricing_data = {
        "Standard": [
            {
                "type": "Type 1",
                "price": 1199,
                "duration_seconds": 15,
                "features": [
                    "Single character",
                    "Social media quality",
                    "No script included",
                ],
            },
            {
                "type": "Type 2",
                "price": 1899,
                "duration_seconds": 30,
                "features": [
                    "Single character",
                    "Social media quality",
                    "No motion graphics",
                    "No script included",
                ],
            },
            {
                "type": "Type 3",
                "price": 3999,
                "duration_seconds": 30,
                "features": [
                    "2 characters",
                    "Conversation type",
                    "Single scene",
                    "Social media quality",
                ],
            },
        ],
        "Premium": [
            {
                "type": "Type 5",
                "price": 5499,
                "duration_seconds": 30,
                "features": [
                    "Realistic 3D Product Animation",
                    "Ultra HD",
                ],
            },
            {
                "type": "Type 6",
                "price": 5999,
                "duration_seconds": 30,
                "features": [
                    "Food & Restaurant Animation",
                    "Ultra HD",
                ],
            },
            {
                "type": "Type 7",
                "price": 6999,
                "duration_seconds": 30,
                "features": [
                    "UGC ads",
                    "Ultra HD",
                    "Professional Voiceover",
                ],
            },
            {
                "type": "Type 8A",
                "price": 9999,
                "duration_seconds": 45,
                "features": [
                    "Visual storytelling",
                    "Brand awareness focus",
                ],
            },
            {
                "type": "Type 8B",
                "price": 12999,
                "duration_seconds": 60,
                "features": [
                    "Visual storytelling",
                    "Brand awareness focus",
                    "No motion graphics included",
                ],
            },
        ],
    }

    knowledge_text = (
        "Company Overview:\n"
        "Ilmora Studios is a creative studio focused on high-impact visual content "
        "combining design, motion, and applied AI.\n\n"
        "Services:\n"
        "- Brand Visuals & Creative Direction\n"
        "- Product Visuals & Promotional Content\n"
        "- Motion Graphics & Short Videos\n"
        "- AI Visuals & Cinematic Concepts\n\n"
        "Workflow:\n"
        "Understand -> Create -> Refine -> Deliver\n\n"
        "Target Clients:\n"
        "Startups, brands, influencers, marketing teams.\n\n"
        "Pricing Descriptions:\n"
        f"{json.dumps(pricing_data, indent=2)}"
    )

    return [
        Document(
            page_content=knowledge_text,
            metadata={"source": "ilmora_knowledge_base", "version": "1.0"},
        )
    ]


def build_vector_store() -> Optional[Any]:
    if OpenAIEmbeddings is None or RecursiveCharacterTextSplitter is None or FAISS is None:
        return None

    documents = load_knowledge_documents()
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=100)
    chunks = splitter.split_documents(documents)

    try:
        embeddings = OpenAIEmbeddings()
        vector_store = FAISS.from_documents(chunks, embeddings)
        vector_store.save_local(VECTOR_DB_PATH)
        return vector_store
    except Exception:
        return None


def load_vector_store() -> Optional[Any]:
    if OpenAIEmbeddings is None or FAISS is None:
        return None

    try:
        embeddings = OpenAIEmbeddings()
        if not os.path.exists(VECTOR_DB_PATH):
            return build_vector_store()
        return FAISS.load_local(
            VECTOR_DB_PATH,
            embeddings,
            allow_dangerous_deserialization=True,
        )
    except Exception:
        return None


def retrieve_context(query: str) -> Optional[str]:
    vector_store = load_vector_store()
    if vector_store is None:
        return None

    results = vector_store.similarity_search(query, k=3)
    if not results:
        return None

    context = "\n\n".join(doc.page_content for doc in results)
    return context or None
