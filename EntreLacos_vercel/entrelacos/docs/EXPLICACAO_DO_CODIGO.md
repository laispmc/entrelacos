# EntreLaços — Explicação geral do código

Guia de estudo para entender o sistema e apresentá-lo. A ordem segue o caminho de uma requisição:
do ponto de entrada até o banco de dados, e depois as regras de negócio mais importantes.

---

## 1. O que o sistema faz, em uma frase

Organizadores cadastram **eventos** com a lista de **itens** de que precisam; visitantes escolhem o que vão
doar num **carrinho**, confirmam com nome e telefone (sem criar conta), e o organizador depois registra o que
foi **entregue**, inclusive em partes. Tudo isso sem que a soma das doações passe da quantidade necessária.

## 2. Mapa das pastas

```
entrelacos/
├── main.py              ← ponto de entrada (a Vercel procura a variável `app` aqui)
├── config.py            ← configurações por ambiente (desenvolvimento, testes, produção)
├── requirements.txt     ← bibliotecas Python
├── .env.example         ← modelo das variáveis de ambiente
├── public/static/       ← CSS, JavaScript e logo (servidos pela CDN na Vercel)
├── docs/                ← documentação, diagramas e este guia (não vão para a Vercel)
├── tests/               ← testes automatizados com pytest
└── app/
    ├── __init__.py      ← create_app(): monta a aplicação
    ├── extensions.py    ← db (banco), csrf (segurança de formulários), login_manager
    ├── models.py        ← tabelas do banco como classes Python
    ├── forms.py         ← formulários e suas validações
    ├── commands.py      ← comandos de terminal (criar-admin, redefinir-senha, popular)
    ├── utils.py         ← telefone, datas e números formatados
    ├── blueprints/      ← ROTAS (cada arquivo é um grupo de páginas)
    ├── services/        ← REGRAS DE NEGÓCIO (sem HTML, sem request)
    └── templates/       ← páginas HTML (Jinja2)
```

A ideia central da organização é **separar responsabilidades em camadas**:

```
Navegador → Blueprint (rota) → Form (valida) → Service (regra) → Model (banco)
                 ↓
             Template (HTML de resposta)
```

- A **rota** só recebe a requisição, chama quem sabe resolver e escolhe a página de resposta.
- O **formulário** confere se os dados de entrada são válidos (nome com sobrenome, telefone com DDD…).
- O **service** aplica as regras (ex.: "não pode doar mais do que falta") e fala com o banco.
- O **model** descreve as tabelas e os relacionamentos.

Vantagem para apresentar: as regras ficam num lugar só e podem ser testadas sem abrir o navegador.

---

## 3. Inicialização: `main.py` → `create_app()`

`main.py` tem só duas linhas úteis: importa `create_app` e cria `app = create_app()`.

`create_app()` (em `app/__init__.py`) é o padrão **Application Factory** do Flask. Ela:

1. **Escolhe a configuração**: o que estiver em `FLASK_CONFIG`; se não houver, `production` na Vercel e
   `development` no computador. Os testes chamam `create_app("testing")`.
2. **Cria o objeto Flask** apontando os arquivos estáticos para `public/static` (na Vercel essa pasta
   é entregue direto pela CDN, sem passar pelo Python).
3. **Exige a `SECRET_KEY`**: sem ela o sistema não sobe, porque é ela que assina a sessão (login e carrinho).
4. **Liga as extensões**: banco (`db`), proteção CSRF (`csrf`) e login (`login_manager`).
5. **Registra os blueprints** com seus prefixos de URL, as **páginas de erro** (404, 403, 413, 500,
   formulário expirado) e os **filtros** de template (`data_br`, `qtd`).
6. **Cria as tabelas** que ainda não existem (`db.create_all()`) e, se `ADMIN_EMAIL`/`ADMIN_SENHA`
   estiverem definidos, **cria o primeiro administrador** (é assim que se entra no sistema na Vercel,
   onde não há terminal).

Detalhe técnico que costuma gerar pergunta: no topo do arquivo há um "ouvinte" que liga
`PRAGMA foreign_keys=ON` em cada conexão **SQLite**, porque o SQLite ignora chaves estrangeiras por padrão.
No PostgreSQL isso não é necessário, então a função simplesmente sai.

### `config.py` e o banco de dados

A função `_url_banco()` decide onde ficam os dados:

| Situação | Banco usado |
|---|---|
| `DATABASE_URL` definida (Vercel/Neon) | PostgreSQL (o endereço é ajustado para o driver `psycopg`) |
| Na Vercel sem `DATABASE_URL` | SQLite em `/tmp` (funciona, mas os dados se perdem) |
| No computador | SQLite em `instance/entrelacos.db` |
| Testes | SQLite em memória (some ao fim de cada teste) |

O mesmo código funciona nos dois bancos porque tudo passa pelo **SQLAlchemy** (ORM): escrevemos Python e
ele gera o SQL do banco certo.

---

## 4. Banco de dados: `models.py`

Cada classe é uma tabela. As principais:

| Classe / tabela | O que guarda | Destaques |
|---|---|---|
| `Administrador` | organizadores | senha guardada só como **hash** (`definir_senha` / `verificar_senha`) |
| `Evento` | nome, data, local, status, capa | `aberto` ou `encerrado`; a imagem fica no banco (`imagem_dados`) |
| `Item` | o que o evento precisa | `quantidade_necessaria` e `quantidade_comprometida` (já reservada) |
| `Doador` | nome e telefone | identificado pelo **telefone** (único), sem conta nem senha |
| `Doacao` | uma confirmação de carrinho | situação geral: pendente, parcial, recebida, cancelada |
| `DoacaoItem` | cada item dentro de uma doação | prometido, recebido e cancelado |
| `Entrega` | cada registro feito pelo organizador | `token` único evita salvar o mesmo envio duas vezes |
| `Recebimento` | quanto de cada item entrou numa entrega | histórico detalhado |

Relação entre elas (o diagrama completo está em `docs/diagrama_er.png`):

```
Administrador 1─N Evento 1─N Item
                     │          │
                     1          1
                     N          N
Doador 1─N Doacao 1─N DoacaoItem
              │                 │
              1─N Entrega 1─N Recebimento
```

**Restrições no próprio banco (CHECK constraints).** Além do Python, o banco também impede dados inválidos,
por exemplo:

- `quantidade_comprometida <= quantidade_necessaria` (nunca reservar além do necessário);
- `quantidade_recebida + quantidade_cancelada <= quantidade_prometida` (nunca receber além do prometido);
- `status IN ('aberto', 'encerrado')`.

É uma segunda camada de proteção: mesmo que algum código errado tentasse gravar algo inválido, o banco recusaria.

**Propriedades calculadas** (`@property`) evitam guardar dados repetidos: `quantidade_disponivel`,
`quantidade_pendente`, `percentual_recebido`, `codigo` (ex.: `EL-00012`) são calculados na hora.

**Situação da doação.** A função `calcular_status(prometido, recebido, cancelado)` resume a regra:

- ainda falta algo → `parcial` se já chegou alguma coisa, senão `pendente`;
- não falta nada → `cancelada` se houve cancelamento, senão `recebida`.

---

## 5. As rotas (blueprints)

| Blueprint | Prefixo | Páginas |
|---|---|---|
| `public.py` | `/` | página inicial (eventos abertos e encerrados), "Como funciona" |
| `eventos.py` | `/eventos` | página do evento, imagem de capa e, com login, cadastro/edição de eventos e itens |
| `doacoes.py` | `/doacoes` | carrinho, confirmação, comprovante, consulta de doações |
| `admin.py` | `/admin` | login/logout, painel com indicadores, lista de doações, registro de recebimentos |

Rotas da área restrita têm `@login_required`: sem login, o visitante é levado para `/admin/login`.

---

## 6. Os fluxos principais

### 6.1 Doar (visitante)

1. **Página do evento** (`/eventos/<id>`): mostra os itens ativos com necessário, prometido e disponível.
2. **Adicionar ao carrinho** (`services/carrinho.py`): o carrinho vive na **sessão** do navegador, no formato
   `{"evento_id": 3, "itens": {"12": 2, "15": 5}}`. Regras: quantidade maior que zero, evento aberto, item ativo,
   não passar do disponível e **um carrinho pertence a um único evento**.
3. **Confirmar** (`/doacoes/confirmar`): o formulário exige nome e sobrenome e telefone válido com DDD.
4. **Gravar a doação** (`services/doacoes.py → confirmar_doacao`). É o trecho mais importante do sistema:

   ```python
   update(Item)
     .where(Item.id == item_id,
            Item.ativo.is_(True),
            Item.quantidade_comprometida + quantidade <= Item.quantidade_necessaria)
     .values(quantidade_comprometida=Item.quantidade_comprometida + quantidade)
   ```

   A verificação ("ainda cabe?") e a reserva acontecem **no mesmo comando SQL**. Se duas pessoas tentam doar
   o último pacote ao mesmo tempo, só uma atualização encontra a condição verdadeira; a outra afeta 0 linhas.
   Se **qualquer** item não couber, é feito `rollback` e **nada** é gravado (a doação é tudo ou nada).
   Isso é uma **transação**.
5. O doador é encontrado pelo telefone (ou criado), a doação é salva e o visitante vê o **comprovante**
   (só quem acabou de doar consegue abrir essa página, porque o id fica guardado na sessão dele).

### 6.2 Consultar uma doação (visitante)

Em `/doacoes/acompanhar` ou na consulta de cada evento, pesquisa-se por **nome** (parte do nome) ou por
**telefone** (completo). O telefone **nunca é exibido** na resposta, e o campo é apagado depois da busca,
para proteger o doador.

### 6.3 Registrar o que chegou (organizador)

Na página de uma doação (`/admin/doacoes/<id>`), o organizador informa, para cada item, quanto **recebeu**
e/ou quanto **cancelou**. Em `services/recebimentos.py`:

- não aceita números negativos nem mais do que o **pendente** de cada item;
- cada envio carrega um **token** único gerado no formulário. Se o mesmo formulário for enviado duas vezes
  (clique duplo, F5), o segundo é recusado;
- **cancelar devolve** a quantidade ao item (ela volta a ficar disponível para outros doadores);
  **receber não mexe** na reserva, que já foi feita na confirmação;
- no fim, a situação da doação é recalculada (`recalcular_status`).

Também há o botão **"cancelar pendências"**, que cancela de uma vez tudo o que ainda não chegou.

### 6.4 Painel (organizador)

`services/dashboard.py` faz consultas com **agregação** (`COUNT`, `SUM`, `AVG`, `GROUP BY`) direto no banco:
eventos ativos, doações por situação, itens que ainda faltam e o progresso (comprometido × recebido) por evento.

### 6.5 Gerenciar eventos e itens (organizador)

- Cadastro e edição de eventos com **imagem de capa** obrigatória.
- A imagem é validada pelo **conteúdo real** (os primeiros bytes do arquivo), não só pela extensão. Um arquivo
  `.png` que não é imagem é recusado. Limite de 3 MB.
- A imagem é guardada **no banco**, e a rota `/eventos/<id>/capa/<nome>` a devolve. O nome muda a cada troca de
  capa, então o navegador pode guardar a imagem em cache sem risco de mostrar a antiga.
- Itens podem ser editados, mas a quantidade necessária **não pode ficar abaixo do já comprometido**.
- Itens são **desativados** (não apagados), para não quebrar o histórico de doações.

---

## 7. Segurança (pontos bons para citar na apresentação)

| Medida | Onde |
|---|---|
| Senhas com hash (nunca em texto puro) | `models.py` (`werkzeug.security`) |
| Proteção **CSRF** em todos os formulários | `extensions.py` + campo `csrf_token` oculto nos templates |
| Validação no **servidor** (o JavaScript só ajuda a digitar) | `forms.py` |
| Login obrigatório na área restrita | `@login_required` |
| Redirecionamento pós-login só para endereços internos | `admin.py → login()` |
| Telefone nunca aparece em páginas públicas | consultas em `doacoes.py` |
| Upload validado por tipo real e tamanho | `services/eventos.py` |
| `SECRET_KEY` e senha do banco fora do código | variáveis de ambiente (`.env` / Vercel) |
| Cookies de sessão `HttpOnly`, `SameSite` e `Secure` em produção | `config.py` |
| Restrições CHECK/UNIQUE no banco | `models.py` |

---

## 8. Interface

- **Templates Jinja2**: `base.html` é o layout (menu, rodapé, mensagens); cada página "herda" dele com
  `{% extends "base.html" %}` e preenche o bloco `conteudo`.
- **Macros** (`_macros.html`): pedaços reaproveitáveis, como o campo de formulário com mensagem de erro,
  o selo de situação e a barra de progresso.
- **Bootstrap 5** para o grid responsivo, com identidade visual própria em `public/static/css/style.css`.
- **JavaScript** (`public/static/js/app.js`): botões + e − de quantidade, máscara de telefone, prévia da imagem
  antes do envio, confirmação antes de ações destrutivas e bloqueio de clique duplo nos botões de envio.

---

## 9. Por que algumas escolhas mudaram para rodar na Vercel

| Antes (só local) | Agora | Motivo |
|---|---|---|
| Imagens salvas em `static/uploads` | Imagens no banco | Na Vercel o disco é temporário e somente leitura |
| Só SQLite | SQLite local + PostgreSQL em produção | Os dados precisam sobreviver entre execuções |
| Logs em arquivo `logs/entrelacos.log` | Logs no terminal / Runtime Logs da Vercel | Não há onde gravar arquivo |
| Admin criado só pelo terminal | Também por `ADMIN_EMAIL`/`ADMIN_SENHA` | Na Vercel não há terminal |
| `static/` dentro de `app/` | `public/static/` | A Vercel serve `public/` pela CDN, mais rápido |
| `run.py` | `main.py` | Nome que a Vercel reconhece automaticamente |

Todas as funcionalidades continuam as mesmas; os 37 testes automatizados passam.

---

## 10. Perguntas prováveis na apresentação (e respostas curtas)

**Como vocês garantem que não doam mais do que o necessário?**
A reserva é feita com um único `UPDATE … WHERE comprometida + quantidade <= necessaria`, dentro de uma
transação. Se não couber, nada é gravado. E o banco ainda tem um CHECK com a mesma regra.

**E se duas pessoas doarem o último item ao mesmo tempo?**
Só a primeira atualização encontra a condição verdadeira; a segunda afeta zero linhas e recebe a mensagem de
que o item não tem mais a quantidade disponível. Há um teste automatizado para isso.

**Por que o doador não precisa de conta?**
Para reduzir atrito: basta nome e telefone. O telefone identifica o doador entre doações e permite a consulta,
mas nunca é exibido publicamente.

**Como funciona a entrega parcial?**
Cada doação guarda, por item, prometido, recebido e cancelado. O organizador pode registrar várias entregas;
a situação é recalculada a cada registro. Cancelar libera a quantidade para outros doadores.

**Por que separar `services` das rotas?**
Para as regras não dependerem da interface: ficam testáveis, reaproveitáveis e mais fáceis de manter.

**Como evitam registro duplicado de recebimento?**
Cada formulário leva um token único; a coluna `token` da tabela `entregas` é `UNIQUE`, então o mesmo envio
não entra duas vezes.

**Como testaram?**
Com `pytest`, usando banco em memória: 37 casos cobrindo doação válida e inválida, concorrência, recebimento
parcial, recebimento acima do prometido, duplicidade, cancelamento, login e evento encerrado.
