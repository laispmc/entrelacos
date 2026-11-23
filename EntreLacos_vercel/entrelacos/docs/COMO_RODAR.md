# Como rodar o EntreLaços

Este guia cobre três situações: rodar no seu computador, publicar na Vercel e rodar os testes.
Os comandos são executados na pasta do projeto, onde fica o arquivo `main.py`.

---

## 1. No seu computador

Pré-requisito: **Python 3.11 ou mais recente**.

```bash
# 1. Entrar na pasta do projeto
cd entrelacos

# 2. Criar e ativar o ambiente virtual
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # Linux / macOS

# 3. Instalar as dependências
pip install -r requirements.txt

# 4. Criar o arquivo .env a partir do exemplo
copy .env.example .env          # Windows
cp .env.example .env            # Linux / macOS
```

Abra o `.env` e troque `SECRET_KEY` por uma chave aleatória. Para gerar uma:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

```bash
# 5. Criar o administrador (a senha é pedida duas vezes e não aparece ao digitar)
flask --app main criar-admin

# 6. (Opcional) Cadastrar três eventos de exemplo
flask --app main popular

# 7. Iniciar o servidor
flask --app main run
```

Acesse **http://127.0.0.1:5000**. A área administrativa fica em **http://127.0.0.1:5000/admin/login**.

Localmente o banco é um SQLite criado sozinho em `instance/entrelacos.db` na primeira execução.

Esqueceu a senha? Defina uma nova pelo terminal:

```bash
flask --app main redefinir-senha
```

> No terminal do Windows, colar com Ctrl+V no campo de senha pode não funcionar. Digite a senha.

---

## 2. Publicar na Vercel

A Vercel executa o Flask como uma função serverless. Duas consequências que o código já trata:

- **O disco não é permanente.** Por isso os dados precisam ficar num banco **PostgreSQL** externo
  e as imagens de capa dos eventos são guardadas dentro do próprio banco (não em uma pasta).
- **Não há terminal.** Por isso o primeiro administrador pode ser criado por variáveis de ambiente.

### Passo a passo

1. **Suba o projeto para um repositório no GitHub.** Atenção: envie o **conteúdo** da pasta `entrelacos`,
   não a pasta em si. Na página do repositório, `main.py`, `requirements.txt`, `app/` e `public/` precisam
   aparecer logo no primeiro nível.
   Se o repositório ficou com tudo dentro de uma subpasta, não tem problema: na Vercel, em
   *Settings → Build and Deployment → Root Directory*, informe o nome dessa subpasta.

   > O upload pelo site do GitHub pode ignorar arquivos que começam com ponto (`.gitignore`, `.vercelignore`,
   > `.python-version`, `.env.example`). O site funciona sem eles, mas pelo GitHub Desktop ou pelo `git`
   > eles vão junto.

2. **Importe o repositório na Vercel:** em vercel.com → *Add New… → Project* → escolha o repositório.
   O framework é detectado como **Flask** automaticamente (a Vercel procura a variável `app` em `main.py`).
   Não é preciso mudar *Build Command* nem *Output Directory*.

3. **Crie o banco PostgreSQL:** no projeto da Vercel, aba **Storage → Create Database → Neon (Postgres)**
   e conecte ao projeto. Isso cria a variável `DATABASE_URL` sozinha.
   (Se preferir outro provedor, como Supabase, copie a connection string e cadastre como `DATABASE_URL`.)

4. **Cadastre as variáveis de ambiente** em *Settings → Environment Variables*:

   | Variável | Valor | Obrigatória |
   |---|---|---|
   | `SECRET_KEY` | uma chave aleatória longa (gere com o comando acima) | sim |
   | `DATABASE_URL` | connection string do Postgres (criada no passo 3) | sim |
   | `ADMIN_EMAIL` | e-mail do primeiro administrador | sim, no 1º deploy |
   | `ADMIN_SENHA` | senha do primeiro administrador (mín. 8 caracteres) | sim, no 1º deploy |
   | `ADMIN_NOME` | nome exibido do administrador | não |

   `FLASK_CONFIG` não precisa ser definida: na Vercel o modo de produção é escolhido automaticamente.

5. **Faça o deploy** (botão *Deploy*, ou um novo *push* no GitHub). Na primeira requisição o sistema cria as
   tabelas no Postgres e o administrador definido em `ADMIN_EMAIL`/`ADMIN_SENHA`.

6. Acesse `https://SEU-PROJETO.vercel.app/admin/login` e entre com esse e-mail e senha.

> Depois que o administrador existir, você pode apagar `ADMIN_SENHA` das variáveis da Vercel.
> Ele não é recriado nem tem a senha alterada se a variável continuar lá.

### Eventos de exemplo no banco da Vercel (opcional)

O comando `popular` roda no seu computador, mas pode gravar direto no Postgres da Vercel.
No `.env` local, coloque temporariamente a mesma `DATABASE_URL` da Vercel e rode:

```bash
flask --app main popular
```

O mesmo vale para `criar-admin` e `redefinir-senha` (útil para trocar a senha do administrador em produção).
Depois remova a `DATABASE_URL` do `.env` para voltar a usar o SQLite local.

### Se algo der errado

- **Erro 500 logo ao abrir:** veja *Deployments → (o deploy) → Logs*. A causa mais comum é `SECRET_KEY`
  ou `DATABASE_URL` não cadastrada.
- **Os dados somem depois de um tempo:** a `DATABASE_URL` não está definida e o sistema está usando um
  SQLite temporário. Faça o passo 3.
- **Mudou uma variável e nada aconteceu:** variáveis novas só valem a partir do próximo deploy
  (*Deployments → ⋯ → Redeploy*).

---

## 3. Testes automatizados

Os testes não são enviados para a Vercel (estão listados no `.vercelignore`). Para rodar no computador:

```bash
pip install -r requirements-dev.txt
pytest
```

Os testes usam um banco SQLite **em memória**, então não alteram nenhum dado real. São 37 casos.
