## ⚡ Pré-requisitos

- Python 3.11+  
- [API Key do Gemini](https://ai.google.dev/) (crie um projeto no Google AI Studio)  

---

## 📦 Instalação

Clone o repositório e crie um ambiente virtual:

```bash
git clone <seu-repo>
cd API-VI-AI

python -m venv venv
source venv/bin/activate   # Mac/Linux
venv\Scripts\activate      # Windows
````

Instale as dependências:

```bash
pip install -r requirements.txt
```

---

## 🔑 Configuração

Crie um arquivo `.env` na raiz com sua chave Gemini:

```env
GEMINI_API_KEY=coloque_sua_chave_aqui
```

---

## 🚀 Execute o servidor

```bash
uvicorn app:app --reload --port 8001
```

Acesse a documentação interativa:
👉 [http://127.0.0.1:8001/docs](http://127.0.0.1:8001/docs)

---

## 📝 Exemplos de uso

### Verifique se está online

```bash
curl http://127.0.0.1:8001/
```

### Fazer uma pergunta

```bash
curl -X POST "http://127.0.0.1:8001/responder" \
     -H "Content-Type: application/json" \
     -d '{"pergunta": "Quais alimentos são ricos em proteínas?"}'
```

Exemplo de resposta esperada:

```json 
{
  "resposta": "Alimentos ricos em proteínas incluem ovos, peixes, carnes magras, feijão, lentilha e grão-de-bico."
}
```

---

## 📂 Estrutura do projeto

```
API-VI-AI/
├── app.py             # Ponto de entrada do FastAPI
├── agent_config.py   # Configuração do modelo Gemini
├── routes.py          # Rotas da API
├── .env               # Sua chave GEMINI_API_KEY
├── requirements.txt   # Dependências
└── venv/              # Ambiente virtual
```
