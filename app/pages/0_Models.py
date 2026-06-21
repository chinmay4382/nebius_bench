"""Models — guide to gated vs open models, license acceptance, and HF token setup."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

st.set_page_config(
    page_title="Models · Nebius Endpoint Lab",
    page_icon="🤗",
    layout="wide",
)

st.title("🤗 Models Guide")
st.caption("Everything you need to know about open vs gated models, license acceptance, and HuggingFace tokens")
st.divider()


# ── What is HuggingFace ────────────────────────────────────────────────────────

st.header("What is HuggingFace?")

col_info, col_stat = st.columns([3, 1])

with col_info:
    st.markdown("""
[HuggingFace](https://huggingface.co) is the central hub where AI researchers and companies publish open-weight language models.
Think of it as the GitHub of AI — every major model release (Meta's Llama, Google's Gemma, Mistral, Qwen, DeepSeek, and more)
is distributed through HuggingFace as a public repository containing model weights, tokenizer files, and configuration.

**Every model deployed by this app comes from HuggingFace.**

When you click *Create Endpoint*, Nebius spins up a GPU VM and the inference container
(vLLM or SGLang) pulls the model weights directly from `huggingface.co` onto the attached disk
before serving. This means:

- You need a HuggingFace account to access **gated** models
- The disk size you set must be large enough to hold the downloaded weights
- Download speed depends on HuggingFace CDN — large models (70B+) can take several minutes
""")

with col_stat:
    st.metric("Models on HuggingFace", "1M+")
    st.metric("Monthly active users", "5M+")
    st.metric("Model downloads / month", "2B+")

st.info(
    "**New to HuggingFace?** Create a free account at [huggingface.co/join](https://huggingface.co/join). "
    "You only need an account to access gated models — open models deploy without any login.",
    icon="💡",
)

st.divider()


# ── Open vs Gated ─────────────────────────────────────────────────────────────

st.header("Model Access: Open vs Gated")
st.markdown(
    "Because all models come from HuggingFace, their access policy is controlled there. "
    "Models fall into two categories:"
)

col_open, col_gated = st.columns(2)

with col_open:
    st.subheader("🔓 Open Models")
    st.markdown("""
No token required. Download and deploy instantly.

**Examples:**
| Model | Publisher |
|---|---|
| Mistral 7B Instruct v0.3 | Mistral AI |
| Qwen 2.5 7B / 72B | Alibaba |
| Qwen 3 14B / 235B | Alibaba |
| DeepSeek-R1 (all sizes) | DeepSeek |
| Mixtral 8x7B | Mistral AI |
| All NVIDIA models | NVIDIA |

These models use permissive licenses (Apache 2.0, MIT, or custom open licenses) that require no gate.
""")

with col_gated:
    st.subheader("🔒 Gated Models")
    st.markdown("""
Require license acceptance + HuggingFace token.

**Examples:**
| Model | Publisher | Reason |
|---|---|---|
| Llama 3.1 / 3.2 / 3.3 | Meta | Meta Community License |
| Llama 4 Scout / Maverick | Meta | Meta Community License |
| Gemma 3 4B / 27B | Google | Gemma Terms of Use |
| Phi-4 / Phi-4 Mini | Microsoft | Microsoft Research License |

HuggingFace uses gating to ensure users read and agree to specific usage terms before accessing the weights.
""")

st.divider()


# ── Step 1: Accept the license ────────────────────────────────────────────────

st.header("Step 1 — Accept the Model License")

st.markdown("Do this **once per model** on HuggingFace. Your acceptance is tied to your HF account.")

with st.expander("▶  How to accept (click to expand)", expanded=True):
    st.markdown("""
1. **Log in** to [huggingface.co](https://huggingface.co) with your account.

2. **Go to the model page** for the model you want to use. Use the links below or search on HuggingFace.

3. You will see a banner like this at the top of the page:

   > *"You need to agree to share your contact information to access this model."*

   or

   > *"This model is gated. You need to accept the license to access it."*

4. **Click "Agree and access repository"** and fill in the short form (name, org, intended use).

5. HuggingFace will review instantly (automated for most models) and grant access.
   You'll see a green **"You have been granted access"** confirmation.

6. That's it — your HF token now has permanent access to this model.
""")

st.markdown("**Quick links to common gated model pages:**")

links = {
    "meta-llama/Llama-3.1-8B-Instruct":        "Llama 3.1 8B",
    "meta-llama/Llama-3.3-70B-Instruct":        "Llama 3.3 70B",
    "meta-llama/Llama-4-Scout-17B-16E-Instruct": "Llama 4 Scout",
    "meta-llama/Llama-4-Maverick-17B-128E-Instruct": "Llama 4 Maverick",
    "google/gemma-3-4b-it":                     "Gemma 3 4B",
    "google/gemma-3-27b-it":                    "Gemma 3 27B",
    "microsoft/Phi-4":                          "Phi-4 14B",
    "microsoft/Phi-4-mini-instruct":            "Phi-4 Mini",
}

cols = st.columns(4)
for i, (model_id, label) in enumerate(links.items()):
    cols[i % 4].link_button(label, f"https://huggingface.co/{model_id}", use_container_width=True)

st.divider()


# ── Step 2: Generate HF token ─────────────────────────────────────────────────

st.header("Step 2 — Generate a HuggingFace Token")

with st.expander("▶  How to create a token (click to expand)", expanded=True):
    st.markdown("""
1. Go to **[huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)**.

2. Click **"New token"**.

3. Give it a name (e.g. `nebius-endpoint-lab`).

4. Set the role to **"Read"** — that's all this app needs.

5. Click **"Generate a token"** and copy it immediately.
   *(It starts with `hf_` and won't be shown again.)*

6. Store it somewhere safe — a password manager or your `.env` file.
""")

    st.info("A **Read** token is sufficient. Write/Admin tokens work too but are unnecessary for model deployment.")

st.divider()


# ── Step 3: Add token to the app ──────────────────────────────────────────────

st.header("Step 3 — Add the Token to This App")

st.markdown("Two ways — pick whichever suits you:")

tab_env, tab_ui = st.tabs(["Option A: .env file (persistent)", "Option B: Paste in UI (per session)"])

with tab_env:
    st.markdown("""
**Best for:** local development where you always use the same token.

1. Open (or create) the `.env` file in the project root:
   ```
   nebius_bench/.env
   ```

2. Add this line:
   ```
   HUGGING_FACE_HUB_TOKEN=hf_xxxxxxxxxxxxxxxxxxxx
   ```

3. Save and **restart the Streamlit app**:
   ```bash
   streamlit run app/Home.py
   ```

4. The token is now loaded automatically — you won't need to paste it on the Deploy page.

> **Note:** `.env` is in `.gitignore` and never committed. Keep it out of version control.
""")

with tab_ui:
    st.markdown("""
**Best for:** one-off deployments or shared environments.

1. Go to the **Deploy & Run** page.

2. Select your model (gated models show a ⚠️ Required label on the token field).

3. Paste your `hf_xxxx…` token into the **HuggingFace Token** field.

4. Click **🚀 Create Endpoint** — the token is sent at creation time and not stored beyond the session.

> **Note:** If the token field is empty on a gated model, the Create Endpoint button stays disabled.
""")

st.divider()


# ── Troubleshooting ────────────────────────────────────────────────────────────

st.header("Troubleshooting")

with st.expander("Endpoint fails with 'Access to model is restricted'"):
    st.markdown("""
- You haven't accepted the license for this specific model. Go to the model page on HuggingFace and accept it.
- You accepted the license but used a **different HF account** than the one your token belongs to. Make sure the token and the accepted license are from the same account.
""")

with st.expander("Endpoint fails with 'Invalid token' or '401 Unauthorized'"):
    st.markdown("""
- The token was copied incorrectly (missing `hf_` prefix, extra spaces). Re-copy it from [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens).
- The token was deleted or revoked. Generate a new one.
- You set `HUGGING_FACE_HUB_TOKEN` in `.env` but restarted the app before saving. Restart again after saving.
""")

with st.expander("I accepted the license but the endpoint still fails"):
    st.markdown("""
- License acceptance can take a few seconds to propagate on HuggingFace's side. Wait 30s and retry.
- Some models (e.g. Llama 4) require Meta to manually approve access. Check your HF notifications for an approval email.
- Verify access by running this in a terminal:
  ```bash
  python -c "from huggingface_hub import whoami; print(whoami())"
  ```
  Then check the model page — it should say "You have been granted access".
""")

with st.expander("HuggingFace Search shows a model as gated=False but it actually requires a token"):
    st.markdown("""
This can happen with models that are newly gated or whose gated status is cached.
The `gated` field comes directly from the HuggingFace API — refresh the page or re-search after a few minutes.
If in doubt, check the model's page directly on HuggingFace.
""")

st.divider()


# ── HuggingFace Model Search ───────────────────────────────────────────────────

def _hf_size_to_disk(size_bytes: int | None) -> str:
    if not size_bytes:
        return "250Gi"
    gb = size_bytes / 1_073_741_824
    padded = gb * 1.3
    if padded <= 120:
        return "120Gi"
    if padded <= 200:
        return f"{int(padded // 10 * 10 + 10)}Gi"
    if padded <= 500:
        return f"{int(padded // 50 * 50 + 50)}Gi"
    if padded <= 1024:
        return "1Ti"
    return "2Ti"


def _params_from_model(model: Any) -> float | None:
    if hasattr(model, "safetensors") and model.safetensors and hasattr(model.safetensors, "total"):
        return model.safetensors.total / 1e9
    return None


def _size_bytes_from_model(model: Any) -> int | None:
    if hasattr(model, "safetensors") and model.safetensors and hasattr(model.safetensors, "total"):
        return model.safetensors.total * 2
    return None


@st.cache_data(ttl=120, show_spinner=False)
def _search_hf(query: str, limit: int = 20) -> list[dict[str, Any]]:
    from huggingface_hub import list_models
    results = list(list_models(
        search=query or None,
        pipeline_tag="text-generation",
        sort="downloads",
        limit=limit,
        expand=["safetensors", "downloads", "likes", "gated"],
    ))
    rows: list[dict[str, Any]] = []
    for m in results:
        params = _params_from_model(m)
        size_bytes = _size_bytes_from_model(m)
        disk = _hf_size_to_disk(size_bytes)
        is_gated = bool(m.gated) if hasattr(m, "gated") and m.gated else False
        publisher, _, model_name = m.id.partition("/")
        rows.append({
            "_model_id":    m.id,
            "Model":        model_name or m.id,
            "Publisher":    publisher,
            "Parameters":   f"{params:.1f}B" if params else "—",
            "Est. Disk":    disk,
            "Downloads":    getattr(m, "downloads", 0) or 0,
            "Likes":        getattr(m, "likes", 0) or 0,
            "Access":       "🔒 Gated" if is_gated else "🔓 Open",
        })
    return rows


st.header("🔍 Explore Models on HuggingFace")
st.markdown(
    "Search the HuggingFace hub for text-generation models. "
    "See parameter counts, estimated disk requirements, and access requirements at a glance — "
    "then deploy directly from the **Deploy & Run** page."
)

search_col, btn_col = st.columns([5, 1])
with search_col:
    hf_query = st.text_input(
        "Search HuggingFace",
        placeholder="e.g. Llama, Qwen, Mistral, DeepSeek, Phi…",
        label_visibility="collapsed",
    )
with btn_col:
    search_clicked = st.button("Search", use_container_width=True, type="primary")

_default_searches = ["Llama", "Qwen", "Mistral", "DeepSeek", "Gemma"]
_default_tabs = st.tabs([f"🔥 {q}" for q in _default_searches] + ["🔎 Results"])

_show_query = hf_query.strip() if hf_query else None

for i, (tab, q) in enumerate(zip(_default_tabs[:-1], _default_searches)):
    with tab:
        try:
            with st.spinner(f"Loading top {q} models…"):
                tab_results = _search_hf(q, limit=15)
            if tab_results:

                df = pd.DataFrame(tab_results).drop(columns=["_model_id"])
                df["Downloads"] = df["Downloads"].apply(lambda x: f"{x:,}")
                df["Likes"]     = df["Likes"].apply(lambda x: f"{x:,}")
                st.dataframe(df, use_container_width=True, hide_index=True)

                chosen_name = st.selectbox(
                    "Select a model to view details",
                    ["—"] + [r["Model"] for r in tab_results],
                    key=f"tab_sel_{i}",
                )
                if chosen_name != "—":
                    chosen = next((r for r in tab_results if r["Model"] == chosen_name), None)
                    if chosen:
                        with st.container(border=True):
                            d1, d2, d3, d4 = st.columns(4)
                            d1.metric("Publisher",  chosen["Publisher"])
                            d2.metric("Parameters", chosen["Parameters"])
                            d3.metric("Est. Disk",  chosen["Est. Disk"])
                            d4.metric("Access",     chosen["Access"])
                            link_col, deploy_col, _ = st.columns([2, 2, 4])
                            link_col.link_button(
                                "Open on HuggingFace",
                                f"https://huggingface.co/{chosen['_model_id']}",
                                use_container_width=True,
                            )
                            with deploy_col:
                                st.page_link(
                                    "pages/1_Deploy_and_Run.py",
                                    label="🚀 Deploy & Run",
                                    use_container_width=True,
                                )
            else:
                st.info("No results found.")
        except Exception as exc:
            st.error(f"HuggingFace API error: {exc}")

with _default_tabs[-1]:
    if _show_query:
        try:
            with st.spinner(f"Searching for **{_show_query}**…"):
                search_results = _search_hf(_show_query, limit=25)
            if search_results:

                df_s = pd.DataFrame(search_results).drop(columns=["_model_id"])
                df_s["Downloads"] = df_s["Downloads"].apply(lambda x: f"{x:,}")
                df_s["Likes"]     = df_s["Likes"].apply(lambda x: f"{x:,}")
                st.caption(f"Found {len(search_results)} models for **{_show_query}**")
                st.dataframe(df_s, use_container_width=True, hide_index=True)

                chosen_s = st.selectbox(
                    "Select a model to view details",
                    ["—"] + [r["Model"] for r in search_results],
                    key="search_sel",
                )
                if chosen_s != "—":
                    chosen = next((r for r in search_results if r["Model"] == chosen_s), None)
                    if chosen:
                        with st.container(border=True):
                            s1, s2, s3, s4 = st.columns(4)
                            s1.metric("Publisher",  chosen["Publisher"])
                            s2.metric("Parameters", chosen["Parameters"])
                            s3.metric("Est. Disk",  chosen["Est. Disk"])
                            s4.metric("Access",     chosen["Access"])
                            sl_col, sd_col, _ = st.columns([2, 2, 4])
                            sl_col.link_button(
                                "Open on HuggingFace",
                                f"https://huggingface.co/{chosen['_model_id']}",
                                use_container_width=True,
                            )
                            with sd_col:
                                st.page_link(
                                    "pages/1_Deploy_and_Run.py",
                                    label="🚀 Deploy & Run",
                                    use_container_width=True,
                                )
            else:
                st.info(f"No text-generation models found for **{_show_query}**.")
        except Exception as exc:
            st.error(f"HuggingFace API error: {exc}")
    else:
        st.info("Type a model name above and click **Search** to explore the full HuggingFace catalogue.")
