# EntreLaços

Plataforma web para organizar campanhas de doação de eventos beneficentes, comunitários e sociais.

Organizadores cadastram eventos e a lista de itens necessários. Visitantes escolhem o que podem doar,
montam um carrinho e confirmam com nome e telefone, sem criar conta. As quantidades ficam reservadas na hora,
para que a soma das doações nunca passe da necessidade. Depois, o organizador registra as entregas,
inclusive parciais, e acompanha tudo por um painel.

## Funcionalidades

**Para quem doa**
- Página inicial com os eventos abertos (e seção separada de eventos encerrados)
- Página do evento com itens, quantidade necessária, prometida e disponível
- Carrinho vinculado a um evento: adicionar, alterar quantidade, remover
- Confirmação com nome completo, telefone e observação opcional
- Consulta das doações do evento por nome ou telefone, com situação por item (o telefone nunca é exibido)

**Para quem organiza**
- Login com senha armazenada em hash
- Cadastro e edição de eventos com imagem de capa
- Cadastro, edição e desativação de itens
- Lista de doações com filtros por evento, situação e doador
- Checklist de recebimento: várias entregas por doação, recebimento parcial e cancelamento do que falta
- Painel com indicadores gerais e progresso por evento

## Tecnologias

Python 3.11+ · Flask · SQLAlchemy (Flask-SQLAlchemy) · SQLite (local) / PostgreSQL (produção) ·
Flask-WTF / WTForms · Flask-Login · Jinja2 · Bootstrap 5 · HTML5 / CSS3 / JavaScript · pytest ·
python-dotenv · Vercel

## Estrutura

```
entrelacos/
├── app/
│   ├── __init__.py          # create_app(): fábrica da aplicação
│   ├── extensions.py        # db, csrf, login_manager
│   ├── models.py            # tabelas e relacionamentos (ORM)
│   ├── forms.py             # formulários e validações (WTForms)
│   ├── commands.py          # comandos: criar-admin / redefinir-senha / popular
│   ├── utils.py             # telefone, datas, formatação
│   ├── blueprints/
│   │   ├── public.py        # página inicial e páginas institucionais
│   │   ├── eventos.py       # página do evento e gerenciamento de eventos/itens
│   │   ├── doacoes.py       # carrinho, confirmação e consulta
│   │   └── admin.py         # login, painel e gestão das doações
│   ├── services/            # regras de negócio (sem dependência das rotas)
│   │   ├── carrinho.py
│   │   ├── doacoes.py       # confirmação em transação única
│   │   ├── recebimentos.py  # recebimento parcial e cancelamento
│   │   ├── eventos.py       # validação da imagem de capa
│   │   └── dashboard.py     # consultas com agregação
│   └── templates/
├── public/static/           # css, js e img (servidos pela CDN na Vercel)
├── docs/                    # documentação, diagrama ER, modelo físico, SQL, guia do código
├── tests/                   # testes com pytest (banco em memória)
├── config.py                # configurações por ambiente
├── main.py                  # ponto de entrada (detectado pela Vercel)
├── requirements.txt         # dependências do site
├── requirements-dev.txt     # + pytest
├── .vercelignore            # o que não vai para a Vercel (docs, testes)
└── .env.example
```

## Como executar

Pré-requisito: **Python 3.11 ou mais recente** instalado.

```bash
# 1. Criar e ativar o ambiente virtual
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # Linux / macOS

# 2. Instalar as dependências
pip install -r requirements.txt

# 3. Criar o arquivo .env a partir do exemplo
copy .env.example .env          # Windows
cp .env.example .env            # Linux / macOS
```

Abra o `.env` e troque `SECRET_KEY` por uma chave aleatória. Para gerar uma:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

```bash
# 4. Criar o administrador (a senha é pedida duas vezes e não aparece ao digitar)
flask --app main criar-admin

# 5. (Opcional) Cadastrar três eventos de exemplo
flask --app main popular

# 6. Iniciar o servidor
flask --app main run
```

Acesse **http://127.0.0.1:5000**. A área administrativa fica em **http://127.0.0.1:5000/admin/login**.

Localmente o banco SQLite é criado automaticamente em `instance/entrelacos.db` na primeira execução.

Esqueceu a senha ou não consegue entrar? Defina uma nova pelo terminal:

```bash
flask --app main redefinir-senha
```

> No terminal do Windows, colar com Ctrl+V no campo de senha pode não funcionar. Digite a senha.

## Publicar na Vercel

1. Envie o projeto para o GitHub com `main.py`, `requirements.txt`, `app/` e `public/` **na raiz do repositório**
   (se ficarem dentro de uma subpasta, informe essa subpasta em *Settings → Build and Deployment → Root Directory*).
2. Na Vercel, importe o repositório. O Flask é detectado automaticamente.
3. Em **Storage**, crie um banco **Neon (Postgres)** e conecte ao projeto. Isso cria a `DATABASE_URL`.
4. Em **Settings → Environment Variables**, cadastre:

   | Variável | Valor |
   |---|---|
   | `SECRET_KEY` | chave aleatória longa |
   | `ADMIN_EMAIL` | e-mail do primeiro administrador |
   | `ADMIN_SENHA` | senha do primeiro administrador (mínimo 8 caracteres) |
   | `ADMIN_NOME` | nome exibido no painel (opcional) |

5. Faça o deploy (ou *Deployments → ⋯ → Redeploy* se mudou variáveis) e acesse `/admin/login`.

Na Vercel o disco não é permanente, por isso os dados ficam no PostgreSQL e as imagens de capa são guardadas
no próprio banco. Detalhes e solução de problemas em [docs/COMO_RODAR.md](docs/COMO_RODAR.md).

## Testes

```bash
pip install -r requirements-dev.txt
pytest
```

Os testes usam um banco SQLite **em memória** (configuração `TestingConfig`), então não alteram os dados reais.
São 37 casos, entre eles:

| Teste | Resultado esperado |
|---|---|
| Acessar página inicial | Lista os eventos abertos |
| Consultar evento existente | Exibe detalhes e itens |
| Confirmar doação válida | Registra a doação e reserva as quantidades |
| Confirmar doação sem nome | Formulário rejeitado |
| Telefone inválido | Formulário rejeitado |
| Doar mais que o disponível | Confirmação impedida |
| Dois doadores disputando o mesmo item | Segunda confirmação recusada por inteiro |
| Registrar recebimento parcial | Atualiza a quantidade recebida |
| Cadastrar evento com imagem | Capa salva no banco e servida pela rota própria |
| Recebimento maior que o prometido | Operação impedida |
| Registrar o mesmo recebimento duas vezes | Segundo envio recusado |
| Cancelar quantidade pendente | Libera só o que não foi recebido |
| Rota administrativa sem login | Redireciona para o login |
| Doar em evento encerrado | Contribuição impedida |

## Segurança e boas práticas

- `SECRET_KEY`, senha do banco e do administrador ficam no `.env` (fora do Git) ou nas variáveis da Vercel; o repositório traz apenas o `.env.example`
- Senhas com hash (`werkzeug.security`)
- Proteção CSRF em todos os formulários (Flask-WTF)
- Validação no servidor; o JavaScript só melhora a usabilidade
- Upload de imagem validado por extensão, tamanho (3 MB) e conteúdo real do arquivo
- Telefones nunca aparecem nas páginas públicas
- Logs de logins, doações, recebimentos e erros no terminal (local) ou em *Logs* (Vercel)
- Páginas de erro amigáveis (404, 403, 413, 500 e formulário expirado)

## Documentação

- [Documentação técnica](docs/DOCUMENTACAO.md) ([PDF](docs/DOCUMENTACAO.pdf))
- [Explicação geral do código](docs/EXPLICACAO_DO_CODIGO.md) ([PDF](docs/EXPLICACAO_DO_CODIGO.pdf))
- [Como rodar e publicar](docs/COMO_RODAR.md)
- [Modelo físico do banco](docs/modelo_fisico.md) e [diagrama ER](docs/diagrama_er.png)
- [Script SQL das tabelas](docs/schema.sql) (SQLite) e [versão PostgreSQL](docs/schema_postgres.sql)
