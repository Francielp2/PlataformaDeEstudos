# Importacao JSON

Esta estrategia separa estrutura e dados:

- migrations criam e alteram tabelas, campos, indices, constraints e relacionamentos;
- JSONs guardam dados massivos cadastraveis, como materias, conteudos, questoes e simulados.

Migrations nao devem inserir dados academicos. Um banco novo deve nascer vazio de materias, conteudos, questoes e simulados, e o povoamento deve ser feito pelos importadores do painel administrativo.

## Pasta data

A pasta `data/` fica na raiz do projeto e organiza JSONs locais usados para povoar bancos. Ela esta no `.gitignore` porque esses arquivos podem variar por ambiente, conter massas grandes ou serem revisados fora do ciclo normal de migrations.

Estrutura sugerida:

```text
data/
├── materias/
├── conteudos/
├── questoes/
└── simulados/
```

## Ordem de povoamento de um banco novo

1. Executar migrations: `python manage.py migrate`.
2. Criar superusuario: `python manage.py createsuperuser`.
3. Importar materias.
4. Importar conteudos.
5. Importar questoes.
6. Criar ou importar simulados.

## Uso dos importadores

Acesse o painel administrativo interno, abra a listagem da entidade e clique em `Importar JSON`. Cole o JSON no textarea e confirme em `Importar`.

As importacoes sao atomicas: se qualquer item falhar, nenhum registro daquele JSON e persistido. Os erros indicam o item e o campo problemático, por exemplo `Conteúdo 7: matéria "fisica" não encontrada.`

Para evitar duplicidades, revise slugs e codigos antes de importar. Por padrao, registros existentes geram erro; o importador nao atualiza nem duplica silenciosamente dados ja cadastrados.
