# Simulados

A importacao JSON de simulados ocorre dentro de um simulado ja criado, na tela de questoes do simulado. O JSON importa questoes para snapshots congelados do simulado.

Formato:

```json
{
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
      "conteudo_principal": "funcao-afim",
      "conteudos": ["funcao-afim"],
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

Regras:

- o simulado nao pode ter tentativas se a estrutura estiver sendo alterada;
- cada questao importada vira um snapshot independente;
- alternativas, enunciado, explicacao, fonte, dificuldade e conteudos ficam congelados no simulado;
- imagens da questao e das alternativas tambem ficam congeladas pelo `public_id` do Cloudinary;
- JSON nao faz upload de imagem: `public_id` deve apontar para asset existente no Cloudinary;
- o conteudo principal deve estar na lista `conteudos`;
- simulados por materia so aceitam conteudos da materia selecionada;
- exatamente uma alternativa deve estar correta;
- a opcao `Salvar questões importadas também no banco de questões` cria tambem a questao no banco individual, em rascunho, exigindo `codigo` unico.

Tentativas, respostas, resultados, historico e diagnostico continuam usando os snapshots do simulado, sem depender de futuras alteracoes no banco de questoes.
