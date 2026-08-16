# Plataforma de Estudos e Organização para ENEM

## Sobre o projeto

A Plataforma de Estudos e Organização para ENEM é um sistema web desenvolvido como Projeto Integrador, com o objetivo de auxiliar estudantes do Ensino Médio na preparação para o ENEM.

Nesta etapa, o projeto mantém o módulo de usuários e prepara a interface para futuros recursos de matérias, conteúdos, questões, simulados e organização manual dos estudos.

Inicialmente o sistema será desenvolvido utilizando Django e terá foco nas disciplinas:

- Matemática
- Física
- Química

---

# Tecnologias utilizadas

## Backend

- Python 3
- Django
- SQLite (desenvolvimento)

## Frontend

- HTML5
- CSS3
- Bootstrap
- JavaScript

## Controle de versão

- Git
- GitHub

---

# Estrutura do projeto

```
plataforma_estudos/
│
├── config/                # Configurações do projeto Django
├── core/                  # Aplicação principal
├── templates/             # Templates HTML
├── static/
│   ├── css/
│   ├── js/
│   └── images/
│
├── .env.example
├── .gitignore
├── manage.py
├── requirements.txt
└── README.md
```

---

# Pré-requisitos

Antes de iniciar, instale:

- Python 3.12 ou superior
- Git

Verifique:

```bash
python --version
```

ou

```bash
python3 --version
```

---

# Clonando o projeto

```bash
git clone URL_DO_REPOSITORIO
```

Entre na pasta:

```bash
cd plataforma_estudos
```

---

# Criando o ambiente virtual

## Linux

```bash
python3 -m venv venv
```

Ative:

```bash
source venv/bin/activate
```

---

## Windows CMD

```cmd
python -m venv venv

venv\Scripts\activate
```

---

## Windows PowerShell

```powershell
python -m venv venv

.\venv\Scripts\Activate.ps1
```

Após ativar deverá aparecer:

```
(venv)
```

---

# Instalando as dependências

Atualize o pip:

```bash
python -m pip install --upgrade pip
```

Instale todas as dependências do projeto:

```bash
python -m pip install -r requirements.txt
```

---

# Configurando o arquivo .env

O arquivo `.env` contém informações locais da máquina e **não deve ser enviado para o GitHub**.

Crie uma cópia do arquivo de exemplo.

## Linux

```bash
cp .env.example .env
```

## Windows

```cmd
copy .env.example .env
```

Depois abra o arquivo `.env`.

Exemplo:

```
SECRET_KEY=
DEBUG=True
```

Gere uma SECRET_KEY executando:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Copie o valor gerado para:

```
SECRET_KEY=sua_chave
```

---

# Banco de dados

Execute as migrations:

```bash
python manage.py migrate
```

---

# Executando o servidor

```bash
python manage.py runserver
```

Acesse:

```
http://127.0.0.1:8000/
```

Painel administrativo:

```
http://127.0.0.1:8000/admin/
```

---

# Atualizando dependências

Sempre que instalar uma nova biblioteca execute:

```bash
python -m pip freeze > requirements.txt
```

Assim todos os integrantes terão as mesmas versões.

---

# Fluxo de trabalho da equipe

## Antes de começar

Sempre atualize sua branch:

```bash
git checkout main

git pull origin main
```

---

## Criando uma nova funcionalidade

Nunca desenvolva diretamente na branch `main`.

Crie uma branch:

```bash
git checkout -b feature/nome-da-funcionalidade
```

Exemplos:

```bash
git checkout -b feature/login

git checkout -b feature/simulados

git checkout -b feature/conteudos

git checkout -b feature/questoes
```

---

## Salvando alterações

```bash
git add .

git commit -m "feat: descrição da funcionalidade"
```

Exemplo:

```bash
git commit -m "feat: adiciona tela de login"
```

---

## Enviando para o GitHub

```bash
git push origin feature/nome-da-funcionalidade
```

Depois abra um Pull Request no GitHub.

---

# Convenção de commits

Utilizaremos o padrão Conventional Commits.

## Nova funcionalidade

```
feat:
```

Exemplo:

```
feat: cria sistema de login
```

---

## Correção

```
fix:
```

Exemplo:

```
fix: corrige validação do formulário
```

---

## Documentação

```
docs:
```

Exemplo:

```
docs: atualiza README
```

---

## Refatoração

```
refactor:
```

---

## Estilo

```
style:
```

---

## Configuração

```
chore:
```

---

# Atualizando sua branch

Caso outro integrante tenha enviado alterações:

```bash
git checkout main

git pull origin main
```

Volte para sua branch:

```bash
git checkout feature/minha-feature
```

Atualize:

```bash
git merge main
```

Resolva conflitos caso existam.

---

# Trabalhando com Models

Sempre que alterar um Model:

Crie a migration:

```bash
python manage.py makemigrations
```

Depois execute:

```bash
python manage.py migrate
```

Os arquivos gerados dentro da pasta

```
migrations/
```

devem ser enviados para o Git.

---

# O que NÃO deve ir para o GitHub

Nunca envie:

```
venv/
```

```
.env
```

```
db.sqlite3
```

```
__pycache__/
```

Esses arquivos já estão configurados no `.gitignore`.

---

# Atualizando seu ambiente

Caso outra pessoa instale novas bibliotecas:

```bash
git pull

python -m pip install -r requirements.txt
```

---

# Caso ocorra erro de dependências

Atualize o ambiente executando:

```bash
python -m pip install --upgrade pip

python -m pip install -r requirements.txt
```

---

# Organização da equipe

Cada integrante será responsável por um módulo específico.

Exemplo:

| Integrante | Responsabilidade |
|------------|------------------|
| Integrante 1 | Usuários e autenticação |
| Integrante 2 | Conteúdos |
| Integrante 3 | Simulados |
| Integrante 4 | Relatórios |
| Integrante 5 | Interface |

Essa divisão poderá ser alterada conforme o andamento do projeto.

---

# Objetivo da primeira versão (MVP)

A primeira versão da plataforma deverá conter:

- Cadastro de usuários
- Login
- Página inicial
- Listagem de matérias
- Listagem de conteúdos
- Questões individuais para estudo
- Simulados
- Correção automática
- Relatório de desempenho
- Histórico
- Organização manual com Minha lista e Estudado

---

# Boas práticas

- Sempre faça `git pull` antes de começar.
- Nunca altere diretamente a branch `main`.
- Escreva commits descritivos.
- Teste sua funcionalidade antes de enviar.
- Mantenha o código organizado e comentado quando necessário.
- Utilize nomes claros para variáveis, funções e classes.
- Em caso de conflitos no Git, converse com o integrante responsável pela funcionalidade antes de resolver.

---

# Contato da equipe

Adicionar posteriormente os integrantes e suas funções.

```

### Observação adicional

Como esse é um projeto desenvolvido em equipe para um período de aproximadamente seis meses, eu também criaria um arquivo chamado **`CONTRIBUTING.md`**. Nele vocês podem documentar padrões de código (PEP 8, convenções para nomes de apps, organização de pastas, uso de branches, regras para Pull Requests e revisão de código). Isso mantém o `README.md` focado na instalação e uso do projeto, enquanto as regras de colaboração ficam centralizadas em um documento específico.
