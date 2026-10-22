# AI providers

Trellis does not include an AI model. It calls a model provider with your own key, and you pay that
provider directly. You choose the provider in the setup screen. The owner can change it later in
*My profile → Settings → AI provider*.

Trellis uses three models:

| Model | What it does | Cost |
|---|---|---|
| Mentor model | Answers your questions and writes lessons. | The strong (more expensive) model. |
| Extract model | Reads your sources and finds the concepts. | A cheap, fast model. |
| Embedding model | Turns text into numbers, so Trellis can find related concepts. | Very cheap. |

When you click **Next** in the setup screen, Trellis tests all three models with a very small
request. If a key, model name or endpoint is wrong, or your plan has no credit, the screen tells you
what is wrong before you continue.

## The presets

| Preset | Key | Where to get it | Models (mentor / extract / embedding) | Embedding size |
|---|---|---|---|---|
| Google Gemini (recommended) | `GEMINI_API_KEY` | <https://aistudio.google.com/apikey> | `gemini/gemini-3.1-pro-preview` / `gemini/gemini-3.7-flash` / `gemini/gemini-embedding-2-preview` | 3072 |
| OpenAI | `OPENAI_API_KEY` | <https://platform.openai.com/api-keys> | `openai/gpt-5.5` / `openai/gpt-5.5-mini` / `openai/text-embedding-3-large` | 3072 |
| Anthropic Claude | `ANTHROPIC_API_KEY` | <https://console.anthropic.com/settings/keys> | `anthropic/claude-sonnet-5` / `anthropic/claude-haiku-4-5-20251001` / none | from the second provider |
| Mistral | `MISTRAL_API_KEY` | <https://console.mistral.ai/api-keys> | `mistral/mistral-large-latest` / `mistral/mistral-small-latest` / `mistral/mistral-embed` | 1024 |
| Ollama (local, free) | no key | <https://ollama.com/download> | `ollama/qwen3:32b` / `ollama/qwen3:8b` / `ollama/nomic-embed-text` | 768 |

Notes:

- **Gemini** also does voice input and video analysis. The free tier is enough to try Trellis, but
  the strong model often has no free quota ("limit: 0"). Then Trellis offers the Flash model as the
  mentor model, or you add billing in Google AI Studio. Interactive lessons need a paid key.
- **OpenAI**: add a payment method before you create the key. A new account without credit gets
  "quota exceeded" on every call.
- **Anthropic** has no embedding model. The setup screen asks for a second provider (Gemini, OpenAI,
  Mistral or Ollama) and its key, for embeddings only.
- **Ollama** runs on your own computer. Start Ollama and pull the models first:
  `ollama pull qwen3:32b nomic-embed-text`. Trellis reaches it at `http://host.docker.internal:11434`.
  It is slow without a strong GPU, and interactive lessons may fail.
- A key from **Azure** or **Microsoft Foundry** is not an OpenAI key, even when the model is GPT.
  It does not work with the OpenAI preset. Use **Other**, below.

## Other: any provider that LiteLLM supports

Choose **Other** to use a provider without a preset. Trellis uses [LiteLLM](https://docs.litellm.ai/docs/providers),
so every model id has the form `<litellm-provider>/<model>`. You fill in:

| Field | What to type |
|---|---|
| Mentor model, Extract model, Embedding model | LiteLLM model ids, for example `azure/my-gpt-deployment`. |
| Embedding size | The vector size of the embedding model (see below). |
| Key variable | The name LiteLLM uses for the key, for example `AZURE_API_KEY`. |
| Key | The key itself. |
| Endpoint | Only when the provider needs one: the base URL of your resource. |
| API version | Only for Azure OpenAI. |

One key is used for all three models, so the embedding model must come from the same provider.

### Azure OpenAI

In the Azure portal, open your Azure OpenAI resource. You need a **deployment** for each model.
The deployment name is the name you gave it, not the model name.

| Field | Value |
|---|---|
| Mentor model | `azure/<your-gpt-deployment>` |
| Extract model | `azure/<your-small-gpt-deployment>` (or the same deployment) |
| Embedding model | `azure/<your-embedding-deployment>` |
| Embedding size | 3072 for `text-embedding-3-large`, 1536 for `text-embedding-3-small` |
| Key variable | `AZURE_API_KEY` |
| Key | *Keys and Endpoint* → KEY 1 |
| Endpoint | `https://<resource>.openai.azure.com` |
| API version | An Azure OpenAI API version that your resource supports, for example `2024-10-21` |

### Microsoft Foundry (Azure AI Foundry)

Foundry projects use the Azure AI model inference endpoint. Deploy a chat model and an embedding
model in your Foundry resource first.

| Field | Value |
|---|---|
| Mentor model | `azure_ai/<your-chat-deployment>` |
| Extract model | `azure_ai/<your-small-chat-deployment>` (or the same deployment) |
| Embedding model | `azure_ai/<your-embedding-deployment>` |
| Embedding size | 3072 for `text-embedding-3-large`, 1536 for `text-embedding-3-small`; for other models, see the model card |
| Key variable | `AZURE_AI_API_KEY` |
| Key | The key of your Foundry resource |
| Endpoint | `https://<resource>.services.ai.azure.com/models` |
| API version | empty |

If the test says "wrong model, deployment or endpoint", check the deployment names (they are case
sensitive) and that the endpoint ends in `/models`.

### OpenRouter

OpenRouter gives one key for models from many vendors: <https://openrouter.ai/keys>.

| Field | Value |
|---|---|
| Mentor model | `openrouter/<vendor>/<model>`, for example `openrouter/anthropic/claude-sonnet-5` |
| Extract model | a cheap model, for example `openrouter/google/gemini-3.7-flash` |
| Embedding model | an embedding model that OpenRouter offers, for example `openrouter/openai/text-embedding-3-large` |
| Embedding size | the size of that embedding model (3072 for `text-embedding-3-large`) |
| Key variable | `OPENROUTER_API_KEY` |
| Endpoint | empty |

The model ids on OpenRouter change often. Copy them from the model page on openrouter.ai. If the
embedding test fails, OpenRouter does not offer that embedding model for your account: use a preset
provider instead.

## Embedding size: choose once

Trellis stores one vector per concept and per source excerpt, and the database index has a fixed
vector size. Trellis sets that size at the first setup, from the embedding model you choose. You
**cannot change the embedding size later**: vectors of a different size do not fit in the index, and
the vectors of different models cannot be compared, even when they have the same size.

You can change the mentor model, the extract model and the key at any time. Trellis refuses a new
embedding model with a different size. It accepts one with the same size, but then old and new
vectors do not compare well. Change the embedding model only to the same model through another
route, for example `text-embedding-3-large` from OpenAI to the same model on Azure.

Common sizes:

| Embedding model | Size |
|---|---|
| OpenAI / Azure `text-embedding-3-large` | 3072 |
| OpenAI / Azure `text-embedding-3-small` | 1536 |
| Gemini `gemini-embedding-2-preview` | 3072 |
| Mistral `mistral-embed` | 1024 |
| Ollama `nomic-embed-text` | 768 |

If the size is wrong, the setup test tells you the size that the model really returns.

## Keys in a file instead of the setup screen

On a server you can put the keys in `.env` instead (see `.env.example`), for example
`OPENAI_API_KEY=...`, and restart with `docker compose up -d`. A key in `.env` is used when the
setup screen has no key for that provider.
