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

## Padrao recomendado para imagens no Cloudinary

O JSON deve receber o `public_id` da imagem ja existente no Cloudinary, sem URL completa e sem extensao do arquivo.

Padrao escolhido para questoes do ENEM:

```text
plataforma-estudos/questoes/enem/{ano}/{caderno}/{cor}/q{numero}
```

Padrao escolhido para imagens de alternativas:

```text
plataforma-estudos/questoes/enem/{ano}/{caderno}/{cor}/q{numero}-{alternativa}
```

Regras de preenchimento:

- `{ano}`: ano da prova, com 4 digitos. Exemplo: `2024`.
- `{caderno}`: nome ou numero do caderno em letras minusculas, sem acento e sem espaco. Exemplos: `caderno1`, `caderno7`, `regular`, `reaplicacao`.
- `{cor}`: cor do caderno em letras minusculas, sem acento. Exemplos: `azul`, `amarelo`, `branco`, `cinza`, `rosa`, `verde`.
- `{numero}`: numero da questao com 3 digitos. Exemplos: `001`, `045`, `136`.
- `{alternativa}`: letra da alternativa em minusculo. Exemplos: `a`, `b`, `c`, `d`, `e`.

Exemplos de `public_id`:

```text
plataforma-estudos/questoes/enem/2024/caderno7/azul/q136
plataforma-estudos/questoes/enem/2024/caderno7/azul/q136-a
plataforma-estudos/questoes/enem/2024/caderno7/azul/q136-b
```

Exemplo no JSON:

```json
{
  "codigo": "ENEM-2024-MAT-136",
  "enunciado": "Texto da questao...",
  "imagem": {
    "public_id": "plataforma-estudos/questoes/enem/2024/caderno7/azul/q136",
    "alt": "Imagem da questao 136 do ENEM 2024, caderno azul"
  },
  "alternativas": [
    {
      "chave": "A",
      "texto": "",
      "imagem": {
        "public_id": "plataforma-estudos/questoes/enem/2024/caderno7/azul/q136-a",
        "alt": "Imagem da alternativa A da questao 136"
      },
      "correta": false,
      "ordem": 1
    },
    {
      "chave": "B",
      "texto": "Texto da alternativa B",
      "imagem": null,
      "correta": true,
      "ordem": 2
    }
  ]
}
```

Para outras fontes, mantenha a mesma logica trocando `enem` pelo tipo da prova ou instituicao:

```text
plataforma-estudos/questoes/{fonte}/{ano}/{prova-ou-caderno}/{cor-ou-versao}/q{numero}
```

Exemplo:

```text
plataforma-estudos/questoes/vestibular/2025/fuvest/primeira-fase/q012
```

Boas praticas:

- usar apenas letras minusculas, numeros, hifens e barras;
- nao usar acentos, espacos ou caracteres especiais;
- nao incluir `.jpg`, `.png` ou `.webp` no `public_id`;
- nao renomear uma imagem no Cloudinary depois de usa-la no JSON, porque isso quebra a referencia salva.

Campos extras presentes em massas antigas, como `ano`, `caderno`, `pagina_pdf`, `gabarito_url` e `observacao_revisao`, sao ignorados pelo importador atual.
