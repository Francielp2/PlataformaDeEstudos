# Conteudos

Formato:

```json
{
  "conteudos": [
    {
      "materia": "matematica",
      "titulo": "Função Afim",
      "slug": "funcao-afim",
      "resumo": "Resumo do conteúdo.",
      "texto_estudo": "",
      "dificuldade": "basic",
      "status": "draft",
      "ordem_sugerida": 1,
      "pai": null
    }
  ]
}
```

Tambem e aceito `materia` no topo do JSON quando todos os conteudos pertencem a mesma materia.

Campos:

- `materia`: slug da materia existente.
- `titulo`: texto obrigatorio.
- `slug`: texto obrigatorio, unico por materia.
- `resumo`: texto obrigatorio.
- `texto_estudo`: texto opcional.
- `dificuldade`: `basic`, `intermediate` ou `advanced`.
- `status`: `draft`, `published` ou `archived`.
- `ordem_sugerida`: inteiro maior ou igual a zero.
- `pai`: `null` ou slug de um conteudo da mesma materia.

Hierarquia:

- o pai pode estar antes ou depois do filho no JSON;
- o pai deve pertencer a mesma materia;
- um conteudo nao pode ser pai de si mesmo;
- ciclos na hierarquia cancelam a importacao.

Exemplo com subconteudo:

```json
{
  "conteudos": [
    {
      "materia": "matematica",
      "titulo": "Funções",
      "slug": "funcoes",
      "resumo": "Introdução a funções.",
      "texto_estudo": "",
      "dificuldade": "basic",
      "status": "draft",
      "ordem_sugerida": 1,
      "pai": null
    },
    {
      "materia": "matematica",
      "titulo": "Função Afim",
      "slug": "funcao-afim",
      "resumo": "Funções do primeiro grau.",
      "texto_estudo": "",
      "dificuldade": "basic",
      "status": "draft",
      "ordem_sugerida": 2,
      "pai": "funcoes"
    }
  ]
}
```

Exemplo invalido:

```json
{
  "conteudos": [
    {
      "materia": "fisica",
      "titulo": "Função Afim",
      "slug": "funcao-afim",
      "resumo": "",
      "dificuldade": "facil",
      "status": "publicado",
      "ordem_sugerida": -1,
      "pai": "funcao-afim"
    }
  ]
}
```
