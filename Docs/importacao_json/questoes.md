# Questoes

Formato aceito pelo banco de questoes:

```json
{
  "materia": "matematica",
  "questoes": [
    {
      "codigo": "ENEM-2024-MAT-001",
      "enunciado": "Texto da questão...",
      "explicacao": "Explicação da resolução.",
      "dificuldade": "medium",
      "tipo_fonte": "enem",
      "fonte_nome": "ENEM",
      "fonte_ano": 2024,
      "fonte_url": "https://example.com",
      "imagem": {
        "public_id": "enem/2025/caderno7/q136",
        "alt": "Gráfico utilizado na questão"
      },
      "status": "draft",
      "conteudo_principal": "funcao-afim",
      "conteudos": ["funcao-afim"],
      "gabarito": "A",
      "requer_imagem": false,
      "alternativas": [
        {
          "chave": "A",
          "texto": "Alternativa A",
          "imagem": null,
          "correta": true,
          "ordem": 1
        },
        {"chave": "B", "texto": "Alternativa B", "correta": false, "ordem": 2}
      ]
    }
  ]
}
```

Campos:

- `materia`: slug da materia, no topo ou em cada questao.
- `codigo`: obrigatorio e unico.
- `enunciado`: texto obrigatorio.
- `explicacao`: texto opcional.
- `dificuldade`: `easy`, `medium` ou `hard`.
- `tipo_fonte`: `original`, `enem`, `vestibular`, `adapted` ou `other`.
- `fonte_nome`: texto opcional.
- `fonte_ano`: inteiro opcional.
- `fonte_url`: URL opcional.
- `imagem`: objeto opcional com `public_id` e `alt`, ou `null`.
- `status`: `draft`, `published` ou `archived`.
- `conteudo_principal`: slug de um dos conteudos informados.
- `conteudos`: lista de slugs de conteudos existentes.
- `gabarito`: chave esperada da alternativa correta, opcional.
- `requer_imagem`: se `true`, exige que `imagem.public_id` esteja informado.
- `alternativas`: lista com pelo menos duas alternativas.

Regras:

- exatamente uma alternativa deve ter `correta: true`;
- cada alternativa precisa ter texto, imagem, ou ambos;
- JSON nao faz upload de imagem: `public_id` deve apontar para asset existente no Cloudinary;
- o conteudo principal deve estar em `conteudos`;
- todos os conteudos precisam existir e pertencer a materia da questao;
- questoes com `status: "published"` tambem passam pelas regras reais de publicacao.

Campos extras presentes em massas antigas, como `ano`, `caderno`, `pagina_pdf`, `gabarito_url` e `observacao_revisao`, sao ignorados pelo importador atual.
