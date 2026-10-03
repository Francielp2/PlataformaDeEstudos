# Videos

Formato:

```json
{
  "materia": "matematica",
  "videos": [
    {
      "conteudo": "porcentagem",
      "url": "https://www.youtube.com/watch?v=XXXXXXXXXXX",
      "nota_curador": "Assista antes de resolver as questões de porcentagem.",
      "ordem": 1,
      "ativo": true
    }
  ]
}
```

O campo `materia` no topo do JSON e opcional e vale como padrao para todos os itens. Cada item tambem pode informar a propria `materia`, que tem prioridade sobre o padrao.

Campos:

- `materia`: slug da materia existente (no item ou no topo do JSON).
- `conteudo`: slug de um conteudo dessa materia.
- `url`: link do YouTube. Formatos aceitos: `youtube.com/watch?v=ID` (com ou sem `www.` ou `m.`), `youtu.be/ID`, `youtube.com/shorts/ID`, `youtube.com/embed/ID`, `youtube.com/live/ID` e `youtube-nocookie.com/embed/ID`.
- `youtube_id`: identificador de 11 caracteres do video. Informe `url` ou `youtube_id`; se os dois forem enviados, precisam apontar para o mesmo video.
- `nota_curador`: texto opcional explicando por que o video foi escolhido.
- `ordem`: inteiro maior ou igual a zero (padrao `0`).
- `ativo`: booleano (padrao `true`).

Autoria:

- titulo, nome do canal, link do canal e thumbnail sao obtidos automaticamente do YouTube (oEmbed), consultado pelo servidor;
- os campos `titulo`, `canal`, `canal_nome` e `canal_url`, se enviados, sao ignorados. Isso garante que a autoria exibida seja sempre a do YouTube.

Regras:

- no maximo 50 videos por importacao;
- o mesmo video nao pode ser cadastrado duas vezes no mesmo conteudo (nem dentro do JSON, nem em relacao ao banco);
- o mesmo video pode ser usado em conteudos diferentes;
- videos privados, removidos ou com incorporacao desativada pelo autor geram erro, por exemplo `Vídeo 3: O vídeo é privado ou o autor não permite incorporá-lo em outros sites.`;
- a importacao e atomica: se qualquer video falhar, nenhum e cadastrado;
- a importacao consulta o YouTube pela internet. Com muitos videos ou o YouTube lento, prefira dividir em lotes menores.

Exemplo com mais de uma materia:

```json
{
  "videos": [
    {
      "materia": "matematica",
      "conteudo": "porcentagem",
      "url": "https://youtu.be/XXXXXXXXXXX",
      "ordem": 1
    },
    {
      "materia": "fisica",
      "conteudo": "cinematica",
      "youtube_id": "YYYYYYYYYYY",
      "nota_curador": "Boa revisão de MRU.",
      "ativo": false
    }
  ]
}
```

Exemplo invalido:

```json
{
  "videos": [
    {
      "materia": "matematica",
      "conteudo": "cinematica",
      "url": "https://vimeo.com/123456",
      "titulo": "Este campo é ignorado",
      "ordem": -1,
      "ativo": "sim"
    }
  ]
}
```

Erros desse exemplo: o conteudo nao pertence a materia, o link nao e do YouTube, a ordem e negativa e `ativo` nao e booleano.
