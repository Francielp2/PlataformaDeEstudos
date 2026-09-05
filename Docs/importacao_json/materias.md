# Materias

Formato:

```json
{
  "materias": [
    {
      "nome": "Matemática",
      "slug": "matematica",
      "descricao": "Descrição da matéria",
      "ordem_exibicao": 1,
      "ativa": true
    }
  ]
}
```

Campos:

- `nome`: texto obrigatorio, unico sem diferenciar maiusculas/minusculas.
- `slug`: texto obrigatorio, unico, em formato de slug valido.
- `descricao`: texto opcional.
- `ordem_exibicao`: inteiro maior ou igual a zero, opcional, padrao `0`.
- `ativa`: booleano opcional, padrao `true`.

Regras:

- o importador nao atualiza materias existentes;
- duplicidade de `nome` ou `slug` no banco ou dentro do proprio JSON cancela toda a importacao;
- a materia passa pelas validacoes reais do model antes de ser salva.

Exemplo invalido:

```json
{
  "materias": [
    {
      "nome": "",
      "slug": "Matemática",
      "ordem_exibicao": -1,
      "ativa": "sim"
    }
  ]
}
```
