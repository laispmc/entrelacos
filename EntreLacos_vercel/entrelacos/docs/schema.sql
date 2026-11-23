-- EntreLaços: DDL gerada a partir dos modelos (app/models.py) — SQLite (uso local)

CREATE TABLE administradores (
	id INTEGER NOT NULL, 
	nome VARCHAR(120) NOT NULL, 
	email VARCHAR(160) NOT NULL, 
	senha_hash VARCHAR(256) NOT NULL, 
	ativo BOOLEAN NOT NULL, 
	criado_em DATETIME NOT NULL, 
	CONSTRAINT pk_administradores PRIMARY KEY (id), 
	CONSTRAINT uq_administradores_email UNIQUE (email)
);

CREATE TABLE doadores (
	id INTEGER NOT NULL, 
	nome VARCHAR(150) NOT NULL, 
	telefone VARCHAR(15) NOT NULL, 
	criado_em DATETIME NOT NULL, 
	CONSTRAINT pk_doadores PRIMARY KEY (id), 
	CONSTRAINT uq_doadores_telefone UNIQUE (telefone)
);

CREATE INDEX ix_doadores_nome ON doadores (nome);

CREATE TABLE eventos (
	id INTEGER NOT NULL, 
	nome VARCHAR(150) NOT NULL, 
	descricao TEXT, 
	data DATE NOT NULL, 
	local VARCHAR(200), 
	imagem_capa VARCHAR(255) NOT NULL, 
	imagem_dados BLOB, 
	imagem_tipo VARCHAR(10), 
	status VARCHAR(20) NOT NULL, 
	criado_em DATETIME NOT NULL, 
	administrador_id INTEGER NOT NULL, 
	CONSTRAINT pk_eventos PRIMARY KEY (id), 
	CONSTRAINT ck_eventos_status_valido CHECK (status IN ('aberto', 'encerrado')), 
	CONSTRAINT fk_eventos_administrador_id_administradores FOREIGN KEY(administrador_id) REFERENCES administradores (id) ON DELETE RESTRICT
);

CREATE INDEX ix_eventos_status ON eventos (status);

CREATE TABLE itens (
	id INTEGER NOT NULL, 
	evento_id INTEGER NOT NULL, 
	nome VARCHAR(120) NOT NULL, 
	descricao VARCHAR(255), 
	quantidade_necessaria INTEGER NOT NULL, 
	quantidade_comprometida INTEGER NOT NULL, 
	unidade VARCHAR(30) NOT NULL, 
	ativo BOOLEAN NOT NULL, 
	CONSTRAINT pk_itens PRIMARY KEY (id), 
	CONSTRAINT ck_itens_necessaria_positiva CHECK (quantidade_necessaria > 0), 
	CONSTRAINT ck_itens_comprometida_nao_negativa CHECK (quantidade_comprometida >= 0), 
	CONSTRAINT ck_itens_comprometida_limite CHECK (quantidade_comprometida <= quantidade_necessaria), 
	CONSTRAINT uq_itens_evento_nome UNIQUE (evento_id, nome), 
	CONSTRAINT fk_itens_evento_id_eventos FOREIGN KEY(evento_id) REFERENCES eventos (id) ON DELETE CASCADE
);

CREATE INDEX ix_itens_evento_id ON itens (evento_id);

CREATE TABLE doacoes (
	id INTEGER NOT NULL, 
	evento_id INTEGER NOT NULL, 
	doador_id INTEGER NOT NULL, 
	nome_informado VARCHAR(150) NOT NULL, 
	observacao VARCHAR(500), 
	status VARCHAR(20) NOT NULL, 
	criado_em DATETIME NOT NULL, 
	CONSTRAINT pk_doacoes PRIMARY KEY (id), 
	CONSTRAINT ck_doacoes_status_valido CHECK (status IN ('pendente', 'parcial', 'recebida', 'cancelada')), 
	CONSTRAINT fk_doacoes_evento_id_eventos FOREIGN KEY(evento_id) REFERENCES eventos (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_doacoes_doador_id_doadores FOREIGN KEY(doador_id) REFERENCES doadores (id) ON DELETE RESTRICT
);

CREATE INDEX ix_doacoes_doador_id ON doacoes (doador_id);

CREATE INDEX ix_doacoes_status ON doacoes (status);

CREATE INDEX ix_doacoes_evento_id ON doacoes (evento_id);

CREATE TABLE doacao_itens (
	id INTEGER NOT NULL, 
	doacao_id INTEGER NOT NULL, 
	item_id INTEGER NOT NULL, 
	quantidade_prometida INTEGER NOT NULL, 
	quantidade_recebida INTEGER NOT NULL, 
	quantidade_cancelada INTEGER NOT NULL, 
	CONSTRAINT pk_doacao_itens PRIMARY KEY (id), 
	CONSTRAINT ck_doacao_itens_prometida_positiva CHECK (quantidade_prometida > 0), 
	CONSTRAINT ck_doacao_itens_recebida_nao_negativa CHECK (quantidade_recebida >= 0), 
	CONSTRAINT ck_doacao_itens_cancelada_nao_negativa CHECK (quantidade_cancelada >= 0), 
	CONSTRAINT ck_doacao_itens_limite_prometido CHECK (quantidade_recebida + quantidade_cancelada <= quantidade_prometida), 
	CONSTRAINT uq_doacao_itens_doacao_item UNIQUE (doacao_id, item_id), 
	CONSTRAINT fk_doacao_itens_doacao_id_doacoes FOREIGN KEY(doacao_id) REFERENCES doacoes (id) ON DELETE CASCADE, 
	CONSTRAINT fk_doacao_itens_item_id_itens FOREIGN KEY(item_id) REFERENCES itens (id) ON DELETE RESTRICT
);

CREATE INDEX ix_doacao_itens_item_id ON doacao_itens (item_id);

CREATE INDEX ix_doacao_itens_doacao_id ON doacao_itens (doacao_id);

CREATE TABLE entregas (
	id INTEGER NOT NULL, 
	doacao_id INTEGER NOT NULL, 
	administrador_id INTEGER NOT NULL, 
	token VARCHAR(36) NOT NULL, 
	tipo VARCHAR(20) NOT NULL, 
	observacao VARCHAR(255), 
	registrado_em DATETIME NOT NULL, 
	CONSTRAINT pk_entregas PRIMARY KEY (id), 
	CONSTRAINT fk_entregas_doacao_id_doacoes FOREIGN KEY(doacao_id) REFERENCES doacoes (id) ON DELETE CASCADE, 
	CONSTRAINT fk_entregas_administrador_id_administradores FOREIGN KEY(administrador_id) REFERENCES administradores (id) ON DELETE RESTRICT, 
	CONSTRAINT uq_entregas_token UNIQUE (token)
);

CREATE INDEX ix_entregas_doacao_id ON entregas (doacao_id);

CREATE TABLE recebimentos (
	id INTEGER NOT NULL, 
	entrega_id INTEGER NOT NULL, 
	doacao_item_id INTEGER NOT NULL, 
	quantidade_recebida INTEGER NOT NULL, 
	quantidade_cancelada INTEGER NOT NULL, 
	CONSTRAINT pk_recebimentos PRIMARY KEY (id), 
	CONSTRAINT ck_recebimentos_recebida_nao_negativa CHECK (quantidade_recebida >= 0), 
	CONSTRAINT ck_recebimentos_cancelada_nao_negativa CHECK (quantidade_cancelada >= 0), 
	CONSTRAINT ck_recebimentos_movimento_positivo CHECK (quantidade_recebida + quantidade_cancelada > 0), 
	CONSTRAINT fk_recebimentos_entrega_id_entregas FOREIGN KEY(entrega_id) REFERENCES entregas (id) ON DELETE CASCADE, 
	CONSTRAINT fk_recebimentos_doacao_item_id_doacao_itens FOREIGN KEY(doacao_item_id) REFERENCES doacao_itens (id) ON DELETE CASCADE
);

CREATE INDEX ix_recebimentos_doacao_item_id ON recebimentos (doacao_item_id);

CREATE INDEX ix_recebimentos_entrega_id ON recebimentos (entrega_id);
